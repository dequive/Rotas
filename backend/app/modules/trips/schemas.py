from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TripCreate(BaseModel):
    contract_id: UUID | None = None
    vehicle_id: UUID
    driver_id: UUID
    origin: str
    destination: str
    cargo_type: str | None = None
    cargo_class: str | None = None
    cargo_weight: Decimal | None = None
    load_state: str | None = None
    requires_load_permit: bool = False
    requires_cargo_manifest: bool = False
    planned_departure: datetime | None = None
    planned_arrival: datetime | None = None
    contract_reference: str | None = None
    payload_override_reason: str | None = None
    is_hazmat: bool = False
    is_international: bool = False
    hazmat_class: str | None = None
    un_number: str | None = None
    hazmat_label: str | None = None
    hos_override_reason: Annotated[str, Field(max_length=500)] | None = None


class TripResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    trip_order_id: UUID | None = None
    contract_id: UUID | None = None
    vehicle_id: UUID
    driver_id: UUID
    origin: str
    destination: str
    cargo_type: str | None = None
    cargo_class: str | None = None
    cargo_weight: float | None = None
    payload_override_reason: str | None = None
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
    contract_reference: str | None = None
    billing_status: str
    billable_at: datetime | None = None
    billed_at: datetime | None = None
    billing_document_id: UUID | None = None
    closed_at: datetime | None = None
    closed_by: UUID | None = None
    operational_close_notes: str | None = None
    total_fuel_cost: float | None = None
    total_expense_cost: float | None = None
    total_transport_cost: float | None = None
    actual_revenue: float | None = None
    actual_margin: float | None = None
    costs_reconciled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TripExecutionEventResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    trip_id: UUID
    event_type: str
    event_time: datetime
    location: dict | None = None
    odometer_reading: float | None = None
    fuel_level: float | None = None
    notes: str | None = None
    reported_by: UUID | None = None
    source: str
    created_at: datetime


class TripDispatchResponse(BaseModel):
    trip: TripResponse
    event: TripExecutionEventResponse


class StartTripRequest(BaseModel):
    km_start: int
    km_start_file_id: UUID | None = None
    actual_departure: datetime | None = None
    override_missing_load_permit: bool = False


class CompleteTripRequest(BaseModel):
    km_end: int
    km_end_file_id: UUID | None = None
    actual_arrival: datetime | None = None
    recipient_name: str | None = None


class OperationalCloseTripRequest(BaseModel):
    closed_at: datetime | None = None
    notes: str | None = None


class AssociateContractRequest(BaseModel):
    contract_id: UUID


class TripStopCreate(BaseModel):
    stop_type: str
    location: dict | None = None
    address: str | None = None
    notes: str | None = None
    photo_file_id: UUID | None = None
    cost: float | None = None
    expense_category: str | None = None
    stopped_at: datetime | None = None


class TripCostCreate(BaseModel):
    cost_type: str
    description: str | None = None
    amount: float
    currency: str = "MZN"
    paid_by: str = "company"
    payment_method: str | None = None
    receipt_file_id: UUID | None = None
    request_reference: str
    incurred_at: datetime


class TripCostCorrectionCreate(BaseModel):
    correction_type: Literal["adjustment", "reversal"]
    adjustment_amount: Decimal | None = None
    reason: str = Field(min_length=3, max_length=500)
    request_reference: str = Field(min_length=1, max_length=120)
    incurred_at: datetime

    @model_validator(mode="after")
    def validate_correction_amount(self) -> Self:
        if self.correction_type == "adjustment":
            if self.adjustment_amount is None or self.adjustment_amount == 0:
                raise ValueError("adjustment_amount must be non-zero for an adjustment")
        elif self.adjustment_amount is not None:
            raise ValueError("adjustment_amount is not accepted for a reversal")
        return self


class TripCostRead(BaseModel):
    id: UUID
    trip_id: UUID
    cost_type: str
    description: str | None = None
    amount: Decimal
    currency: str
    paid_by: str
    payment_method: str | None = None
    receipt_file_id: UUID | None = None
    request_reference: str
    source_type: str
    source_id: UUID | None = None
    entry_type: Literal["original", "adjustment", "reversal"]
    corrects_id: UUID | None = None
    correction_reason: str | None = None
    driver_id: UUID | None = None
    driver_visibility: Literal["hidden", "visible"]
    recorded_by_type: Literal["driver", "manager", "system"]
    incurred_at: datetime
    created_at: datetime


class TripDriverAllowanceRecordRequest(BaseModel):
    distance_km: float | None = None
    incurred_at: datetime | None = None
    request_reference: str | None = None
    notes: str | None = None


class DispatchClearanceApproveRequest(BaseModel):
    vehicle_checked: bool = True
    driver_checked: bool = True
    documents_checked: bool = True
    load_permit_checked: bool = False
    cargo_checked: bool = True
    fuel_advance_checked: bool = True
    route_risk_checked: bool = True
    blocked_reason: str | None = None


class DispatchClearanceResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    trip_order_id: UUID | None = None
    trip_id: UUID
    vehicle_checked: bool
    driver_checked: bool
    documents_checked: bool
    load_permit_checked: bool
    cargo_checked: bool
    fuel_advance_checked: bool
    route_risk_checked: bool
    clearance_status: str
    blocked_reason: str | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TripDispatchRequest(BaseModel):
    dispatched_at: datetime | None = None
    notes: str | None = None


class TripExecutionEventCreate(BaseModel):
    event_type: str
    event_time: datetime | None = None
    location: dict | None = None
    odometer_reading: float | None = None
    fuel_level: float | None = None
    notes: str | None = None
    source: str = "manual"


class TripIncidentCreate(BaseModel):
    incident_type: str
    severity: str = "medium"
    occurred_at: datetime | None = None
    location: dict | None = None
    description: str
    immediate_action: str | None = None
    financial_impact_estimate: float | None = None
    delay_minutes: int | None = None


class TripIncidentResolveRequest(BaseModel):
    resolution_notes: str
    resolved_at: datetime | None = None


class TripPatch(BaseModel):
    cargo_type: str | None = None
    load_state: str | None = None
    origin: str | None = None
    destination: str | None = None
    notes: str | None = None
    cargo_weight: Decimal | None = None
    payload_override_reason: str | None = None



class TripStopPatch(BaseModel):
    stop_type: str | None = None
    location: dict | None = None
    notes: str | None = None
    duration_minutes: int | None = None


# ── Response contracts (F7.2) ─────────────────────────────────────────────────


class DriverDespachoTable(BaseModel):
    """Despacho table applied to the allowance, as configured per tenant."""

    name: str
    reference: str | None = None
    effective_from: str | None = None
    currency: str
    source: str
    entry_mode: str | None = None


class TripDriverAllowanceResponse(BaseModel):
    """`service.record_driver_travel_allowance` — trip cost plus applied policy."""

    id: UUID
    trip_id: UUID
    cost_type: str
    description: str | None = None
    amount: Decimal
    currency: str
    paid_by: str | None = None
    payment_method: str | None = None
    receipt_file_id: UUID | None = None
    request_reference: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    incurred_at: datetime
    distance_km: float
    allowance_amount: float
    despacho_table: DriverDespachoTable
    # Tier shape is tenant-configured (min_km / max_km / amount), so it stays open.
    despacho_tier: dict | None = None
