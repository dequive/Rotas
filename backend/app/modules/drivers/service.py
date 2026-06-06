import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import status
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.core.tokens import hash_token
from app.modules.audit.models import AuditLog
from app.modules.audit.service import record_audit_log
from app.modules.checklists.models import Checklist
from app.modules.drivers.models import Driver
from app.modules.drivers.schemas import DriverCreate, DriverDocumentRenewalRequest, DriverPatch
from app.modules.files.models import File
from app.modules.fuel.models import FuelLog, VehicleRefuel
from app.modules.operations.models import OperationalWaiver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip, TripIncident


def now_utc() -> datetime:
    return datetime.now(UTC)


def serialize_driver(driver: Driver) -> dict:
    return {
        "id": driver.id,
        "tenant_id": driver.tenant_id,
        "full_name": driver.full_name,
        "phone": driver.phone,
        "email": driver.email,
        "emergency_contact_name": driver.emergency_contact_name,
        "emergency_contact_phone": driver.emergency_contact_phone,
        "license_number": driver.license_number,
        "license_category": driver.license_category,
        "license_valid_until": driver.license_valid_until,
        "passport_number": driver.passport_number,
        "passport_valid_until": driver.passport_valid_until,
        "bi_number": driver.bi_number,
        "bi_valid_until": driver.bi_valid_until,
        "inss_number": driver.inss_number,
        "employment_type": driver.employment_type,
        "documents": driver.documents,
        "status": driver.status,
        "score": driver.score,
        "photo_file_id": driver.photo_file_id,
        "created_at": driver.created_at,
        "updated_at": driver.updated_at,
    }


async def _get_cached_driver_count(
    db: AsyncSession, tenant_id: UUID, redis: AsyncRedis | None
) -> int:
    """Return active driver count from Redis cache (TTL 30s) or DB (D-15)."""
    cache_key = f"tenant:limits:{tenant_id}"
    if redis is not None:
        cached = await redis.hget(cache_key, "driver_count")
        if cached is not None:
            return int(cached)
    result = await db.execute(
        select(func.count()).select_from(Driver).where(
            Driver.tenant_id == tenant_id,
            Driver.status != "inactive",
        )
    )
    count = result.scalar_one()
    if redis is not None:
        await redis.hset(cache_key, "driver_count", count)
        await redis.expire(cache_key, 30)
    return count


async def _check_driver_limit(
    db: AsyncSession, tenant: Tenant, redis: AsyncRedis | None
) -> None:
    """Raise plan_limit_reached if tenant is at or over max_drivers (D-13, D-14).

    Skip entirely when max_drivers is None (unlimited enterprise plan).
    """
    if tenant.max_drivers is None:
        return
    count = await _get_cached_driver_count(db, tenant.id, redis)
    if count >= tenant.max_drivers:
        raise ApiError(
            "plan_limit_reached",
            f"Driver limit reached ({count}/{tenant.max_drivers}). Upgrade your plan.",
            status_code=403,
            details={
                "upgrade_url": get_settings().upgrade_url,
                "dimension": "drivers",
                "used": count,
                "max": tenant.max_drivers,
            },
        )


async def _require_driver(db: AsyncSession, tenant_id: UUID, driver_id: UUID) -> Driver:
    driver = await db.get(Driver, driver_id)
    if not driver or driver.tenant_id != tenant_id:
        raise ApiError("driver_not_found", "Driver not found.", status_code=404)
    return driver


async def _phone_exists(
    db: AsyncSession,
    tenant_id: UUID,
    phone: str,
    *,
    exclude_driver_id: UUID | None = None,
) -> bool:
    query = select(Driver.id).where(Driver.tenant_id == tenant_id, Driver.phone == phone)
    if exclude_driver_id:
        query = query.where(Driver.id != exclude_driver_id)
    return await db.scalar(query) is not None


async def list_drivers(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Driver).where(Driver.tenant_id == tenant_id)

    if status_filter:
        query = query.where(Driver.status == status_filter)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Driver.full_name.ilike(pattern),
                Driver.phone.ilike(pattern),
                Driver.email.ilike(pattern),
                Driver.license_number.ilike(pattern),
            )
        )

    result = await db.execute(query.order_by(Driver.full_name.asc()).limit(limit).offset(offset))
    return [serialize_driver(driver) for driver in result.scalars()]


async def create_driver(
    db: AsyncSession,
    tenant_id: UUID,
    payload: DriverCreate,
    *,
    actor_id: UUID | None = None,
    redis: AsyncRedis | None = None,
) -> dict:
    tenant = await db.get(Tenant, tenant_id)
    if not tenant or not tenant.is_active:
        raise ApiError(
            "tenant_not_found",
            "Tenant not found or inactive.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    await _check_driver_limit(db, tenant, redis)

    if payload.phone and await _phone_exists(db, tenant_id, payload.phone):
        raise ApiError(
            "driver_phone_conflict",
            "Driver phone already exists for this tenant.",
            status_code=status.HTTP_409_CONFLICT,
            details={"phone": payload.phone},
        )

    driver = Driver(tenant_id=tenant_id, **payload.model_dump())
    db.add(driver)
    await db.flush()
    await db.refresh(driver)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="driver.created",
        entity_type="driver",
        entity_id=driver.id,
        new_values=serialize_driver(driver),
    )
    await db.commit()
    await db.refresh(driver)
    return serialize_driver(driver)


async def get_driver(db: AsyncSession, tenant_id: UUID, driver_id: UUID) -> dict:
    return serialize_driver(await _require_driver(db, tenant_id, driver_id))


def _number(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return value


def _history_event(
    *,
    occurred_at: datetime | None,
    source: str,
    event_type: str,
    summary: str,
    reference_type: str,
    reference_id: UUID,
    details: dict | None = None,
) -> dict:
    return {
        "occurred_at": occurred_at,
        "source": source,
        "event_type": event_type,
        "summary": summary,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "details": details or {},
    }


async def list_driver_history(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    driver = await _require_driver(db, tenant_id, driver_id)
    window = min(limit + offset, 500)
    events: list[dict] = []

    audit_rows = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.entity_type == "driver",
            AuditLog.entity_id == driver_id,
        )
        .order_by(AuditLog.created_at.desc())
        .limit(window)
    )
    for log in audit_rows.scalars():
        events.append(
            _history_event(
                occurred_at=log.created_at,
                source="audit",
                event_type=log.action,
                summary=log.action.replace("_", " "),
                reference_type="audit_log",
                reference_id=log.id,
                details={"old_values": log.old_values, "new_values": log.new_values},
            )
        )

    trip_rows = await db.execute(
        select(Trip)
        .where(Trip.tenant_id == tenant_id, Trip.driver_id == driver_id)
        .order_by(Trip.created_at.desc())
        .limit(window)
    )
    for trip in trip_rows.scalars():
        events.append(
            _history_event(
                occurred_at=trip.actual_departure
                or trip.planned_departure
                or trip.created_at,
                source="trips",
                event_type=f"trip.{trip.status}",
                summary=f"Trip {trip.origin} -> {trip.destination} is {trip.status}.",
                reference_type="trip",
                reference_id=trip.id,
                details={
                    "vehicle_id": trip.vehicle_id,
                    "origin": trip.origin,
                    "destination": trip.destination,
                    "km_start": trip.km_start,
                    "km_end": trip.km_end,
                    "billing_status": trip.billing_status,
                    "total_transport_cost": _number(trip.total_transport_cost),
                    "actual_margin": _number(trip.actual_margin),
                },
            )
        )

    checklist_rows = await db.execute(
        select(Checklist)
        .where(Checklist.tenant_id == tenant_id, Checklist.driver_id == driver_id)
        .order_by(Checklist.created_at.desc())
        .limit(window)
    )
    for checklist in checklist_rows.scalars():
        events.append(
            _history_event(
                occurred_at=checklist.completed_at
                or checklist.client_captured_at
                or checklist.created_at,
                source="checklists",
                event_type=f"checklist.{checklist.status}",
                summary=f"{checklist.type} checklist {checklist.status}.",
                reference_type="checklist",
                reference_id=checklist.id,
                details={
                    "vehicle_id": checklist.vehicle_id,
                    "type": checklist.type,
                    "duration_seconds": checklist.duration_seconds,
                },
            )
        )

    fuel_log_rows = await db.execute(
        select(FuelLog)
        .where(FuelLog.tenant_id == tenant_id, FuelLog.driver_id == driver_id)
        .order_by(FuelLog.fuel_date.desc())
        .limit(window)
    )
    for fuel_log in fuel_log_rows.scalars():
        events.append(
            _history_event(
                occurred_at=fuel_log.fuel_date,
                source="fuel",
                event_type="fuel.external_refuel",
                summary=f"External refuel of {_number(fuel_log.liters)} L.",
                reference_type="fuel_log",
                reference_id=fuel_log.id,
                details={
                    "vehicle_id": fuel_log.vehicle_id,
                    "station_name": fuel_log.station_name,
                    "liters": _number(fuel_log.liters),
                    "total_cost": _number(fuel_log.total_cost),
                    "km_at_refuel": fuel_log.km_at_refuel,
                    "flagged": fuel_log.flagged,
                    "is_verified": fuel_log.is_verified,
                },
            )
        )

    refuel_rows = await db.execute(
        select(VehicleRefuel)
        .where(VehicleRefuel.tenant_id == tenant_id, VehicleRefuel.driver_id == driver_id)
        .order_by(VehicleRefuel.refueled_at.desc())
        .limit(window)
    )
    for refuel in refuel_rows.scalars():
        events.append(
            _history_event(
                occurred_at=refuel.refueled_at,
                source="fuel_operations",
                event_type="fuel.internal_refuel",
                summary=f"Internal refuel of {_number(refuel.liters)} L.",
                reference_type="vehicle_refuel",
                reference_id=refuel.id,
                details={
                    "vehicle_id": refuel.vehicle_id,
                    "trip_id": refuel.trip_id,
                    "tank_id": refuel.tank_id,
                    "liters": _number(refuel.liters),
                    "total_cost": _number(refuel.total_cost),
                    "odometer_reading": refuel.odometer_reading,
                },
            )
        )

    incident_rows = await db.execute(
        select(TripIncident)
        .where(TripIncident.tenant_id == tenant_id, TripIncident.driver_id == driver_id)
        .order_by(TripIncident.occurred_at.desc())
        .limit(window)
    )
    for incident in incident_rows.scalars():
        events.append(
            _history_event(
                occurred_at=incident.occurred_at,
                source="incidents",
                event_type=f"incident.{incident.status}",
                summary=f"{incident.severity} {incident.incident_type} incident.",
                reference_type="trip_incident",
                reference_id=incident.id,
                details={
                    "trip_id": incident.trip_id,
                    "vehicle_id": incident.vehicle_id,
                    "severity": incident.severity,
                    "description": incident.description,
                    "delay_minutes": incident.delay_minutes,
                },
            )
        )

    waiver_rows = await db.execute(
        select(OperationalWaiver)
        .where(
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.entity_type == "driver",
            OperationalWaiver.entity_id == driver_id,
        )
        .order_by(OperationalWaiver.created_at.desc())
        .limit(window)
    )
    for waiver in waiver_rows.scalars():
        events.append(
            _history_event(
                occurred_at=waiver.approved_at or waiver.created_at,
                source="operations",
                event_type=f"waiver.{waiver.status}",
                summary=f"{waiver.risk_level} {waiver.waiver_type} waiver.",
                reference_type="operational_waiver",
                reference_id=waiver.id,
                details={
                    "reason": waiver.reason,
                    "expires_at": waiver.expires_at,
                    "approved_by": waiver.approved_by,
                },
            )
        )

    events.sort(key=lambda item: item["occurred_at"] or datetime.min, reverse=True)
    return {
        "driver": {
            "id": driver.id,
            "full_name": driver.full_name,
            "status": driver.status,
            "score": driver.score,
        },
        "items": events[offset : offset + limit],
        "limit": limit,
        "offset": offset,
        "returned": len(events[offset : offset + limit]),
    }


async def patch_driver(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    payload: DriverPatch,
    *,
    actor_id: UUID | None = None,
) -> dict:
    driver = await _require_driver(db, tenant_id, driver_id)
    old_values = serialize_driver(driver)
    values = payload.model_dump(exclude_unset=True)

    if "phone" in values and values["phone"] and values["phone"] != driver.phone:
        if await _phone_exists(db, tenant_id, values["phone"], exclude_driver_id=driver.id):
            raise ApiError(
                "driver_phone_conflict",
                "Driver phone already exists for this tenant.",
                status_code=status.HTTP_409_CONFLICT,
                details={"phone": values["phone"]},
            )

    for field, value in values.items():
        setattr(driver, field, value)

    await db.flush()
    await db.refresh(driver)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="driver.updated",
        entity_type="driver",
        entity_id=driver.id,
        old_values=old_values,
        new_values=serialize_driver(driver),
    )
    await db.commit()
    await db.refresh(driver)
    return serialize_driver(driver)


async def issue_pairing_code(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    driver = await _require_driver(db, tenant_id, driver_id)
    if driver.status != "active":
        raise ApiError(
            "driver_inactive",
            "Driver must be active to pair a device.",
            status_code=409,
        )
    code = f"{secrets.randbelow(1_000_000):06d}"
    driver.pairing_code_hash = hash_token(code)
    driver.pairing_code_expires_at = datetime.now(UTC) + timedelta(minutes=15)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="driver.pairing_code_issued",
        entity_type="driver",
        entity_id=driver.id,
    )
    await db.commit()
    return {
        "driver_id": driver.id,
        "pairing_code": code,
        "expires_at": driver.pairing_code_expires_at,
    }


async def get_driver_scorecard(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    days: int = 30,
) -> dict:
    """D-08: Compute driver scorecard from existing trip/sync/delivery data.

    Returns score 0-100 with tier, or None score if insufficient data (< 3 trips).
    All aggregations use SQL — no Python-level iteration over rows.

    Formula (D-08):
    - 40% delivery proof rate (delivered / completed trips)
    - 25% sync discipline (avg sync events per trip, normalized 0-100)
    - 20% distance (total km, normalized: 500km/period = 100)
    - 15% stop efficiency (avg stop min, inverted — 0 min = 100, >=60 min = 0)
    """
    from app.modules.cargo.models import DeliveryProof
    from app.modules.sync.models import SyncEvent
    from app.modules.trips.models import Trip, TripStop

    window_start = now_utc() - timedelta(days=days)

    # --- Completed trips in window ---
    completed_count = (
        await db.scalar(
            select(func.count(Trip.id)).where(
                Trip.tenant_id == tenant_id,
                Trip.driver_id == driver_id,
                Trip.status == "completed",
                Trip.actual_departure >= window_start,
            )
        )
        or 0
    )

    # Minimum viable window check (D-09)
    if completed_count < 3:
        return {
            "driver_id": str(driver_id),
            "score": None,
            "tier": "insuficiente",
            "message": "Mínimo 3 viagens em 30 dias para score válido",
            "period_days": days,
            "completed_trips": completed_count,
            "metrics": {},
        }

    # --- Metric 1: Delivery proof rate (40%) ---
    trips_with_proof = (
        await db.scalar(
            select(func.count(func.distinct(Trip.id)))
            .join(DeliveryProof, DeliveryProof.trip_id == Trip.id)
            .where(
                Trip.tenant_id == tenant_id,
                Trip.driver_id == driver_id,
                Trip.status == "completed",
                Trip.actual_departure >= window_start,
            )
        )
        or 0
    )
    delivery_rate = (trips_with_proof / completed_count) * 100  # 0-100

    # --- Metric 2: Sync discipline (25%) ---
    # Count sync_events for this driver in window; normalize: 5 events/trip = 100
    sync_count = (
        await db.scalar(
            select(func.count(SyncEvent.id)).where(
                SyncEvent.tenant_id == tenant_id,
                SyncEvent.driver_id == driver_id,
                SyncEvent.created_at >= window_start,
            )
        )
        or 0
    )
    sync_per_trip = sync_count / completed_count
    sync_score = min(sync_per_trip / 5.0 * 100, 100.0)

    # --- Metric 3: Distance (20%) ---
    total_km_result = await db.execute(
        select(func.sum(Trip.km_end - Trip.km_start).label("total_km")).where(
            Trip.tenant_id == tenant_id,
            Trip.driver_id == driver_id,
            Trip.status == "completed",
            Trip.actual_departure >= window_start,
            Trip.km_end.isnot(None),
            Trip.km_start.isnot(None),
        )
    )
    total_km = total_km_result.scalar() or 0
    # Normalize: 500 km over period = 100 score
    distance_score = min((total_km / 500.0) * 100, 100.0)

    # --- Metric 4: Stop efficiency (15%) ---
    stop_data = await db.execute(
        select(
            func.avg(
                func.extract("epoch", TripStop.resumed_at - TripStop.stopped_at) / 60.0
            ).label("avg_stop_minutes")
        )
        .join(Trip, Trip.id == TripStop.trip_id)
        .where(
            Trip.tenant_id == tenant_id,
            Trip.driver_id == driver_id,
            Trip.status == "completed",
            Trip.actual_departure >= window_start,
            TripStop.resumed_at.isnot(None),
            TripStop.stopped_at.isnot(None),
        )
    )
    avg_stop_minutes = float(stop_data.scalar() or 0.0)
    # Invert: 0 min avg = 100 score, 60+ min avg = 0 score
    stop_score = max(0.0, (1.0 - (avg_stop_minutes / 60.0)) * 100)

    # --- Composite score ---
    composite = (
        0.40 * delivery_rate
        + 0.25 * sync_score
        + 0.20 * distance_score
        + 0.15 * stop_score
    )
    score = round(composite, 1)

    # Tier assignment (D-09)
    if score >= 80:
        tier = "verde"
    elif score >= 60:
        tier = "amarelo"
    else:
        tier = "vermelho"

    return {
        "driver_id": str(driver_id),
        "score": score,
        "tier": tier,
        "period_days": days,
        "completed_trips": completed_count,
        "metrics": {
            "delivery_rate": round(delivery_rate, 1),
            "sync_score": round(sync_score, 1),
            "distance_score": round(distance_score, 1),
            "stop_score": round(stop_score, 1),
            "total_km": total_km,
            "avg_stop_minutes": round(avg_stop_minutes, 1),
        },
    }


async def renew_driver_document(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
    document_type: str,
    payload: DriverDocumentRenewalRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    if document_type not in {"driving_license", "passport", "bi"}:
        raise ApiError(
            "unsupported_driver_document",
            "Supported driver documents are driving_license, passport and bi.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"document_type": document_type},
        )
    driver = await _require_driver(db, tenant_id, driver_id)
    if payload.file_id is not None:
        file = await db.get(File, payload.file_id)
        if not file or file.tenant_id != tenant_id:
            raise ApiError("file_not_found", "File not found.", status_code=404)
        file.entity_type = "driver_document"
        file.entity_id = driver.id

    old_values = serialize_driver(driver)
    documents = dict(driver.documents or {})
    current_document = documents.get(document_type)
    if not isinstance(current_document, dict):
        current_document = {}
    current_document.update(
        {
            "valid_until": payload.valid_until.isoformat(),
            "file_id": str(payload.file_id) if payload.file_id else current_document.get("file_id"),
            "reference": payload.reference,
            "notes": payload.notes,
            "renewed_at": datetime.now(UTC).isoformat(),
        }
    )
    documents[document_type] = current_document
    driver.documents = documents
    if document_type == "driving_license":
        driver.license_valid_until = payload.valid_until
        if payload.reference:
            driver.license_number = payload.reference
    if document_type == "passport":
        driver.passport_valid_until = payload.valid_until
        if payload.reference:
            driver.passport_number = payload.reference
    if document_type == "bi":
        driver.bi_valid_until = payload.valid_until
        if payload.reference:
            driver.bi_number = payload.reference

    await db.flush()
    await db.refresh(driver)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="driver.document_renewed",
        entity_type="driver",
        entity_id=driver.id,
        old_values=old_values,
        new_values={
            "document_type": document_type,
            "valid_until": payload.valid_until,
            "file_id": payload.file_id,
            "reference": payload.reference,
        },
    )
    await db.commit()
    await db.refresh(driver)
    return serialize_driver(driver)
