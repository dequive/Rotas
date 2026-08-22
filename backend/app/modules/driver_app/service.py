from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.checklists import service as checklists_service
from app.modules.trips import service as trips_service
from app.modules.trips.models import Trip

ACTIVE_DRIVER_TRIP_STATUSES = (
    "planned",
    "dispatch_pending",
    "dispatched",
    "in_progress",
    "delayed",
    "incident",
)


async def list_driver_checklist_templates(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    return await checklists_service.list_templates(
        db,
        tenant_id,
        type_filter="pre_partida",
        is_active=True,
    )


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
    return trips_service.serialize_trip(trip)


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
