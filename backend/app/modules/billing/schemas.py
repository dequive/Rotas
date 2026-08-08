import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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
