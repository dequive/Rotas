from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TripOrderCreate(BaseModel):
    contract_id: UUID | None = None
    client_id: UUID | None = None
    customer_reference: str | None = None
    origin: str = Field(min_length=1, max_length=160)
    destination: str = Field(min_length=1, max_length=160)
    cargo_type: str | None = None
    cargo_description: str | None = None
    estimated_weight: float | None = None
    estimated_volume: float | None = None
    cargo_value: float | None = None
    cargo_risk_level: str = "normal"
    status: str
    created_at: datetime
    updated_at: datetime
    requested_pickup_date: date
    requested_delivery_date: date | None = None
    sla_pickup_deadline: datetime | None = None
    sla_delivery_deadline: datetime | None = None
    priority: str = "normal"
    estimated_distance_km: float | None = None
    estimated_fuel_cost: float | None = None
    estimated_toll_cost: float | None = None
    estimated_revenue: float | None = None
    source: str = "manual"
    requires_load_permit: bool = False
    requires_police_clearance: bool = False
    requires_customs_clearance: bool = False
    operational_notes: str | None = None
    commercial_notes: str | None = None


class TripOrderConfirmRequest(BaseModel):
    reason: str | None = None


class TripOrderAssignRequest(BaseModel):
    vehicle_id: UUID
    driver_id: UUID
    reason: str | None = None


class TripOrderCancelRequest(BaseModel):
    reason: str


class DispatchClearanceRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=10, max_length=500)
