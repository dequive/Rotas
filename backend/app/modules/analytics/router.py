"""Analytics router — RPT-01 (KPIs) and RPT-02 (document expiry)."""
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.permissions import DASHBOARD_ROLES, require_roles
from app.core.deps import get_session
from app.modules.analytics import service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpis")
async def get_kpis(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    period_start: datetime = Query(..., description="Period start (ISO 8601)"),
    period_end: datetime = Query(..., description="Period end (ISO 8601)"),
    vehicle_id: UUID | None = Query(None),
    driver_id: UUID | None = Query(None),
) -> dict:
    """RPT-01: Fleet KPI aggregations for the authenticated tenant."""
    return await service.get_fleet_kpis(
        db,
        principal.tenant_id,
        period_start=period_start,
        period_end=period_end,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
    )


@router.get("/document-expiry")
async def get_document_expiry(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    horizon_days: int = Query(30, ge=7, le=90),
) -> list:
    """RPT-02: Vehicles and drivers with documents expiring within horizon_days."""
    return await service.get_document_expiry_alerts(
        db, principal.tenant_id, horizon_days=horizon_days
    )
