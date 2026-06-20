import json
import logging
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/availability", tags=["availability"])

AV_TTL = 30  # seconds
AV_LOCK_TTL = 5  # seconds for stampede lock


def _driver_availability_status(item: dict) -> str:
    """Derive availability status string for a driver item dict.

    Returns one of: "available", "hos_warning", "hos_violation", "unavailable"
    """
    if any(b["code"] == "driver_hos_violation" for b in item.get("blockers", [])):
        return "hos_violation"
    if item.get("hos_status") == "warning":
        return "hos_warning"
    if item.get("available"):
        return "available"
    return "unavailable"


def _filter_drivers(items: list[dict], status: str | None) -> list[dict]:
    """Apply optional status filter to driver items.

    Filter values:
    - "available"     → item["available"] == True (and no HOS violation/warning)
    - "hos_warning"   → hos_status == "warning"
    - "hos_violation" → any blocker with code "driver_hos_violation"
    - "unavailable"   → item["available"] == False
    - None            → no filter
    """
    if status is None:
        return items
    if status == "available":
        return [i for i in items if i.get("available") is True]
    if status == "hos_warning":
        return [i for i in items if i.get("hos_status") == "warning"]
    if status == "hos_violation":
        return [
            i
            for i in items
            if any(b["code"] == "driver_hos_violation" for b in i.get("blockers", []))
        ]
    if status == "unavailable":
        return [i for i in items if not i.get("available")]
    # Fallback: match on derived availability_status field
    return [i for i in items if i.get("availability_status") == status]


def _filter_vehicles(items: list[dict], status: str | None) -> list[dict]:
    """Apply optional status filter to vehicle items.

    Filter values:
    - "available"      → computed_status == "available"
    - "in_trip"        → computed_status == "in_trip"
    - "in_maintenance" → computed_status == "in_maintenance"
    - "unavailable"    → computed_status == "unavailable"
    - None             → no filter
    """
    if status is None:
        return items
    return [i for i in items if i.get("computed_status") == status]


async def _compute_drivers_list(db: AsyncSession, tenant_id) -> list[dict]:
    """Fetch all active drivers and compute availability summary for each.

    Fetches the full fleet (no pagination) so the caller can filter + paginate
    in Python — either from cache or inline.
    """
    result = await db.execute(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.status == "active")
    )
    drivers = result.scalars().all()
    items = []
    for driver in drivers:
        try:
            summary = await availability_service.driver_availability_summary(
                db, tenant_id, driver.id
            )
        except Exception:
            logger.warning(
                "Skipping driver %s in availability list — summary raised error",
                driver.id,
                exc_info=True,
            )
            continue

        # Extract HOS data — populated by plan 16-02; defaults to "ok" if absent
        hos = summary.get("hos") or {}
        hos_status = hos.get("status", "ok")

        item: dict = {
            "driver_id": str(summary["entity_id"]),
            "driver_name": driver.full_name,
            "status": summary["status"],  # DB field: "active" | "inactive"
            "available": summary["available"],
            "blockers": summary["blockers"],
            "warnings": summary["warnings"],
            "active_trip_id": (
                str(summary["active_trip_id"]) if summary.get("active_trip_id") else None
            ),
            "hos_status": hos_status,
            "hours_today": hos.get("hours_today"),
            "hours_this_week": hos.get("hours_this_week"),
        }
        item["availability_status"] = _driver_availability_status(item)
        items.append(item)
    return items


async def _compute_vehicles_list(db: AsyncSession, tenant_id) -> list[dict]:
    """Fetch all vehicles and compute availability summary for each.

    Fetches the full fleet (no pagination) so the caller can filter + paginate
    in Python — either from cache or inline. Includes inactive vehicles for a
    full fleet picture.
    """
    result = await db.execute(select(Vehicle).where(Vehicle.tenant_id == tenant_id))
    vehicles = result.scalars().all()
    items = []
    for vehicle in vehicles:
        try:
            summary = await availability_service.vehicle_availability_summary(
                db, tenant_id, vehicle.id
            )
        except Exception:
            logger.warning(
                "Skipping vehicle %s in availability list — summary raised error",
                vehicle.id,
                exc_info=True,
            )
            continue

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

        # Extract work_order_id from the workshop blocker if present
        work_order_id: str | None = None
        for b in summary["blockers"]:
            if b["code"] == "vehicle_workshop_blocked" and b.get("work_order_id"):
                work_order_id = str(b["work_order_id"])
                break
        if work_order_id is None and summary.get("active_work_order_id"):
            work_order_id = str(summary["active_work_order_id"])

        items.append(
            {
                "vehicle_id": str(summary["entity_id"]),
                "plate_number": vehicle.plate,
                "status": computed_status,  # alias for computed_status for convenience
                "computed_status": computed_status,
                "available": summary["available"],
                "blockers": summary["blockers"],
                "warnings": summary["warnings"],
                "active_trip_id": (
                    str(summary["active_trip_id"]) if summary.get("active_trip_id") else None
                ),
                "active_work_order_id": work_order_id,
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
    - status: optional filter — "available" | "hos_warning" | "hos_violation" | "unavailable"
    - limit / offset: pagination applied after filter
    """
    redis = getattr(request.app.state, "redis", None)
    tenant_id = principal.tenant_id

    all_items: list[dict] | None = None

    if redis is not None:
        key = f"av:drivers:{tenant_id}"
        lock_key = f"av:drivers:{tenant_id}:lock"
        cached = await redis.get(key)
        if cached:
            all_items = json.loads(cached)
        else:
            locked = await redis.set(lock_key, "1", nx=True, ex=AV_LOCK_TTL)
            if locked:
                try:
                    all_items = await _compute_drivers_list(db, tenant_id)
                    await redis.set(key, json.dumps(all_items, default=str), ex=AV_TTL)
                finally:
                    await redis.delete(lock_key)

    if all_items is None:
        # Redis unavailable or another request holds the lock — compute from DB
        all_items = await _compute_drivers_list(db, tenant_id)

    # Filter, then paginate
    filtered = _filter_drivers(all_items, status)
    total = len(filtered)
    page = filtered[offset : offset + limit]

    return {"items": page, "total": total, "limit": limit, "offset": offset}


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
    - status: optional filter — "available" | "in_trip" | "in_maintenance" | "unavailable"
    - limit / offset: pagination applied after filter
    """
    redis = getattr(request.app.state, "redis", None)
    tenant_id = principal.tenant_id

    all_items: list[dict] | None = None

    if redis is not None:
        key = f"av:vehicles:{tenant_id}"
        lock_key = f"av:vehicles:{tenant_id}:lock"
        cached = await redis.get(key)
        if cached:
            all_items = json.loads(cached)
        else:
            locked = await redis.set(lock_key, "1", nx=True, ex=AV_LOCK_TTL)
            if locked:
                try:
                    all_items = await _compute_vehicles_list(db, tenant_id)
                    await redis.set(key, json.dumps(all_items, default=str), ex=AV_TTL)
                finally:
                    await redis.delete(lock_key)

    if all_items is None:
        # Redis unavailable or another request holds the lock — compute from DB
        all_items = await _compute_vehicles_list(db, tenant_id)

    # Filter, then paginate
    filtered = _filter_vehicles(all_items, status)
    total = len(filtered)
    page = filtered[offset : offset + limit]

    return {"items": page, "total": total, "limit": limit, "offset": offset}
