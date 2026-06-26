"""Platform management router (Phase 25 — Plan 02).

8 endpoints for platform operators to manage tenants and platform users.
All endpoints are guarded by require_platform_role() — tenant JWTs are rejected
at the scope check before any route logic runs.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.cache import invalidate_tenant_caches
from app.core.rbac import (
    PLATFORM_ADMIN,
    PLATFORM_BILLING,
    PLATFORM_SUPPORT,
    require_platform_role,
)
from app.database import get_session_raw as get_session
from app.modules.platform import service
from app.modules.platform.schemas import PlatformChangePlanRequest, PlatformCreateUserRequest

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/tenants")
async def list_tenants(
    principal: Annotated[
        Principal,
        Depends(require_platform_role(PLATFORM_ADMIN, PLATFORM_SUPPORT, PLATFORM_BILLING)),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """List all tenants. Accessible by all platform roles."""
    return await service.list_tenants(db, actor_id=principal.user_id, actor_role=principal.role)


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: UUID,
    principal: Annotated[
        Principal,
        Depends(require_platform_role(PLATFORM_ADMIN, PLATFORM_SUPPORT, PLATFORM_BILLING)),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Get tenant detail. platform_support reads are logged to platform_audit_logs."""
    return await service.get_tenant_detail(
        db, tenant_id, actor_id=principal.user_id, actor_role=principal.role
    )


@router.patch("/tenants/{tenant_id}/plan")
async def change_plan(
    request: Request,
    tenant_id: UUID,
    payload: PlatformChangePlanRequest,
    principal: Annotated[Principal, Depends(require_platform_role(PLATFORM_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Change tenant subscription plan. platform_admin only."""
    res = await service.change_tenant_plan(db, tenant_id, payload.plan, actor=principal)
    redis = getattr(request.app.state, "redis", None)
    await invalidate_tenant_caches(redis, tenant_id)
    return res


@router.post("/tenants/{tenant_id}/suspend")
async def suspend_tenant(
    request: Request,
    tenant_id: UUID,
    principal: Annotated[Principal, Depends(require_platform_role(PLATFORM_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Suspend a tenant (set is_active=False). platform_admin only."""
    res = await service.suspend_tenant(db, tenant_id, actor=principal)
    redis = getattr(request.app.state, "redis", None)
    await invalidate_tenant_caches(redis, tenant_id)
    return res


@router.post("/tenants/{tenant_id}/reactivate")
async def reactivate_tenant(
    request: Request,
    tenant_id: UUID,
    principal: Annotated[Principal, Depends(require_platform_role(PLATFORM_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Reactivate a suspended tenant (set is_active=True). platform_admin only."""
    res = await service.reactivate_tenant(db, tenant_id, actor=principal)
    redis = getattr(request.app.state, "redis", None)
    await invalidate_tenant_caches(redis, tenant_id)
    return res


@router.get("/tenants/{tenant_id}/audit-log")
async def get_audit_log(
    tenant_id: UUID,
    principal: Annotated[
        Principal,
        Depends(require_platform_role(PLATFORM_ADMIN, PLATFORM_SUPPORT)),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List platform audit log entries for a tenant. admin and support only."""
    return await service.list_platform_audit_log(db, tenant_id, limit=limit, offset=offset)


@router.get("/platform-users")
async def list_platform_users(
    principal: Annotated[Principal, Depends(require_platform_role(PLATFORM_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    """List all platform users. platform_admin only."""
    return await service.list_platform_users(db)


@router.post("/platform-users", status_code=201)
async def create_platform_user(
    payload: PlatformCreateUserRequest,
    principal: Annotated[Principal, Depends(require_platform_role(PLATFORM_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Create a new platform user. platform_admin only."""
    return await service.create_platform_user(
        db, payload.email, payload.role, payload.password, actor=principal
    )
