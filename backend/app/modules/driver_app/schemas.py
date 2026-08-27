from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DriverProfileRead(BaseModel):
    tenant_id: UUID
    driver_id: UUID
    device_id: str | None = None


class DriverChecklistTemplateRead(BaseModel):
    id: UUID
    name: str
    type: str
    category: str | None = None
    is_active: bool
    items: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DriverTripRead(BaseModel):
    """Trip execution fields visible to the assigned driver."""

    id: UUID
    vehicle_id: UUID
    driver_id: UUID
    origin: str
    destination: str
    cargo_type: str | None = None
    cargo_class: str | None = None
    cargo_weight: float | None = None
    load_state: str | None = None
    requires_load_permit: bool
    requires_cargo_manifest: bool
    waybill_number: str | None = None
    km_start: int | None = None
    km_end: int | None = None
    status: str
    planned_departure: datetime | None = None
    actual_departure: datetime | None = None
    planned_arrival: datetime | None = None
    actual_arrival: datetime | None = None
    recipient_name: str | None = None
    cargo_status: str | None = None
    created_at: datetime
    updated_at: datetime


class DriverTripPageRead(BaseModel):
    items: list[DriverTripRead]
    total: int
    limit: int
    offset: int


class DriverChecklistRecordRead(BaseModel):
    """Submitted checklist facts visible to the owning driver."""

    id: UUID
    trip_id: UUID | None = None
    vehicle_id: UUID
    checklist_type: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class DriverChecklistRecordPageRead(BaseModel):
    items: list[DriverChecklistRecordRead]
    total: int
    limit: int
    offset: int


class DriverFuelRecordRead(BaseModel):
    """Immutable refuelling facts visible to the owning driver."""

    id: UUID
    trip_id: UUID | None = None
    vehicle_id: UUID
    fuel_date: datetime
    station_name: str | None = None
    fuel_type: str
    liters: Decimal
    total_cost: Decimal
    km_at_refuel: int
    has_receipt: bool
    is_verified: bool
    is_flagged: bool
    created_at: datetime


class DriverFuelRecordPageRead(BaseModel):
    items: list[DriverFuelRecordRead]
    total: int
    limit: int
    offset: int


class DriverExpenseRecordRead(BaseModel):
    """Driver-paid trip expense without reconciliation or accounting fields."""

    id: UUID
    trip_id: UUID
    expense_type: str
    description: str | None = None
    amount: Decimal
    currency: str
    payment_method: str | None = None
    has_receipt: bool
    entry_type: Literal["original", "adjustment", "reversal"]
    corrects_id: UUID | None = None
    correction_reason: str | None = None
    recorded_by_type: Literal["driver", "manager", "system"]
    incurred_at: datetime
    created_at: datetime


class DriverExpenseRecordPageRead(BaseModel):
    items: list[DriverExpenseRecordRead]
    total: int
    limit: int
    offset: int


class DriverAdvanceRecordRead(BaseModel):
    """Travel dispatch amount issued to the owning driver."""

    id: UUID
    trip_id: UUID
    total_amount: Decimal
    allowance_amount: Decimal
    expense_amount: Decimal
    currency: str
    status: str
    issued_at: datetime


class DriverAdvanceRecordPageRead(BaseModel):
    items: list[DriverAdvanceRecordRead]
    total: int
    limit: int
    offset: int


class DriverDocumentRequirementRead(BaseModel):
    document_type: str
    present: bool


class DriverTripDocumentRead(BaseModel):
    id: UUID
    document_type: str
    document_number: str | None = None
    status: str
    file_id: UUID | None = None
    issued_at: datetime


class DriverDocumentRequestCreate(BaseModel):
    document_type: str = Field(min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=500)


class DriverDocumentRequestRead(BaseModel):
    id: UUID
    trip_id: UUID
    document_type: str
    status: str
    note: str | None = None
    created_at: datetime


class DriverTripDocumentsRead(BaseModel):
    trip_id: UUID
    complete: bool
    can_request: bool
    missing_required: list[str]
    requirements: list[DriverDocumentRequirementRead]
    documents: list[DriverTripDocumentRead]
    requests: list[DriverDocumentRequestRead]


class DriverVehicleRead(BaseModel):
    id: UUID
    plate: str
    brand: str | None = None
    model: str | None = None


class DriverBootstrapRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    profile: DriverProfileRead
    checklist_templates: list[DriverChecklistTemplateRead] = Field(
        alias="checklistTemplates"
    )
    active_trip: DriverTripRead | None = Field(alias="activeTrip")
    vehicles: list[DriverVehicleRead] = Field(default_factory=list)


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ApiErrorResponse(BaseModel):
    error: ApiErrorDetail
