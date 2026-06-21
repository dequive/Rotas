from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, FLEET_WRITE, require_permission
from app.modules.notifications import service
from app.modules.notifications.schemas import EmailNotificationCreate

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/email", status_code=201)
async def enqueue_email_endpoint(
    payload: EmailNotificationCreate,
    principal: Annotated[Principal, Depends(require_permission(FLEET_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    result = await service.enqueue_email(db, principal.tenant_id, payload, actor_id=principal.user_id)
    await db.commit()
    return result


@router.get("")
async def list_notifications(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    channel: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_notifications(
        db, principal.tenant_id, status=status, channel=channel, limit=limit, offset=offset
    )


@router.get("/{notification_id}")
async def get_notification(
    notification_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_notification(db, principal.tenant_id, notification_id)
