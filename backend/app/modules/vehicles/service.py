from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import status
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.modules.audit.models import AuditLog
from app.modules.audit.service import record_audit_log
from app.modules.checklists.models import Checklist
from app.modules.files.models import File
from app.modules.fuel.models import FuelLog, VehicleRefuel
from app.modules.operations.models import OperationalWaiver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip, TripIncident
from app.modules.vehicles.models import Vehicle
from app.modules.vehicles.schemas import VehicleCreate, VehicleDocumentRenewalRequest, VehiclePatch
from app.modules.workshop.models import MaintenanceRequest, MaintenanceSchedule, WorkOrder


def serialize_vehicle(vehicle: Vehicle) -> dict:
    return {
        "id": vehicle.id,
        "tenant_id": vehicle.tenant_id,
        "plate": vehicle.plate,
        "chassis": vehicle.chassis,
        "brand": vehicle.brand,
        "model": vehicle.model,
        "year": vehicle.year,
        "color": vehicle.color,
        "category": vehicle.category,
        "status": vehicle.status,
        "current_km": vehicle.current_km,
        "fuel_type": vehicle.fuel_type,
        "documents": vehicle.documents,
        "qr_code_hash": vehicle.qr_code_hash,
        "photo_file_id": vehicle.photo_file_id,
        "avg_consumption_target": vehicle.avg_consumption_target,
        "fuel_limit_daily": vehicle.fuel_limit_daily,
        "created_at": vehicle.created_at,
        "updated_at": vehicle.updated_at,
    }


async def _require_vehicle(db: AsyncSession, tenant_id: UUID, vehicle_id: UUID) -> Vehicle:
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)
    return vehicle


async def _get_cached_vehicle_count(
    db: AsyncSession, tenant_id: UUID, redis: AsyncRedis | None
) -> int:
    """Return active vehicle count from Redis cache (TTL 30s) or DB (D-15)."""
    cache_key = f"tenant:limits:{tenant_id}"
    if redis is not None:
        cached = await redis.hget(cache_key, "vehicle_count")
        if cached is not None:
            return int(cached)
    result = await db.execute(
        select(func.count()).select_from(Vehicle).where(
            Vehicle.tenant_id == tenant_id,
            Vehicle.status != "retired",
        )
    )
    count = result.scalar_one()
    if redis is not None:
        await redis.hset(cache_key, "vehicle_count", count)
        await redis.expire(cache_key, 30)
    return count


async def _check_vehicle_limit(
    db: AsyncSession, tenant: Tenant, redis: AsyncRedis | None
) -> None:
    """Raise plan_limit_reached if tenant is at or over max_vehicles (D-13, D-14).

    Skip entirely when max_vehicles is None (unlimited enterprise plan).
    """
    if tenant.max_vehicles is None:
        return
    count = await _get_cached_vehicle_count(db, tenant.id, redis)
    if count >= tenant.max_vehicles:
        raise ApiError(
            "plan_limit_reached",
            f"Vehicle limit reached ({count}/{tenant.max_vehicles}). Upgrade your plan.",
            status_code=403,
            details={
                "upgrade_url": get_settings().upgrade_url,
                "dimension": "vehicles",
                "used": count,
                "max": tenant.max_vehicles,
            },
        )


async def _plate_exists(
    db: AsyncSession,
    tenant_id: UUID,
    plate: str,
    *,
    exclude_vehicle_id: UUID | None = None,
) -> bool:
    query = select(Vehicle.id).where(Vehicle.tenant_id == tenant_id, Vehicle.plate == plate)
    if exclude_vehicle_id:
        query = query.where(Vehicle.id != exclude_vehicle_id)
    return await db.scalar(query) is not None


async def list_vehicles(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Vehicle).where(Vehicle.tenant_id == tenant_id)

    if status_filter:
        query = query.where(Vehicle.status == status_filter)
    if search:
        pattern = f"%{search}%"
        query = query.where(
            or_(
                Vehicle.plate.ilike(pattern),
                Vehicle.brand.ilike(pattern),
                Vehicle.model.ilike(pattern),
                Vehicle.chassis.ilike(pattern),
            )
        )

    result = await db.execute(query.order_by(Vehicle.plate.asc()).limit(limit).offset(offset))
    return [serialize_vehicle(vehicle) for vehicle in result.scalars()]


async def create_vehicle(
    db: AsyncSession,
    tenant_id: UUID,
    payload: VehicleCreate,
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

    await _check_vehicle_limit(db, tenant, redis)

    if await _plate_exists(db, tenant_id, payload.plate):
        raise ApiError(
            "vehicle_plate_conflict",
            "Vehicle plate already exists for this tenant.",
            status_code=status.HTTP_409_CONFLICT,
            details={"plate": payload.plate},
        )

    vehicle = Vehicle(tenant_id=tenant_id, **payload.model_dump())
    db.add(vehicle)
    await db.flush()
    await db.refresh(vehicle)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle.created",
        entity_type="vehicle",
        entity_id=vehicle.id,
        new_values=serialize_vehicle(vehicle),
    )
    await db.commit()
    await db.refresh(vehicle)
    return serialize_vehicle(vehicle)


async def get_vehicle(db: AsyncSession, tenant_id: UUID, vehicle_id: UUID) -> dict:
    return serialize_vehicle(await _require_vehicle(db, tenant_id, vehicle_id))


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


async def list_vehicle_history(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    vehicle = await _require_vehicle(db, tenant_id, vehicle_id)
    window = min(limit + offset, 500)
    events: list[dict] = []

    audit_rows = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.tenant_id == tenant_id,
            AuditLog.entity_type == "vehicle",
            AuditLog.entity_id == vehicle_id,
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
        .where(Trip.tenant_id == tenant_id, Trip.vehicle_id == vehicle_id)
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
                    "driver_id": trip.driver_id,
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
        .where(Checklist.tenant_id == tenant_id, Checklist.vehicle_id == vehicle_id)
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
                    "driver_id": checklist.driver_id,
                    "type": checklist.type,
                    "duration_seconds": checklist.duration_seconds,
                },
            )
        )

    fuel_log_rows = await db.execute(
        select(FuelLog)
        .where(FuelLog.tenant_id == tenant_id, FuelLog.vehicle_id == vehicle_id)
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
                    "driver_id": fuel_log.driver_id,
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
        .where(VehicleRefuel.tenant_id == tenant_id, VehicleRefuel.vehicle_id == vehicle_id)
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
                    "driver_id": refuel.driver_id,
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
        .where(TripIncident.tenant_id == tenant_id, TripIncident.vehicle_id == vehicle_id)
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
                    "driver_id": incident.driver_id,
                    "severity": incident.severity,
                    "description": incident.description,
                    "delay_minutes": incident.delay_minutes,
                },
            )
        )

    maintenance_rows = await db.execute(
        select(MaintenanceRequest)
        .where(
            MaintenanceRequest.tenant_id == tenant_id,
            MaintenanceRequest.vehicle_id == vehicle_id,
        )
        .order_by(MaintenanceRequest.requested_at.desc())
        .limit(window)
    )
    for request in maintenance_rows.scalars():
        events.append(
            _history_event(
                occurred_at=request.requested_at,
                source="workshop",
                event_type=f"maintenance_request.{request.status}",
                summary=f"{request.priority} {request.request_type} maintenance request.",
                reference_type="maintenance_request",
                reference_id=request.id,
                details={
                    "trip_id": request.trip_id,
                    "incident_id": request.incident_id,
                    "description": request.description,
                    "odometer_reading": request.odometer_reading,
                },
            )
        )

    work_order_rows = await db.execute(
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id, WorkOrder.vehicle_id == vehicle_id)
        .order_by(WorkOrder.created_at.desc())
        .limit(window)
    )
    for work_order in work_order_rows.scalars():
        events.append(
            _history_event(
                occurred_at=work_order.closed_at or work_order.created_at,
                source="workshop",
                event_type=f"work_order.{work_order.status}",
                summary=f"Work order {work_order.work_order_number} is {work_order.status}.",
                reference_type="work_order",
                reference_id=work_order.id,
                details={
                    "maintenance_request_id": work_order.maintenance_request_id,
                    "estimated_cost": _number(work_order.estimated_cost),
                    "actual_cost": _number(work_order.actual_cost),
                    "planned_work": work_order.planned_work,
                },
            )
        )

    schedule_rows = await db.execute(
        select(MaintenanceSchedule)
        .where(
            MaintenanceSchedule.tenant_id == tenant_id,
            MaintenanceSchedule.vehicle_id == vehicle_id,
        )
        .order_by(MaintenanceSchedule.created_at.desc())
        .limit(window)
    )
    for schedule in schedule_rows.scalars():
        events.append(
            _history_event(
                occurred_at=schedule.due_at or schedule.created_at,
                source="workshop",
                event_type=f"maintenance_schedule.{schedule.status}",
                summary=f"Preventive maintenance schedule is {schedule.status}.",
                reference_type="maintenance_schedule",
                reference_id=schedule.id,
                details={"plan_id": schedule.plan_id, "due_km": schedule.due_km},
            )
        )

    waiver_rows = await db.execute(
        select(OperationalWaiver)
        .where(
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.entity_type == "vehicle",
            OperationalWaiver.entity_id == vehicle_id,
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
        "vehicle": {
            "id": vehicle.id,
            "plate": vehicle.plate,
            "status": vehicle.status,
            "current_km": vehicle.current_km,
        },
        "items": events[offset : offset + limit],
        "limit": limit,
        "offset": offset,
        "returned": len(events[offset : offset + limit]),
    }


async def patch_vehicle(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    payload: VehiclePatch,
    *,
    actor_id: UUID | None = None,
) -> dict:
    vehicle = await _require_vehicle(db, tenant_id, vehicle_id)
    old_values = serialize_vehicle(vehicle)
    values = payload.model_dump(exclude_unset=True)

    if "plate" in values and values["plate"] != vehicle.plate:
        if await _plate_exists(db, tenant_id, values["plate"], exclude_vehicle_id=vehicle.id):
            raise ApiError(
                "vehicle_plate_conflict",
                "Vehicle plate already exists for this tenant.",
                status_code=status.HTTP_409_CONFLICT,
                details={"plate": values["plate"]},
            )

    for field, value in values.items():
        setattr(vehicle, field, value)

    await db.flush()
    await db.refresh(vehicle)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle.updated",
        entity_type="vehicle",
        entity_id=vehicle.id,
        old_values=old_values,
        new_values=serialize_vehicle(vehicle),
    )
    await db.commit()
    await db.refresh(vehicle)
    return serialize_vehicle(vehicle)


async def get_vehicle_qr_code(db: AsyncSession, tenant_id: UUID, vehicle_id: UUID) -> dict:
    vehicle = await _require_vehicle(db, tenant_id, vehicle_id)
    qr_hash = vehicle.qr_code_hash or f"rotas:vehicle:{vehicle.id}"
    if not vehicle.qr_code_hash:
        vehicle.qr_code_hash = qr_hash
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            action="vehicle.qr_code_issued",
            entity_type="vehicle",
            entity_id=vehicle.id,
            new_values={"qr_code_hash": qr_hash},
        )
        await db.commit()
        await db.refresh(vehicle)

    return {
        "vehicle_id": vehicle.id,
        "plate": vehicle.plate,
        "qr_code_hash": vehicle.qr_code_hash,
        "deep_link": f"rotas://vehicles/{vehicle.id}/checklist",
    }


async def renew_vehicle_document(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    document_type: str,
    payload: VehicleDocumentRenewalRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    vehicle = await _require_vehicle(db, tenant_id, vehicle_id)
    if payload.file_id is not None:
        file = await db.get(File, payload.file_id)
        if not file or file.tenant_id != tenant_id:
            raise ApiError("file_not_found", "File not found.", status_code=404)
        file.entity_type = "vehicle_document"
        file.entity_id = vehicle.id

    old_values = serialize_vehicle(vehicle)
    documents = dict(vehicle.documents or {})
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
    documents[f"{document_type}_valid_until"] = payload.valid_until.isoformat()
    vehicle.documents = documents

    await db.flush()
    await db.refresh(vehicle)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle.document_renewed",
        entity_type="vehicle",
        entity_id=vehicle.id,
        old_values=old_values,
        new_values={
            "document_type": document_type,
            "valid_until": payload.valid_until,
            "file_id": payload.file_id,
            "reference": payload.reference,
        },
    )
    await db.commit()
    await db.refresh(vehicle)
    return serialize_vehicle(vehicle)
