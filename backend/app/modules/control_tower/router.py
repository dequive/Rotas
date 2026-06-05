from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.permissions import DASHBOARD_ROLES, require_roles
from app.database import get_session
from app.modules.control_tower import service

router = APIRouter(prefix="/control-tower", tags=["control-tower"])


@router.get("")
async def get_control_tower(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    date_: Annotated[date | None, Query(alias="date")] = None,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page — max 200"),
):
    return await service.get_control_tower(
        db,
        principal.tenant_id,
        target_date=date_,
        page=page,
        page_size=page_size,
    )
