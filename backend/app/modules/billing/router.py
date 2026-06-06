from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.errors import ApiError
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import ADMIN_ROLES, DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.billing import schemas, service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/billable-trips")
async def list_billable_trips(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    client_name: str | None = None,
    contract_reference: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_billable_trips(
        db,
        principal.tenant_id,
        client_name=client_name,
        contract_reference=contract_reference,
        period_start=period_start,
        period_end=period_end,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.post("/documents")
async def create_document(
    payload: schemas.BillingDocumentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="billing.document.create",
        entity_type="billing_document",
        payload=payload,
        handler=lambda: service.create_document(db, principal.tenant_id, payload),
    )


@router.get("/documents")
async def list_documents(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_documents(
        db,
        principal.tenant_id,
        status_filter=status,
        period_start=period_start,
        period_end=period_end,
        limit=limit,
        offset=offset,
    )


@router.get("/documents/{document_id}")
async def get_document(
    document_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_document(db, principal.tenant_id, document_id)


@router.get("/documents/{document_id}/export")
async def export_document(
    document_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    export_format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
):
    return await service.export_document(
        db,
        principal.tenant_id,
        document_id,
        export_format,
    )


@router.post("/documents/{document_id}/issue")
async def issue_document(
    document_id: UUID,
    payload: schemas.IssueBillingDocumentRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="billing.document.issue",
        entity_type="billing_document",
        payload={"document_id": document_id, **payload.model_dump()},
        handler=lambda: service.issue_document(db, principal.tenant_id, document_id, payload),
    )


@router.post("/waivers", status_code=201)
async def create_waiver(
    payload: schemas.CreateBillingWaiver,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """BILL-03: Create a billing waiver request for a negative-margin trip.
    Available to: manager, admin, owner.
    """
    return await service.create_billing_waiver(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        trip_id=payload.trip_id,
        reason=payload.reason,
    )


@router.post("/waivers/{waiver_id}/approve")
async def approve_waiver(
    waiver_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """BILL-03: Approve a pending billing waiver. Requires owner or admin role."""
    return await service.approve_billing_waiver(
        db,
        tenant_id=principal.tenant_id,
        waiver_id=waiver_id,
        approver_id=principal.user_id,
    )


@router.post("/waivers/{waiver_id}/reject")
async def reject_waiver(
    waiver_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """BILL-03: Reject a pending billing waiver. Requires owner or admin role."""
    return await service.reject_billing_waiver(
        db,
        tenant_id=principal.tenant_id,
        waiver_id=waiver_id,
        rejector_id=principal.user_id,
    )


@router.post("/documents/{document_id}/export-job", status_code=202)
async def create_export_job(
    document_id: UUID,
    request: Request,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    export_format: str = Query("pdf", pattern="^(pdf|xlsx)$"),
):
    """BILL-01/02: Enqueue async export job. Returns job_id for polling.

    export_format query param: ?export_format=pdf (default) or ?export_format=xlsx
    """
    arq_redis = getattr(request.app.state, "arq_redis", None)
    if arq_redis is None:
        raise ApiError("redis_unavailable", "Export service temporarily unavailable.", status_code=503)
    return await service.enqueue_export_job(
        db, principal.tenant_id, document_id, export_format, arq_redis
    )


@router.get("/jobs/{job_id}/status")
async def get_job_status(
    job_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Poll export job status: queued | processing | done | failed."""
    return await service.get_export_job_status(db, principal.tenant_id, job_id)


@router.get("/jobs/{job_id}/download")
async def download_job_file(
    job_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """BILL-01/02: Download completed export file. Tenant-isolated — no public URL."""
    from app.modules.billing.models import ExportJob
    from sqlalchemy import select as sa_select

    job = await db.scalar(
        sa_select(ExportJob).where(
            ExportJob.id == job_id, ExportJob.tenant_id == principal.tenant_id
        )
    )
    if not job:
        raise ApiError("job_not_found", "Export job not found", status_code=404)
    if job.status != "done":
        raise ApiError(
            "job_not_done",
            f"Job status is '{job.status}' — not ready for download.",
            status_code=409,
        )
    if not job.file_path or not Path(job.file_path).exists():
        raise ApiError("file_not_found", "Export file not found on disk.", status_code=404)

    content_type = (
        "application/pdf"
        if job.job_type == "billing_pdf"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return FileResponse(path=job.file_path, media_type=content_type)
