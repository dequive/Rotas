from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import ADMIN_ROLES, DASHBOARD_ROLES, require_roles
from app.core.deps import get_session
from app.modules.users import schemas, service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
async def list_users(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_users(db, principal.tenant_id, limit=limit, offset=offset)


@router.post("")
async def create_user(
    payload: schemas.UserCreate,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="users.create",
        entity_type="user",
        payload=payload,
        handler=lambda: service.create_user(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.patch("/{user_id}")
async def patch_user(
    user_id: UUID,
    payload: schemas.UserPatch,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_user(
        db,
        principal.tenant_id,
        user_id,
        payload,
        actor_id=principal.user_id,
    )
