import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, require_permission
from app.modules.availability import service as availability_service
from app.modules.drivers.models import Driver
from app.modules.vehicles.models import Vehicle

router = APIRouter(prefix="/availability", tags=["availability"])


async def _compute_drivers_list(
    db: AsyncSession,
    tenant_id,
    limit: int,
    offset: int,
) -> list[dict]:
    result = await db.execute(
        select(Driver)
        .where(Driver.tenant_id == tenant_id, Driver.status == "active")
        .offset(offset)
        .limit(limit)
    )
    drivers = result.scalars().all()
    items = []
    for driver in drivers:
        summary = await availability_service.driver_availability_summary(db, tenant_id, driver.id)
        items.append(
            {
                "driver_id": str(summary["entity_id"]),
                "driver_name": driver.full_name,
                "status": summary["status"],
                "available": summary["available"],
                "blockers": summary["blockers"],
                "warnings": summary["warnings"],
                "active_trip_id": (
                    str(summary["active_trip_id"]) if summary["active_trip_id"] else None
                ),
                "hos_status": "pending",
            }
        )
    return items


async def _compute_vehicles_list(
    db: AsyncSession,
    tenant_id,
    limit: int,
    offset: int,
) -> list[dict]:
    result = await db.execute(
        select(Vehicle)
        .where(Vehicle.tenant_id == tenant_id)
        .offset(offset)
        .limit(limit)
    )
    vehicles = result.scalars().all()
    items = []
    for vehicle in vehicles:
        summary = await availability_service.vehicle_availability_summary(db, tenant_id, vehicle.id)
        # Derive computed_status from blockers
        blocker_codes = [b["code"] for b in summary["blockers"]]
        if "vehicle_workshop_blocked" in blocker_codes:
            computed_status = "in_maintenance"
        elif "vehicle_assignment_conflict" in blocker_codes:
            computed_status = "in_trip"
        elif not summary["available"]:
            computed_status = "unavailable"
        else:
            computed_status = "available"
        items.append(
            {
                "vehicle_id": str(summary["entity_id"]),
                "plate_number": vehicle.plate,
                "status": computed_status,
                "available": summary["available"],
                "blockers": summary["blockers"],
                "warnings": summary["warnings"],
                "active_trip_id": (
                    str(summary["active_trip_id"]) if summary["active_trip_id"] else None
                ),
                "active_work_order_id": (
                    str(summary["active_work_order_id"])
                    if summary["active_work_order_id"]
                    else None
                ),
            }
        )
    return items


@router.get("/drivers")
async def list_driver_availability(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return availability summary for all active drivers in the tenant.

    Query params:
    - status: optional filter ("available", "hos_warning", "hos_violation", "unavailable")
    - limit / offset: pagination
    """
    redis = getattr(request.app.state, "redis", None)
    tenant_id = principal.tenant_id

    items: list[dict] | None = None

    if redis is not None:
        key = f"av:drivers:{tenant_id}"
        lock_key = f"av:drivers:{tenant_id}:lock"
        cached = await redis.get(key)
        if cached:
            items = json.loads(cached)
        else:
            locked = await redis.set(lock_key, "1", nx=True, ex=5)
            if locked:
                try:
                    items = await _compute_drivers_list(db, tenant_id, limit=200, offset=0)
                    await redis.set(key, json.dumps(items, default=str), ex=30)
                finally:
                    await redis.delete(lock_key)

    if items is None:
        items = await _compute_drivers_list(db, tenant_id, limit=limit, offset=offset)
    else:
        # Apply pagination to cached full list
        items = items[offset: offset + limit]

    if status is not None:
        items = [i for i in items if i["status"] == status]

    return {"items": items, "total": len(items), "limit": limit, "offset": offset}


@router.get("/vehicles")
async def list_vehicle_availability(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Return availability summary for all vehicles in the tenant.

    Query params:
    - status: optional filter ("available", "in_trip", "in_maintenance", "unavailable")
    - limit / offset: pagination
    """
    redis = getattr(request.app.state, "redis", None)
    tenant_id = principal.tenant_id

    items: list[dict] | None = None

    if redis is not None:
        key = f"av:vehicles:{tenant_id}"
        lock_key = f"av:vehicles:{tenant_id}:lock"
        cached = await redis.get(key)
        if cached:
            items = json.loads(cached)
        else:
            locked = await redis.set(lock_key, "1", nx=True, ex=5)
            if locked:
                try:
                    items = await _compute_vehicles_list(db, tenant_id, limit=200, offset=0)
                    await redis.set(key, json.dumps(items, default=str), ex=30)
                finally:
                    await redis.delete(lock_key)

    if items is None:
        items = await _compute_vehicles_list(db, tenant_id, limit=limit, offset=offset)
    else:
        # Apply pagination to cached full list
        items = items[offset: offset + limit]

    if status is not None:
        items = [i for i in items if i["status"] == status]

    return {"items": items, "total": len(items), "limit": limit, "offset": offset}
