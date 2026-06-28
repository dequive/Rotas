from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PurchaseOrderCreate(BaseModel):
    third_party_id: UUID
    work_order_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    trip_id: Optional[UUID] = None
    po_number: str
    description: str
    estimated_amount: Optional[Decimal] = None
    currency: str = "MZN"
    issued_at: datetime


class PurchaseOrderResponse(PurchaseOrderCreate):
    id: UUID
    tenant_id: UUID
    status: str
    approved_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierInvoiceCreate(BaseModel):
    third_party_id: UUID
    work_order_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    trip_id: Optional[UUID] = None
    invoice_number: Optional[str] = None
    description: Optional[str] = None
    amount: Decimal
    currency: str = "MZN"
    issued_at: datetime
    due_date: Optional[datetime] = None


class SupplierInvoiceResponse(SupplierInvoiceCreate):
    id: UUID
    tenant_id: UUID
    status: str
    file_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentCreate(BaseModel):
    third_party_id: UUID
    amount: Decimal
    currency: str = "MZN"
    value_date: datetime
    payment_method: str
    reference: Optional[str] = None
    notes: Optional[str] = None


class SupplierPaymentResponse(SupplierPaymentCreate):
    id: UUID
    tenant_id: UUID
    status: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InvoicePaymentRequest(BaseModel):
    amount: Decimal
    payment_method: str
    value_date: datetime
    reference: Optional[str] = None
    notes: Optional[str] = None
