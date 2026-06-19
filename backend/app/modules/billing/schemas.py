from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BillingDocumentCreate(BaseModel):
    contract_id: UUID | None = None
    client_name: str
    contract_reference: str | None = None
    billing_period_start: datetime
    billing_period_end: datetime
    currency: str = "MZN"
    trip_ids: list[UUID] = Field(default_factory=list)
    client_nuit: str | None = None


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
    iva_rate: Decimal = Field(Decimal("0.1700"), ge=0, le=1)


# FDOC-03: Nota de Crédito
class CreateCreditNoteRequest(BaseModel):
    amount: Decimal = Field(..., gt=0, description="Credit amount (pre-IVA)")
    reason: str = Field(..., min_length=5, max_length=500)
    iva_rate: Decimal = Field(Decimal("0.1700"), ge=0, le=1)


# FDOC-04: Recibo (standalone)
class CreateReceiptRequest(BaseModel):
    amount_paid: Decimal = Field(..., gt=0, description="Amount received")


# ── Phase 6: Payment Registration Schemas ─────────────────────────────────────


class ClientPaymentCreate(BaseModel):
    client_id: UUID
    billing_document_id: UUID | None = None  # None = advance payment
    amount: Decimal = Field(..., gt=0, description="Payment amount (must be > 0)")
    currency: str = Field("MZN", max_length=3)
    value_date: datetime
    payment_method: str = Field(
        ...,
        pattern="^(bank_transfer|cheque|cash)$",
        description="bank_transfer | cheque | cash",
    )
    reference: str | None = Field(None, max_length=120)
    notes: str | None = None


class VoidPaymentRequest(BaseModel):
    void_reason: str = Field(..., min_length=5, max_length=500)


class ApplyAdvanceRequest(BaseModel):
    billing_document_id: UUID
    amount_applied: Decimal = Field(..., gt=0)
