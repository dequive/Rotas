from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.checklists import service as checklists_service
from app.modules.trips.models import Trip

ACTIVE_DRIVER_TRIP_STATUSES = (
    "planned",
    "dispatch_pending",
    "dispatched",
    "in_progress",
    "delayed",
    "incident",
)


def _serialize_driver_trip(trip: Trip) -> dict:
    return {
        "id": trip.id,
        "vehicle_id": trip.vehicle_id,
        "driver_id": trip.driver_id,
        "origin": trip.origin,
        "destination": trip.destination,
        "cargo_type": trip.cargo_type,
        "cargo_class": trip.cargo_class,
        "cargo_weight": float(trip.cargo_weight) if trip.cargo_weight is not None else None,
        "load_state": trip.load_state,
        "requires_load_permit": trip.requires_load_permit,
        "requires_cargo_manifest": trip.requires_cargo_manifest,
        "waybill_number": trip.waybill_number,
        "km_start": trip.km_start,
        "km_end": trip.km_end,
        "status": trip.status,
        "planned_departure": trip.planned_departure,
        "actual_departure": trip.actual_departure,
        "planned_arrival": trip.planned_arrival,
        "actual_arrival": trip.actual_arrival,
        "recipient_name": trip.recipient_name,
        "cargo_status": trip.cargo_status,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
    }


def _serialize_driver_template(template: dict) -> dict:
    return {
        key: template[key]
        for key in (
            "id",
            "name",
            "type",
            "category",
            "is_active",
            "items",
            "created_at",
            "updated_at",
        )
    }


async def list_driver_checklist_templates(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    templates = await checklists_service.list_templates(
        db,
        tenant_id,
        type_filter="pre_partida",
        is_active=True,
    )
    return [_serialize_driver_template(template) for template in templates]


async def get_active_driver_trip(
    db: AsyncSession,
    tenant_id: UUID,
    driver_id: UUID,
) -> dict | None:
    trip = await db.scalar(
        select(Trip)
        .where(
            Trip.tenant_id == tenant_id,
            Trip.driver_id == driver_id,
            Trip.status.in_(ACTIVE_DRIVER_TRIP_STATUSES),
        )
        .order_by(Trip.created_at.desc())
        .limit(1)
    )
    if trip is None:
        return None
    return _serialize_driver_trip(trip)


async def get_bootstrap_payload(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    driver_id: UUID,
    device_id: str | None,
) -> dict:
    return {
        "profile": {
            "tenant_id": tenant_id,
            "driver_id": driver_id,
            "device_id": device_id,
        },
        "checklistTemplates": await list_driver_checklist_templates(db, tenant_id),
        "activeTrip": await get_active_driver_trip(db, tenant_id, driver_id),
        # Transitional field for old clients. The assigned trip, not a fleet
        # selector, is the Driver app's source of vehicle identity.
        "vehicles": [],
    }
