from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import func, literal, or_, select, text, union_all
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
        "max_payload_kg": float(vehicle.max_payload_kg) if vehicle.max_payload_kg is not None else None,
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
        select(func.count())
        .select_from(Vehicle)
        .where(
            Vehicle.tenant_id == tenant_id,
            Vehicle.status != "retired",
        )
    )
    count = result.scalar_one()
    if redis is not None:
        await redis.hset(cache_key, "vehicle_count", count)
        await redis.expire(cache_key, 30)
    return count


async def _check_vehicle_limit(db: AsyncSession, tenant: Tenant, redis: AsyncRedis | None) -> None:
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


async def list_vehicle_history(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """NQ-01: Single UNION ALL query replaces 10 serial queries.

    All 10 history sources are merged server-side. Pagination is applied by
    PostgreSQL (LIMIT/OFFSET on the outer SELECT), so there is no Python-side
    over-fetch regardless of the requested page depth.
    """
    vehicle = await _require_vehicle(db, tenant_id, vehicle_id)

    tid = tenant_id
    vid = vehicle_id

    _audit = select(
        AuditLog.created_at.label("occurred_at"),
        literal("audit").label("source"),
        AuditLog.action.label("event_type"),
        AuditLog.action.label("summary"),
        literal("audit_log").label("reference_type"),
        AuditLog.id.label("reference_id"),
        func.jsonb_build_object(
            "old_values", AuditLog.old_values,
            "new_values", AuditLog.new_values,
        ).label("details"),
    ).where(
        AuditLog.tenant_id == tid,
        AuditLog.entity_type == "vehicle",
        AuditLog.entity_id == vid,
    )

    _trips = select(
        func.coalesce(Trip.actual_departure, Trip.planned_departure, Trip.created_at).label("occurred_at"),
        literal("trips").label("source"),
        func.concat("trip.", Trip.status).label("event_type"),
        func.concat("Trip ", Trip.origin, " -> ", Trip.destination, " is ", Trip.status, ".").label("summary"),
        literal("trip").label("reference_type"),
        Trip.id.label("reference_id"),
        func.jsonb_build_object(
            "driver_id", Trip.driver_id,
            "origin", Trip.origin,
            "destination", Trip.destination,
            "km_start", Trip.km_start,
            "km_end", Trip.km_end,
            "billing_status", Trip.billing_status,
            "total_transport_cost", Trip.total_transport_cost,
            "actual_margin", Trip.actual_margin,
        ).label("details"),
    ).where(Trip.tenant_id == tid, Trip.vehicle_id == vid)

    _checklists = select(
        func.coalesce(
            Checklist.completed_at, Checklist.client_captured_at, Checklist.created_at
        ).label("occurred_at"),
        literal("checklists").label("source"),
        func.concat("checklist.", Checklist.status).label("event_type"),
        func.concat(Checklist.type, " checklist ", Checklist.status, ".").label("summary"),
        literal("checklist").label("reference_type"),
        Checklist.id.label("reference_id"),
        func.jsonb_build_object(
            "driver_id", Checklist.driver_id,
            "type", Checklist.type,
            "duration_seconds", Checklist.duration_seconds,
        ).label("details"),
    ).where(Checklist.tenant_id == tid, Checklist.vehicle_id == vid)

    _fuel_logs = select(
        FuelLog.fuel_date.label("occurred_at"),
        literal("fuel").label("source"),
        literal("fuel.external_refuel").label("event_type"),
        func.concat("External refuel of ", FuelLog.liters, " L.").label("summary"),
        literal("fuel_log").label("reference_type"),
        FuelLog.id.label("reference_id"),
        func.jsonb_build_object(
            "driver_id", FuelLog.driver_id,
            "station_name", FuelLog.station_name,
            "liters", FuelLog.liters,
            "total_cost", FuelLog.total_cost,
            "km_at_refuel", FuelLog.km_at_refuel,
            "flagged", FuelLog.flagged,
            "is_verified", FuelLog.is_verified,
        ).label("details"),
    ).where(FuelLog.tenant_id == tid, FuelLog.vehicle_id == vid)

    _refuels = select(
        VehicleRefuel.refueled_at.label("occurred_at"),
        literal("fuel_operations").label("source"),
        literal("fuel.internal_refuel").label("event_type"),
        func.concat("Internal refuel of ", VehicleRefuel.liters, " L.").label("summary"),
        literal("vehicle_refuel").label("reference_type"),
        VehicleRefuel.id.label("reference_id"),
        func.jsonb_build_object(
            "driver_id", VehicleRefuel.driver_id,
            "trip_id", VehicleRefuel.trip_id,
            "tank_id", VehicleRefuel.tank_id,
            "liters", VehicleRefuel.liters,
            "total_cost", VehicleRefuel.total_cost,
            "odometer_reading", VehicleRefuel.odometer_reading,
        ).label("details"),
    ).where(VehicleRefuel.tenant_id == tid, VehicleRefuel.vehicle_id == vid)

    _incidents = select(
        TripIncident.occurred_at.label("occurred_at"),
        literal("incidents").label("source"),
        func.concat("incident.", TripIncident.status).label("event_type"),
        func.concat(TripIncident.severity, " ", TripIncident.incident_type, " incident.").label("summary"),
        literal("trip_incident").label("reference_type"),
        TripIncident.id.label("reference_id"),
        func.jsonb_build_object(
            "trip_id", TripIncident.trip_id,
            "driver_id", TripIncident.driver_id,
            "severity", TripIncident.severity,
            "description", TripIncident.description,
            "delay_minutes", TripIncident.delay_minutes,
        ).label("details"),
    ).where(TripIncident.tenant_id == tid, TripIncident.vehicle_id == vid)

    _maint_requests = select(
        MaintenanceRequest.requested_at.label("occurred_at"),
        literal("workshop").label("source"),
        func.concat("maintenance_request.", MaintenanceRequest.status).label("event_type"),
        func.concat(
            MaintenanceRequest.priority, " ", MaintenanceRequest.request_type, " maintenance request.",
        ).label("summary"),
        literal("maintenance_request").label("reference_type"),
        MaintenanceRequest.id.label("reference_id"),
        func.jsonb_build_object(
            "trip_id", MaintenanceRequest.trip_id,
            "incident_id", MaintenanceRequest.incident_id,
            "description", MaintenanceRequest.description,
            "odometer_reading", MaintenanceRequest.odometer_reading,
        ).label("details"),
    ).where(
        MaintenanceRequest.tenant_id == tid,
        MaintenanceRequest.vehicle_id == vid,
    )

    _work_orders = select(
        func.coalesce(WorkOrder.closed_at, WorkOrder.created_at).label("occurred_at"),
        literal("workshop").label("source"),
        func.concat("work_order.", WorkOrder.status).label("event_type"),
        func.concat("Work order ", WorkOrder.work_order_number, " is ", WorkOrder.status, ".").label("summary"),
        literal("work_order").label("reference_type"),
        WorkOrder.id.label("reference_id"),
        func.jsonb_build_object(
            "maintenance_request_id", WorkOrder.maintenance_request_id,
            "estimated_cost", WorkOrder.estimated_cost,
            "actual_cost", WorkOrder.actual_cost,
            "planned_work", WorkOrder.planned_work,
        ).label("details"),
    ).where(WorkOrder.tenant_id == tid, WorkOrder.vehicle_id == vid)

    _schedules = select(
        func.coalesce(MaintenanceSchedule.due_at, MaintenanceSchedule.created_at).label("occurred_at"),
        literal("workshop").label("source"),
        func.concat("maintenance_schedule.", MaintenanceSchedule.status).label("event_type"),
        func.concat("Preventive maintenance schedule is ", MaintenanceSchedule.status, ".").label("summary"),
        literal("maintenance_schedule").label("reference_type"),
        MaintenanceSchedule.id.label("reference_id"),
        func.jsonb_build_object(
            "plan_id", MaintenanceSchedule.plan_id,
            "due_km", MaintenanceSchedule.due_km,
        ).label("details"),
    ).where(MaintenanceSchedule.tenant_id == tid, MaintenanceSchedule.vehicle_id == vid)

    _waivers = select(
        func.coalesce(OperationalWaiver.approved_at, OperationalWaiver.created_at).label("occurred_at"),
        literal("operations").label("source"),
        func.concat("waiver.", OperationalWaiver.status).label("event_type"),
        func.concat(OperationalWaiver.risk_level, " ", OperationalWaiver.waiver_type, " waiver.").label("summary"),
        literal("operational_waiver").label("reference_type"),
        OperationalWaiver.id.label("reference_id"),
        func.jsonb_build_object(
            "reason", OperationalWaiver.reason,
            "expires_at", OperationalWaiver.expires_at,
            "approved_by", OperationalWaiver.approved_by,
        ).label("details"),
    ).where(
        OperationalWaiver.tenant_id == tid,
        OperationalWaiver.entity_type == "vehicle",
        OperationalWaiver.entity_id == vid,
    )

    # NQ-01: Single round-trip — ORDER BY + LIMIT + OFFSET applied at the outer
    # level by PostgreSQL. No Python sort, no over-fetch.
    stmt = (
        union_all(
            _audit, _trips, _checklists, _fuel_logs, _refuels,
            _incidents, _maint_requests, _work_orders, _schedules, _waivers,
        )
        .order_by(text("occurred_at DESC NULLS LAST"))
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(stmt)
    items = [
        {
            "occurred_at": row.occurred_at,
            "source": row.source,
            "event_type": row.event_type,
            "summary": row.summary,
            "reference_type": row.reference_type,
            "reference_id": row.reference_id,
            "details": row.details or {},
        }
        for row in result
    ]

    return {
        "vehicle": {
            "id": vehicle.id,
            "plate": vehicle.plate,
            "status": vehicle.status,
            "current_km": vehicle.current_km,
        },
        "items": items,
        "limit": limit,
        "offset": offset,
        "returned": len(items),
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
