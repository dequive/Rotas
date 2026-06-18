from datetime import datetime
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


class IssueBillingDocumentRequest(BaseModel):
    issued_at: datetime | None = None


class CreateBillingWaiver(BaseModel):
    trip_id: UUID
    reason: str = Field(..., min_length=10, description="Justification for the negative margin waiver")


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

