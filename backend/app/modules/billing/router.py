from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import ADMIN_ROLES, DASHBOARD_ROLES, WRITE_ROLES, require_roles
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
        raise ApiError(
            "redis_unavailable", "Export service temporarily unavailable.", status_code=503
        )
    return await service.enqueue_export_job(
        db, principal.tenant_id, document_id, export_format, arq_redis
    )


@router.get("/compliance-report", status_code=202)
async def get_compliance_report(
    month: str,
    request: Request,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """FISC-03: Enqueue monthly compliance XLSX export for AT submission.

    Returns ExportJob ID for polling via GET /billing/jobs/{job_id}/status
    Query param: ?month=YYYY-MM (e.g. ?month=2026-01)
    """
    arq_redis = getattr(request.app.state, "arq_redis", None)
    if arq_redis is None:
        raise ApiError(
            "redis_unavailable", "Export service temporarily unavailable.", status_code=503
        )
    return await service.create_compliance_report_job(
        db=db,
        tenant_id=principal.tenant_id,
        month=month,
        arq=arq_redis,
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
    from sqlalchemy import select as sa_select

    from app.modules.billing.models import ExportJob

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


# ── SM-01: BillingDocument state machine endpoints ───────────────────────────


@router.patch("/documents/{document_id}/mark-paid", summary="Mark billing document as paid (SM-01)")
async def mark_billing_document_paid(
    document_id: UUID,
    payload: schemas.BillingDocumentMarkPaidRequest,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """SM-01: Transition BillingDocument from 'issued' or 'overdue' to 'paid'.
    Returns HTTP 409 if the current status does not allow the transition.
    """
    doc = await service.mark_billing_document_paid(
        db,
        document_id=document_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        paid_at=payload.paid_at,
    )
    await db.commit()
    await db.refresh(doc)
    return {"id": doc.id, "status": doc.status, "paid_at": doc.paid_at}


@router.patch("/documents/{document_id}/cancel", summary="Cancel billing document (SM-01)")
async def cancel_billing_document(
    document_id: UUID,
    payload: schemas.BillingDocumentCancelRequest,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """SM-01: Transition BillingDocument to 'cancelled'. Requires cancellation_reason.
    Allowed from 'draft' or 'overdue'. Returns HTTP 409 for invalid transitions.
    """
    doc = await service.cancel_billing_document(
        db,
        document_id=document_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        reason=payload.cancellation_reason,
    )
    await db.commit()
    await db.refresh(doc)
    return {"id": doc.id, "status": doc.status, "cancellation_reason": doc.cancellation_reason}


# ── FDOC-02: Nota de Débito ───────────────────────────────────────────────────


@router.post("/documents/{document_id}/debit-note", status_code=201)
async def create_debit_note(
    document_id: UUID,
    payload: schemas.CreateDebitNoteRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """FDOC-02: Create a Nota de Débito against an issued invoice. Returns the new document."""
    return await service.create_debit_note(
        db,
        tenant_id=principal.tenant_id,
        parent_id=document_id,
        amount=payload.amount,
        reason=payload.reason,
        iva_rate=payload.iva_rate,
    )


# ── FDOC-03: Nota de Crédito ──────────────────────────────────────────────────


@router.post("/documents/{document_id}/credit-note", status_code=201)
async def create_credit_note(
    document_id: UUID,
    payload: schemas.CreateCreditNoteRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """FDOC-03: Create a Nota de Crédito against an issued invoice. Returns the new document."""
    return await service.create_credit_note(
        db,
        tenant_id=principal.tenant_id,
        parent_id=document_id,
        amount=payload.amount,
        reason=payload.reason,
        iva_rate=payload.iva_rate,
    )


# ── FDOC-04: Fatura-Recibo + Recibo ──────────────────────────────────────────


@router.post("/documents/{document_id}/invoice-receipt", status_code=201)
async def create_invoice_receipt(
    document_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """FDOC-04: Transition parent invoice to paid and create a Fatura-Recibo."""
    return await service.create_invoice_receipt(
        db,
        tenant_id=principal.tenant_id,
        parent_id=document_id,
    )


@router.post("/documents/{document_id}/receipt", status_code=201)
async def create_receipt(
    document_id: UUID,
    payload: schemas.CreateReceiptRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """FDOC-04: Create a standalone Recibo for a partial or out-of-band payment."""
    return await service.create_receipt(
        db,
        tenant_id=principal.tenant_id,
        parent_id=document_id,
        amount_paid=payload.amount_paid,
    )


# ── FDOC-05: AR Básico ────────────────────────────────────────────────────────


# ── PAY-01/02/03: Client Payments ────────────────────────────────────────────


@router.post("/payments", status_code=201)
async def register_payment(
    payload: schemas.ClientPaymentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Register a client payment (full, partial, or advance).

    Requires Idempotency-Key header to prevent double-registration.
    If billing_document_id is None, creates an advance payment with no allocation.
    """
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="billing.payment.register",
        entity_type="client_payment",
        payload=payload,
        handler=lambda: service.register_payment(
            db, principal.tenant_id, principal.user_id, payload
        ),
    )


@router.post("/payments/{payment_id}/void")
async def void_payment(
    payment_id: UUID,
    payload: schemas.VoidPaymentRequest,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Void a confirmed payment. Only owner/admin can void payments.

    Sets status='voided', reverses billing_document paid_at if applicable.
    Payments are never hard-deleted — financial audit trail preserved.
    """
    return await service.void_payment(
        db,
        payment_id=payment_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        void_reason=payload.void_reason,
    )


@router.post("/payments/{payment_id}/apply", status_code=201)
async def apply_advance_to_invoice(
    payment_id: UUID,
    payload: schemas.ApplyAdvanceRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Apply an existing advance payment to a specific invoice.

    Creates a PaymentAllocation row. Verifies advance has not been over-applied.
    """
    return await service.apply_advance_to_invoice(
        db,
        payment_id=payment_id,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        billing_document_id=payload.billing_document_id,
        amount_applied=payload.amount_applied,
    )


@router.get("/ar")
async def list_ar_documents(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    aging_bucket: Annotated[
        str | None, Query(description="current | 1_30 | 31_60 | 61_90 | over_90")
    ] = None,
    contract_id: Annotated[UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """FDOC-05: List issued invoices with due_date set, ordered by due_date ASC.

    Returns days_overdue and aging_bucket for each document.
    Filter by aging_bucket to get documents in a specific AR aging band.
    """
    return await service.list_ar_documents(
        db,
        tenant_id=principal.tenant_id,
        aging_bucket=aging_bucket,
        contract_id=contract_id,
        limit=limit,
        offset=offset,
    )
