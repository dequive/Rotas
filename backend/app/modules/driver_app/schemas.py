from datetime import datetime
from typing import Any
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
