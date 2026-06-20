from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import ADMIN_USERS, TRIPS_DISPATCH, TRIPS_READ, require_permission
from app.modules.trips import known_routes_service as svc

router = APIRouter(prefix="/known-routes", tags=["known-routes"])


@router.get("")
async def list_routes(
    principal: Annotated[Principal, Depends(require_permission(TRIPS_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    active_only: bool = True,
):
    return await svc.list_known_routes(db, principal.tenant_id, active_only=active_only)


@router.post("", status_code=201)
async def create_route(
    payload: dict,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await svc.create_known_route(db, principal.tenant_id, payload)


@router.patch("/{route_id}")
async def update_route(
    route_id: UUID,
    payload: dict,
    principal: Annotated[Principal, Depends(require_permission(TRIPS_DISPATCH))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await svc.update_known_route(db, principal.tenant_id, route_id, payload)


@router.delete("/{route_id}")
async def delete_route(
    route_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await svc.delete_known_route(db, principal.tenant_id, route_id)
