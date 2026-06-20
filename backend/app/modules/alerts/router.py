from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.alerts import schemas, service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    priority: str | None = None,
    alert_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_alerts(
        db,
        principal.tenant_id,
        status_filter=status,
        priority=priority,
        alert_type=alert_type,
        limit=limit,
        offset=offset,
    )


@router.post("")
async def create_alert(
    payload: schemas.AlertCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_alert(db, principal.tenant_id, payload, actor_id=principal.user_id)


@router.patch("/{alert_id}/status")
async def patch_alert_status(
    alert_id: UUID,
    payload: schemas.AlertStatusPatch,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_alert_status(
        db,
        principal.tenant_id,
        alert_id,
        payload,
        actor_id=principal.user_id,
    )
