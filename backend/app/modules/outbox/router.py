from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal
from app.core.deps import get_session
from app.core.rbac import OUTBOX_READ, OUTBOX_REPLAY, require_permission
from app.modules.outbox import operations
from app.modules.outbox.schemas import OutboxReplayRequest

router = APIRouter(prefix="/outbox-events", tags=["outbox-operations"])


@router.get("")
async def list_outbox_events(
    principal: Annotated[TenantPrincipal, Depends(require_permission(OUTBOX_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status_filter: str | None = Query(None, alias="status"),
    event_type: str | None = None,
    aggregate_type: str | None = None,
    correlation_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await operations.list_outbox_events(
        db,
        principal.tenant_id,
        status_filter=status_filter,
        event_type=event_type,
        aggregate_type=aggregate_type,
        correlation_id=correlation_id,
        limit=limit,
        offset=offset,
    )


@router.get("/reconciliation")
async def get_outbox_reconciliation(
    principal: Annotated[TenantPrincipal, Depends(require_permission(OUTBOX_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.get_outbox_reconciliation(db, principal.tenant_id)


@router.get("/{event_id}")
async def get_outbox_event(
    event_id: UUID,
    principal: Annotated[TenantPrincipal, Depends(require_permission(OUTBOX_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.get_outbox_event(db, principal.tenant_id, event_id)


@router.post("/{event_id}/replay")
async def replay_dead_letter(
    event_id: UUID,
    payload: OutboxReplayRequest,
    principal: Annotated[TenantPrincipal, Depends(require_permission(OUTBOX_REPLAY))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.replay_dead_letter(
        db,
        principal.tenant_id,
        event_id,
        reason=payload.reason,
        actor_id=principal.user_id,
    )
