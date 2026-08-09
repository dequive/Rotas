from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.errors import ApiError
from app.core.rbac import PLATFORM_ADMIN, PLATFORM_SUPPORT, require_platform_role
from app.database import get_session_raw as get_session
from app.modules.outbox import service
from app.modules.outbox.schemas import (
    OutboxHealthResponse,
    OutboxOperationalEvent,
    OutboxReplayRequest,
    OutboxReplayResponse,
)

router = APIRouter(prefix="/platform/outbox", tags=["platform:outbox"])


@router.get("/health", response_model=OutboxHealthResponse)
async def get_outbox_health(
    principal: Annotated[
        Principal,
        Depends(require_platform_role(PLATFORM_ADMIN, PLATFORM_SUPPORT)),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    return await service.outbox_health(db)


@router.get("/dead-letters", response_model=list[OutboxOperationalEvent])
async def get_dead_letters(
    principal: Annotated[
        Principal,
        Depends(require_platform_role(PLATFORM_ADMIN, PLATFORM_SUPPORT)),
    ],
    db: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=200),
) -> list[OutboxOperationalEvent]:
    rows = await service.list_dead_letters(db, tenant_id=tenant_id, limit=limit)
    return [OutboxOperationalEvent.model_validate(row, from_attributes=True) for row in rows]


@router.post("/{event_id}/replay", response_model=OutboxReplayResponse)
async def replay_dead_letter(
    request: Request,
    event_id: UUID,
    payload: OutboxReplayRequest,
    principal: Annotated[Principal, Depends(require_platform_role(PLATFORM_ADMIN))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> OutboxReplayResponse:
    if principal.user_id is None or principal.role is None:
        raise ApiError(
            "platform_actor_required",
            "An authenticated platform actor is required.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    row = await service.replay_dead_letter(
        db,
        event_id=event_id,
        operator_id=principal.user_id,
        operator_role=principal.role,
        reason=payload.reason,
        ip_address=request.client.host if request.client else None,
    )
    return OutboxReplayResponse.model_validate(row, from_attributes=True)
