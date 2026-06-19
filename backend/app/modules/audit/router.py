from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.permissions import ADMIN_ROLES, require_roles
from app.modules.audit import service

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("")
async def list_audit_logs(
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    action: str | None = None,
    correlation_id: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_audit_logs(
        db,
        principal.tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        correlation_id=correlation_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
