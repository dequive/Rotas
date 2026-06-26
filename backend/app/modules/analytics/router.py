"""Analytics router — RPT-01 (KPIs), RPT-02 (document expiry), ANA-02/03 (exports)."""

import json
import uuid as _uuid
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import FLEET_READ, require_permission
from app.modules.analytics import service
from app.modules.billing.models import ExportJob

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/kpis")
async def get_kpis(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    period_start: Annotated[datetime, Query(description="Period start (ISO 8601)")],
    period_end: Annotated[datetime, Query(description="Period end (ISO 8601)")],
    vehicle_id: Annotated[UUID | None, Query()] = None,
    driver_id: Annotated[UUID | None, Query()] = None,
) -> dict:
    """RPT-01: Fleet KPI aggregations for the authenticated tenant."""
    redis = getattr(request.app.state, "redis", None)
    cache_key = (
        f"tenant:{principal.tenant_id}:analytics:kpis"
        f":start={period_start.isoformat()}:end={period_end.isoformat()}"
        f":vehicle={vehicle_id}:driver={driver_id}"
    )
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

    result = await service.get_fleet_kpis(
        db,
        principal.tenant_id,
        period_start=period_start,
        period_end=period_end,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
    )

    if redis is not None:
        await redis.setex(cache_key, 60, json.dumps(result, default=str))
    return result


@router.get("/document-expiry")
async def get_document_expiry(
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    horizon_days: int = Query(30, ge=7, le=90),
) -> list:
    """RPT-02: Vehicles and drivers with documents expiring within horizon_days."""
    return await service.get_document_expiry_alerts(
        db, principal.tenant_id, horizon_days=horizon_days
    )


@router.get("/dashboard")
async def get_dashboard(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    period_start: Annotated[datetime, Query(description="Period start (ISO 8601)")],
    period_end: Annotated[datetime, Query(description="Period end (ISO 8601)")],
) -> dict:
    """ANA-01: Extended analytics dashboard with Redis cache (TTL 300s)."""
    redis = getattr(request.app.state, "redis", None)
    return await service.get_analytics_dashboard(
        db, principal.tenant_id, period_start, period_end, redis=redis
    )


@router.get("/fuel-report")
async def trigger_fuel_report(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    month: Annotated[str, Query(description="Month YYYY-MM", pattern=r"^\d{4}-\d{2}$")],
) -> JSONResponse:
    """ANA-02: Enqueue fuel XLSX export job. Returns 202 with job_id.

    Idempotent: a queued or processing job for the same tenant+month is returned
    immediately without creating a duplicate.
    """
    existing = await db.scalar(
        select(ExportJob).where(
            ExportJob.tenant_id == principal.tenant_id,
            ExportJob.job_type == "analytics_fuel_xlsx",
            ExportJob.status.in_(["queued", "processing"]),
        )
    )
    if existing:
        return JSONResponse(
            {"job_id": str(existing.id), "status": existing.status}, status_code=202
        )

    job = ExportJob(
        id=_uuid.uuid4(),
        tenant_id=principal.tenant_id,
        job_type="analytics_fuel_xlsx",
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    arq_redis = getattr(request.app.state, "arq_redis", None)
    if arq_redis:
        await arq_redis.enqueue_job(
            "task_export_fuel_report", str(job.id), str(principal.tenant_id), month
        )

    return JSONResponse({"job_id": str(job.id), "status": "queued"}, status_code=202)


@router.get("/compliance-report")
async def trigger_compliance_report(
    request: Request,
    principal: Annotated[Principal, Depends(require_permission(FLEET_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    """ANA-03: Enqueue compliance PDF export job. Returns 202 with job_id.

    Idempotent: a queued or processing job for the same tenant is returned
    immediately without creating a duplicate.
    """
    existing = await db.scalar(
        select(ExportJob).where(
            ExportJob.tenant_id == principal.tenant_id,
            ExportJob.job_type == "analytics_compliance_pdf",
            ExportJob.status.in_(["queued", "processing"]),
        )
    )
    if existing:
        return JSONResponse(
            {"job_id": str(existing.id), "status": existing.status}, status_code=202
        )

    job = ExportJob(
        id=_uuid.uuid4(),
        tenant_id=principal.tenant_id,
        job_type="analytics_compliance_pdf",
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    arq_redis = getattr(request.app.state, "arq_redis", None)
    if arq_redis:
        await arq_redis.enqueue_job(
            "task_export_compliance_report", str(job.id), str(principal.tenant_id)
        )

    return JSONResponse({"job_id": str(job.id), "status": "queued"}, status_code=202)
