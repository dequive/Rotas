from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.permissions import DASHBOARD_ROLES, require_roles
from app.core.deps import get_session
from app.modules.control_tower import service

router = APIRouter(prefix="/control-tower", tags=["control-tower"])


@router.get("")
async def get_control_tower(
    request: Request,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    date_: Annotated[date | None, Query(alias="date")] = None,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page — max 200"),
):
    redis = getattr(request.app.state, "redis", None)
    return await service.get_ct_cached(
        db,
        principal.tenant_id,
        redis,
        target_date=date_,
        page=page,
        page_size=page_size,
    )
