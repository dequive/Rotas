from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import ADMIN_USERS, require_permission
from app.modules.users import schemas, service
from app.modules.users.models import TenantRole  # noqa: F401 — ensure ORM registered

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_users(db, principal.tenant_id, limit=limit, offset=offset)


@router.post("")
async def create_user(
    request: Request,
    payload: schemas.UserCreate,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    redis = getattr(request.app.state, "redis", None)
    res = await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="users.create",
        entity_type="user",
        payload=payload,
        handler=lambda: service.create_user(
            db, principal.tenant_id, payload, actor_id=principal.user_id, redis=redis
        ),
    )
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


@router.patch("/{user_id}")
async def patch_user(
    request: Request,
    user_id: UUID,
    payload: schemas.UserPatch,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.patch_user(
        db,
        principal.tenant_id,
        user_id,
        payload,
        actor_id=principal.user_id,
    )
    redis = getattr(request.app.state, "redis", None)
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res


# ── Tenant role endpoints ─────────────────────────────────────────────────────


@router.get("/tenant-roles")
async def list_tenant_roles_endpoint(
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict]:
    return await service.list_tenant_roles(db, principal.tenant_id)


@router.post("/tenant-roles", status_code=201)
async def create_tenant_role_endpoint(
    payload: schemas.TenantRoleCreate,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    return await service.create_tenant_role(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.patch("/tenant-roles/{role_id}")
async def update_tenant_role_endpoint(
    role_id: UUID,
    payload: schemas.TenantRoleUpdate,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    return await service.update_tenant_role(db, principal.tenant_id, role_id, payload)


@router.post("/{user_id}/role")
async def assign_custom_role_endpoint(
    request: Request,
    user_id: UUID,
    payload: schemas.AssignCustomRoleRequest,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    res = await service.assign_custom_role_to_user(
        db,
        principal.tenant_id,
        user_id,
        custom_role_id=payload.custom_role_id,
        actor_id=principal.user_id,
    )
    redis = getattr(request.app.state, "redis", None)
    await invalidate_tenant_caches(redis, principal.tenant_id)
    return res
