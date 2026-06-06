from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import Principal
from app.core.permissions import ADMIN_ROLES, DASHBOARD_ROLES, require_roles
from app.core.deps import get_session
from app.modules.tenants import schemas, service
from app.modules.tenants.models import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me")
async def get_my_tenant(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_current_tenant(db, principal.tenant_id)


@router.patch("/me")
async def patch_my_tenant(
    payload: schemas.TenantPatch,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_current_tenant(
        db,
        principal.tenant_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/me/driver-despacho-table")
async def get_my_driver_despacho_table(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_driver_despacho_table(db, principal.tenant_id)


@router.put("/me/driver-despacho-table")
async def put_my_driver_despacho_table(
    payload: schemas.DriverDespachoTableUpdate,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.put_driver_despacho_table(
        db,
        principal.tenant_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/me/limits")
async def get_tenant_limits(
    request: Request,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """GET /api/v1/tenants/me/limits — returns usage vs plan limits for the authenticated tenant.

    Uses Redis cache (TTL 30s) per D-15 to avoid a DB COUNT per request.
    max=null means unlimited (enterprise plan, D-13).
    pct is null when max is null.
    """
    from app.modules.vehicles.service import _get_cached_vehicle_count
    from app.modules.drivers.service import _get_cached_driver_count
    from app.modules.users.service import _get_cached_user_count

    redis = getattr(request.app.state, "redis", None)
    tenant_id = principal.tenant_id

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one()

    vehicle_used = await _get_cached_vehicle_count(db, tenant_id, redis)
    driver_used = await _get_cached_driver_count(db, tenant_id, redis)
    user_used = await _get_cached_user_count(db, tenant_id, redis)

    def _pct(used: int, max_val: int | None) -> float | None:
        if max_val is None:
            return None
        return round(used / max_val * 100, 1) if max_val > 0 else None

    return {
        "vehicles": {
            "used": vehicle_used,
            "max": tenant.max_vehicles,
            "pct": _pct(vehicle_used, tenant.max_vehicles),
        },
        "drivers": {
            "used": driver_used,
            "max": tenant.max_drivers,
            "pct": _pct(driver_used, tenant.max_drivers),
        },
        "users": {
            "used": user_used,
            "max": tenant.max_users,
            "pct": _pct(user_used, tenant.max_users),
        },
        "upgrade_url": get_settings().upgrade_url,
    }
