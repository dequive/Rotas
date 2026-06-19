from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.modules.operational_exceptions import service
from app.modules.operational_exceptions.schemas import ResolveExceptionRequest

router = APIRouter(prefix="/operational-exceptions", tags=["operational-exceptions"])


@router.get("")
async def list_exceptions(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    exception_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    return await service.list_exceptions(
        db,
        principal.tenant_id,
        status_filter=status,
        exception_type=exception_type,
        limit=limit,
    )


@router.post("/{exception_id}/acknowledge")
async def acknowledge_exception(
    exception_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.acknowledge_exception(
        db, principal.tenant_id, exception_id, actor_id=principal.user_id
    )


@router.post("/{exception_id}/resolve")
async def resolve_exception(
    exception_id: UUID,
    payload: ResolveExceptionRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.resolve_exception(
        db,
        principal.tenant_id,
        exception_id,
        resolution_notes=payload.resolution_notes,
        actor_id=principal.user_id,
    )
