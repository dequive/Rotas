from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MaintenanceRequestCreate(BaseModel):
    vehicle_id: UUID
    trip_id: UUID | None = None
    incident_id: UUID | None = None
    request_type: str = "corrective"
    priority: str = "normal"
    description: str = Field(min_length=1)
    odometer_reading: int | None = Field(default=None, ge=0)


class WorkOrderCreate(BaseModel):
    maintenance_request_id: UUID | None = None
    vehicle_id: UUID
    diagnosis: str | None = None
    planned_work: str = Field(min_length=1)
    estimated_cost: float | None = Field(default=None, ge=0)


class WorkOrderApproveRequest(BaseModel):
    notes: str | None = None


class WorkOrderTransitionRequest(BaseModel):
    notes: str | None = None


class WorkOrderTaskCreate(BaseModel):
    description: str = Field(min_length=1)


class WorkOrderTaskCompleteRequest(BaseModel):
    notes: str | None = None


class SparePartInventoryCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    unit: str = Field(default="unit", min_length=1, max_length=30)
    minimum_quantity: float = Field(default=0, ge=0)


class SparePartReceiptCreate(BaseModel):
    inventory_id: UUID
    request_reference: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    occurred_at: datetime
    notes: str | None = None


class MaintenancePartIssueCreate(BaseModel):
    inventory_id: UUID
    request_reference: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0)
    occurred_at: datetime
    notes: str | None = None


class WorkshopToolCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    is_critical: bool = False
    calibration_due_at: datetime | None = None


class ToolCheckoutCreate(BaseModel):
    tool_id: UUID
    checkout_reference: str = Field(min_length=1, max_length=120)
    checked_out_at: datetime
    due_at: datetime | None = None
    notes: str | None = None


class ToolReturnCreate(BaseModel):
    return_reference: str = Field(min_length=1, max_length=120)
    returned_at: datetime
    return_condition: str = "available"
    notes: str | None = None


class MaintenancePlanCreate(BaseModel):
    vehicle_id: UUID
    request_reference: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    interval_km: int | None = Field(default=None, gt=0)
    interval_days: int | None = Field(default=None, gt=0)
    next_due_km: int | None = Field(default=None, ge=0)
    next_due_at: datetime | None = None


class WorkOrderCloseRequest(BaseModel):
    actual_cost: float | None = Field(default=None, ge=0)
    notes: str = Field(min_length=1)
