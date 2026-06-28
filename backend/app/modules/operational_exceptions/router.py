from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.rbac import TRIPS_CLOSE, TRIPS_READ, require_permission
from app.modules.operational_exceptions import service
from app.modules.operational_exceptions.schemas import ResolveExceptionRequest

router = APIRouter(prefix="/operational-exceptions", tags=["operational-exceptions"])


@router.get("")
async def list_exceptions(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
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
    request: Request,
    exception_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_CLOSE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.acknowledge_exception(
        db, principal.tenant_id, exception_id, actor_id=principal.user_id
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.post("/{exception_id}/resolve")
async def resolve_exception(
    request: Request,
    exception_id: UUID,
    payload: ResolveExceptionRequest,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_CLOSE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.resolve_exception(
        db,
        principal.tenant_id,
        exception_id,
        resolution_notes=payload.resolution_notes,
        actor_id=principal.user_id,
    )
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res
