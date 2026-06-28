from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MaintenanceRequestCreate(BaseModel):
    vehicle_id: UUID
    trip_id: UUID | None = None
    incident_id: UUID | None = None
    request_type: str = "corrective"
    priority: str = "normal"
    description: str = Field(min_length=1)
    odometer_reading: int | None = Field(default=None, ge=0)


class MaintenanceRequestNoteCreate(BaseModel):
    body: str = Field(min_length=1)


class MaintenanceRequestNoteResponse(BaseModel):
    id: UUID
    author_id: UUID
    body: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MaintenanceRequestStatusUpdate(BaseModel):
    status: str = Field(min_length=1, max_length=30)



class WorkOrderCreate(BaseModel):
    maintenance_request_id: UUID | None = None
    governance_case_id: UUID | None = None
    vehicle_id: UUID | None = None
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
    actual_minutes: int | None = Field(default=None, ge=1)


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


# --- Workshop Staff Rates ---


class WorkshopStaffRateCreate(BaseModel):
    user_id: UUID
    hourly_rate: Decimal = Field(gt=0)
    effective_from: date


class WorkshopStaffRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    user_id: UUID
    hourly_rate: Decimal
    effective_from: date
    created_at: datetime


# --- Task Assignment ---


class TaskAssignRequest(BaseModel):
    assigned_to: UUID
    estimated_minutes: int | None = Field(default=None, ge=1)


# --- Tool Calibration ---


class ToolCalibrationCreate(BaseModel):
    calibrated_by: UUID | None = None
    calibrated_at: datetime
    next_due_at: datetime
    notes: str | None = None


class ToolCalibrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tool_id: UUID
    calibrated_by: UUID | None
    calibrated_at: datetime
    next_due_at: datetime
    notes: str | None
    created_at: datetime


class ToolUpdateRequest(BaseModel):
    status: str | None = None
    location: str | None = None
    calibration_interval_days: int | None = Field(default=None, ge=1)
    category: str | None = None


# --- Serialized Spare Parts ---


class SerialItemCreate(BaseModel):
    serial_number: str = Field(min_length=1, max_length=120)
    notes: str | None = None


class SerialItemInstallRequest(BaseModel):
    vehicle_id: UUID


class SerialItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_id: UUID
    serial_number: str
    status: str
    vehicle_id: UUID | None
    installed_at: datetime | None
    scrapped_at: datetime | None
    notes: str | None
    created_at: datetime


# --- Vehicle History ---


class VehicleHistoryEvent(BaseModel):
    event_type: str
    event_date: datetime
    title: str
    description: str | None
    reference_id: UUID
    odometer_reading: int | None


class VehicleHistoryResponse(BaseModel):
    events: list[VehicleHistoryEvent]
    next_cursor: str | None
    total_count: int
