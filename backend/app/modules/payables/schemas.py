from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PurchaseOrderCreate(BaseModel):
    third_party_id: UUID
    work_order_id: UUID | None = None
    vehicle_id: UUID | None = None
    trip_id: UUID | None = None
    po_number: str
    description: str
    estimated_amount: Decimal | None = None
    currency: str = "MZN"
    issued_at: datetime


class PurchaseOrderResponse(PurchaseOrderCreate):
    id: UUID
    tenant_id: UUID
    status: str
    approved_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceCreate(BaseModel):
    third_party_id: UUID
    work_order_id: UUID | None = None
    vehicle_id: UUID | None = None
    trip_id: UUID | None = None
    invoice_number: str | None = None
    description: str | None = None
    amount: Decimal
    currency: str = "MZN"
    issued_at: datetime
    due_date: datetime | None = None


class SupplierInvoiceResponse(SupplierInvoiceCreate):
    id: UUID
    tenant_id: UUID
    status: str
    file_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentCreate(BaseModel):
    third_party_id: UUID
    amount: Decimal
    currency: str = "MZN"
    value_date: datetime
    payment_method: str
    reference: str | None = None
    notes: str | None = None


class SupplierPaymentResponse(SupplierPaymentCreate):
    id: UUID
    tenant_id: UUID
    status: str
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoicePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: str
    value_date: datetime
    reference: str | None = None
    notes: str | None = None
