from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


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
    hazmat_class: str | None = None
    un_number: str | None = None
    hazmat_label: str | None = None


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


class TripStopPatch(BaseModel):
    stop_type: str | None = None
    location: dict | None = None
    notes: str | None = None
    duration_minutes: int | None = None
