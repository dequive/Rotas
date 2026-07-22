from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import Principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.rbac import ADMIN_USERS, require_own_tenant_or_platform, require_permission
from app.database import AsyncSessionLocal, set_rls_tenant
from app.modules.tenants import schemas, service
from app.modules.tenants.models import Tenant
from app.modules.tenants.schemas import TenantDocumentProfileUpdate

router = APIRouter(prefix="/tenants", tags=["tenants"])

# Reusable Query annotation for the optional ?tenant_id= param used by platform_admin.
_TargetTenantId = Annotated[UUID | None, Query(alias="tenant_id")]

# Singleton guard instance — reused across all combined-guard routes so FastAPI's dependency
# deduplication cache treats them as the same dependency within a single request.
_combined_guard = require_own_tenant_or_platform()


async def _open_session_for_principal(principal: Principal) -> AsyncSession:
    """Open an AsyncSession with the appropriate RLS context for the principal.

    - platform scope: no RLS injection (tenant_id is None on the principal; the effective
      tenant is resolved in the route handler via ?tenant_id= query param).
    - dashboard scope: sets RLS context using principal.tenant_id, matching the behaviour
      of app.core.deps.get_session without calling get_current_principal() a second time.

    This is a helper, not a FastAPI Depends — it is called directly by each route after
    receiving the principal from the shared _combined_guard dependency.
    """
    if principal.scope == "platform":
        return AsyncSessionLocal()
    set_rls_tenant(str(principal.tenant_id))
    return AsyncSessionLocal()


def _resolve_tenant_id(principal: Principal, target_tenant_id: UUID | None) -> UUID:
    """Return the effective tenant_id for a combined-guard endpoint.

    - platform scope: uses the ?tenant_id= query param (required).
    - dashboard scope: uses principal.tenant_id (own tenant only).
    """
    if principal.scope == "platform":
        if target_tenant_id is None:
            raise ApiError(
                "tenant_id_required",
                "Platform admin must provide ?tenant_id= query param for this endpoint.",
                status_code=400,
            )
        return target_tenant_id
    return principal.tenant_id  # type: ignore[return-value]


@router.get("/me")
async def get_my_tenant(
    principal: Annotated[Principal, Depends(_combined_guard)],
    target_tenant_id: _TargetTenantId = None,
):
    effective_tenant_id = _resolve_tenant_id(principal, target_tenant_id)
    if principal.scope != "platform":
        set_rls_tenant(str(effective_tenant_id))
    try:
        async with AsyncSessionLocal() as db:
            return await service.get_current_tenant(db, effective_tenant_id)
    finally:
        if principal.scope != "platform":
            set_rls_tenant(None)


@router.patch("/me")
async def patch_my_tenant(
    payload: schemas.TenantPatch,
    principal: Annotated[Principal, Depends(_combined_guard)],
    target_tenant_id: _TargetTenantId = None,
):
    effective_tenant_id = _resolve_tenant_id(principal, target_tenant_id)
    actor_id = principal.user_id if principal.scope != "platform" else None
    if principal.scope != "platform":
        set_rls_tenant(str(effective_tenant_id))
    try:
        async with AsyncSessionLocal() as db:
            return await service.patch_current_tenant(
                db,
                effective_tenant_id,
                payload,
                actor_id=actor_id,
            )
    finally:
        if principal.scope != "platform":
            set_rls_tenant(None)


@router.get("/me/driver-despacho-table")
async def get_my_driver_despacho_table(
    principal: Annotated[Principal, Depends(_combined_guard)],
    target_tenant_id: _TargetTenantId = None,
):
    effective_tenant_id = _resolve_tenant_id(principal, target_tenant_id)
    if principal.scope != "platform":
        set_rls_tenant(str(effective_tenant_id))
    try:
        async with AsyncSessionLocal() as db:
            return await service.get_driver_despacho_table(db, effective_tenant_id)
    finally:
        if principal.scope != "platform":
            set_rls_tenant(None)


@router.put("/me/driver-despacho-table")
async def put_my_driver_despacho_table(
    payload: schemas.DriverDespachoTableUpdate,
    principal: Annotated[Principal, Depends(_combined_guard)],
    target_tenant_id: _TargetTenantId = None,
):
    effective_tenant_id = _resolve_tenant_id(principal, target_tenant_id)
    actor_id = principal.user_id if principal.scope != "platform" else None
    if principal.scope != "platform":
        set_rls_tenant(str(effective_tenant_id))
    try:
        async with AsyncSessionLocal() as db:
            return await service.put_driver_despacho_table(
                db,
                effective_tenant_id,
                payload,
                actor_id=actor_id,
            )
    finally:
        if principal.scope != "platform":
            set_rls_tenant(None)


@router.get("/me/document-profile")
async def get_my_document_profile(
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    result = await service.get_document_profile(db, principal.tenant_id)
    return result or {}


@router.put("/me/document-profile")
async def put_my_document_profile(
    payload: TenantDocumentProfileUpdate,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    data = payload.model_dump(exclude_unset=True)
    return await service.upsert_document_profile(
        db, principal.tenant_id, data, actor_id=principal.user_id
    )


@router.get("/me/limits")
async def get_tenant_limits(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """GET /api/v1/tenants/me/limits — returns usage vs plan limits for the authenticated tenant.

    Uses Redis cache (TTL 30s) per D-15 to avoid a DB COUNT per request.
    max=null means unlimited (enterprise plan, D-13).
    pct is null when max is null.
    """
    from app.modules.drivers.service import _get_cached_driver_count
    from app.modules.users.service import _get_cached_user_count
    from app.modules.vehicles.service import _get_cached_vehicle_count

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


@router.patch("/me/modules")
async def update_my_product_modules(
    payload: schemas.ProductModulesUpdate,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """PATCH /api/v1/tenants/me/modules — update active product modules (tms, oficina) for tenant."""
    return await service.update_product_modules(
        db, principal.tenant_id, payload.product_modules, actor_id=principal.user_id
    )
