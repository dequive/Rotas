import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_nuit(v: str | None) -> str | None:
    if v is None:
        return v
    if not v.strip():
        return None
    cleaned = re.sub(r"\D", "", v)
    if len(cleaned) != 9:
        raise ValueError("NUIT must be exactly 9 digits.")
    return cleaned



class BillingDocumentCreate(BaseModel):
    contract_id: UUID | None = None
    client_name: str
    contract_reference: str | None = None
    billing_period_start: datetime
    billing_period_end: datetime
    currency: str = "MZN"
    trip_ids: list[UUID] = Field(default_factory=list)
    client_nuit: str | None = None

    @field_validator("client_nuit")
    @classmethod
    def validate_nuit(cls, v: str | None) -> str | None:
        return _normalize_nuit(v)

    @model_validator(mode="after")
    def validate_periods(self) -> "BillingDocumentCreate":
        if self.billing_period_end <= self.billing_period_start:
            raise ValueError("billing_period_end must be after billing_period_start.")
        return self


class IssueBillingDocumentRequest(BaseModel):
    issued_at: datetime | None = None


class CreateBillingWaiver(BaseModel):
    trip_id: UUID
    reason: str = Field(
        ..., min_length=10, description="Justification for the negative margin waiver"
    )


class BillingWaiverResponse(BaseModel):
    id: UUID
    trip_id: UUID
    status: str
    reason: str
    approved_by: UUID | None
    created_at: datetime


# SM-01: BillingDocument state machine request schemas
class BillingDocumentMarkPaidRequest(BaseModel):
    paid_at: datetime | None = None


class BillingDocumentCancelRequest(BaseModel):
    cancellation_reason: str = Field(..., min_length=5, max_length=500)


# FDOC-02: Nota de Débito
class CreateDebitNoteRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Additional charge amount (pre-IVA)")
    reason: str = Field(..., min_length=5, max_length=500)
    iva_rate: Decimal = Field(Decimal("0.1600"), ge=0, le=1)


# FDOC-03: Nota de Crédito
class CreateCreditNoteRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Credit amount (pre-IVA)")
    reason: str = Field(..., min_length=5, max_length=500)
    iva_rate: Decimal = Field(Decimal("0.1600"), ge=0, le=1)


# FDOC-04: Recibo (standalone)
class CreateReceiptRequest(BaseModel):
    amount_paid: Decimal = Field(..., gt=0, description="Amount received")


# ── Phase 6: Payment Registration Schemas ─────────────────────────────────────


class ClientPaymentCreate(BaseModel):
    client_id: UUID
    billing_document_id: UUID | None = None  # None = advance payment
    amount: Decimal = Field(..., gt=0, description="Payment amount (must be > 0)")
    currency: Annotated[str, Field(max_length=3)] = "MZN"
    value_date: datetime
    payment_method: str = Field(
        ...,
        pattern="^(bank_transfer|cheque|cash)$",
        description="bank_transfer | cheque | cash",
    )
    reference: Annotated[str, Field(max_length=120)] | None = None
    notes: str | None = None


class VoidPaymentRequest(BaseModel):
    void_reason: str = Field(..., min_length=5, max_length=500)


class ApplyAdvanceRequest(BaseModel):
    billing_document_id: UUID
    amount_applied: Decimal = Field(..., gt=0)


# ── Response contracts (F7.2) ─────────────────────────────────────────────────
# Every response model below mirrors the corresponding `service.serialize_*`
# helper so the OpenAPI contract exposes a non-empty 2xx schema.


class BillingWaiverDecisionResponse(BaseModel):
    id: UUID
    status: str
    approved_by: UUID | None = None


class BillableTripResponse(BaseModel):
    trip_id: UUID
    vehicle_id: UUID | None = None
    vehicle_plate: str | None = None
    contract_id: UUID | None = None
    contract_reference: str | None = None
    client_name: str | None = None
    origin: str | None = None
    destination: str | None = None
    cargo_type: str | None = None
    cargo_class: str | None = None
    load_state: str | None = None
    delivered_at: datetime | None = None
    delivery_proof_id: UUID | None = None
    delivery_proof_status: str | None = None
    billing_status: str | None = None
    candidate_status: str
    amount: Decimal | None = None
    waiver_status: str | None = None


class BillingItemResponse(BaseModel):
    id: UUID
    contract_id: UUID | None = None
    billing_document_id: UUID
    trip_id: UUID | None = None
    load_permit_id: UUID | None = None
    cargo_manifest_id: UUID | None = None
    transport_document_id: UUID | None = None
    delivery_proof_id: UUID | None = None
    client_reference: str | None = None
    origin: str | None = None
    destination: str | None = None
    district: str | None = None
    cargo_description: str | None = None
    cargo_class: str | None = None
    load_state: str | None = None
    loaded_at: datetime | None = None
    delivered_at: datetime
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    status: str
    created_at: datetime


class BillingDocumentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    contract_id: UUID | None = None
    client_name: str
    contract_reference: str | None = None
    billing_period_start: datetime
    billing_period_end: datetime
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    issued_at: datetime | None = None
    paid_at: datetime | None = None
    due_date: datetime | None = None
    file_id: UUID | None = None
    invoice_number: str | None = None
    iva_rate: Decimal | None = None
    document_type: str
    parent_document_id: UUID | None = None
    client_nuit: str | None = None
    items: list[BillingItemResponse] = Field(default_factory=list)


class BillingDocumentSummaryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    contract_id: UUID | None = None
    client_id: UUID | None = None
    client_name: str
    contract_reference: str | None = None
    billing_period_start: datetime
    billing_period_end: datetime
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    issued_at: datetime | None = None
    paid_at: datetime | None = None
    due_date: datetime | None = None
    file_id: UUID | None = None
    invoice_number: str | None = None
    document_type: str
    item_count: int
    created_at: datetime


class BillingDocumentListResponse(BaseModel):
    items: list[BillingDocumentSummaryResponse]
    total: int


class BillingDocumentStatusResponse(BaseModel):
    id: UUID
    status: str
    paid_at: datetime | None = None


class BillingDocumentCancelledResponse(BaseModel):
    id: UUID
    status: str
    cancellation_reason: str | None = None


class AdjustmentNoteResponse(BaseModel):
    """FDOC-02/03: Nota de Débito and Nota de Crédito issued against an invoice."""

    id: UUID
    invoice_number: str | None = None
    document_type: str
    parent_document_id: UUID | None = None
    parent_invoice_number: str | None = None
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: str
    issued_at: datetime | None = None


class InvoiceReceiptResponse(BaseModel):
    """FDOC-04: Fatura-Recibo created from a settled invoice."""

    id: UUID
    invoice_number: str | None = None
    document_type: str
    parent_document_id: UUID | None = None
    parent_invoice_number: str | None = None
    parent_status: str
    total_amount: Decimal
    status: str
    issued_at: datetime | None = None


class ReceiptResponse(BaseModel):
    """FDOC-04: standalone Recibo for a partial or out-of-band payment."""

    id: UUID
    invoice_number: str | None = None
    document_type: str
    parent_document_id: UUID | None = None
    parent_invoice_number: str | None = None
    amount_paid: Decimal
    status: str
    issued_at: datetime | None = None


class BillingDocumentExportResponse(BaseModel):
    billing_document_id: UUID
    export_format: str
    file_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    sha256_hash: str
    status: str
    download_url: str
    message: str


class ExportJobEnqueuedResponse(BaseModel):
    job_id: UUID
    status: str


class ExportJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    job_type: str


class ArSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    current: Decimal
    bucket_1_30: Decimal = Field(alias="1_30")
    bucket_31_60: Decimal = Field(alias="31_60")
    bucket_61_90: Decimal = Field(alias="61_90")
    over_90: Decimal
    total_ar: Decimal
    currency: str
    as_of: str


class TopDebtorResponse(BaseModel):
    client_id: UUID
    client_name: str
    outstanding: Decimal
    worst_bucket: str


class ClientStatementDocumentResponse(BaseModel):
    id: UUID
    invoice_number: str | None = None
    document_type: str
    status: str
    total_amount: Decimal
    currency: str
    issued_at: datetime | None = None
    due_date: datetime | None = None
    amount_paid: Decimal
    outstanding: Decimal


class ClientStatementResponse(BaseModel):
    client_id: UUID
    client_name: str
    total_invoiced: Decimal
    total_paid: Decimal
    balance: Decimal
    currency: str
    documents: list[ClientStatementDocumentResponse]
    as_of: str | None = None


class PaymentAllocationResponse(BaseModel):
    id: UUID
    billing_document_id: UUID
    amount_applied: Decimal
    created_at: datetime


class ClientPaymentResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    client_id: UUID
    billing_document_id: UUID | None = None
    amount: Decimal
    currency: str
    value_date: datetime
    payment_method: str
    reference: str | None = None
    notes: str | None = None
    status: str
    voided_at: datetime | None = None
    voided_by: UUID | None = None
    void_reason: str | None = None
    created_by: UUID | None = None
    created_at: datetime
    allocations: list[PaymentAllocationResponse] = Field(default_factory=list)


class ClientPaymentListResponse(BaseModel):
    items: list[ClientPaymentResponse]
    total: int
