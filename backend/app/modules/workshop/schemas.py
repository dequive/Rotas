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


class MaintenanceRequestResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    vehicle_id: UUID
    trip_id: UUID | None = None
    incident_id: UUID | None = None
    request_type: str
    priority: str
    description: str
    odometer_reading: int | None = None
    status: str
    requested_by: UUID | None = None
    requested_at: datetime
    created_at: datetime
    updated_at: datetime


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


class WorkOrderResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    maintenance_request_id: UUID | None = None
    vehicle_id: UUID | None = None
    work_order_number: str
    diagnosis: str | None = None
    planned_work: str
    estimated_cost: Decimal | None = None
    actual_cost: Decimal | None = None
    labor_cost: str
    status: str
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    closed_by: UUID | None = None
    closed_at: datetime | None = None
    close_notes: str | None = None
    quality_checked_by: UUID | None = None
    quality_checked_at: datetime | None = None
    quality_notes: str | None = None
    billing_status: str
    billing_document_id: UUID | None = None
    billing_error: str | None = None
    service_provider_third_party_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


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
    name: str = Field(min_length=1, max_length=160)
    service_catalog_item_id: UUID | None = None
    vehicle_id: UUID | None = None
    interval_km: int | None = Field(default=None, gt=0)
    interval_days: int | None = Field(default=None, gt=0)
    ownership_scope: str = Field(default="fleet", pattern="^(fleet|customer|all)$")
    request_reference: str | None = None
    next_due_km: int | None = Field(default=None, ge=0)
    next_due_at: datetime | None = None


class PreventiveScheduleCreate(BaseModel):
    vehicle_id: UUID
    plan_id: UUID


class WorkOrderCloseRequest(BaseModel):
    actual_cost: float | None = Field(default=None, ge=0)
    notes: str = Field(min_length=1)


# --- Workshop Staff Rates ---


class WorkshopStaffRateCreate(BaseModel):
    user_id: UUID
    hourly_rate: Decimal = Field(gt=Decimal(0))
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


# --- Advanced Inventory & Parts Schemas ---


class PartIssueRequest(BaseModel):
    inventory_id: UUID
    quantity: Decimal = Field(gt=Decimal(0))
    notes: str | None = None


class PartReturnRequest(BaseModel):
    inventory_id: UUID
    quantity: Decimal = Field(gt=Decimal(0))
    reason: str = Field(min_length=1)


class InventoryAdjustmentRequest(BaseModel):
    inventory_id: UUID
    quantity: Decimal = Field(gt=Decimal(0))
    direction: str = Field(pattern="^(in|out)$")
    reason: str = Field(min_length=1)


class PurchaseOrderItemCreate(BaseModel):
    inventory_id: UUID
    quantity_ordered: Decimal = Field(gt=Decimal(0))
    unit_price: Decimal = Field(ge=Decimal(0))


class PurchaseOrderCreate(BaseModel):
    supplier_third_party_id: UUID
    items: list[PurchaseOrderItemCreate] = Field(min_length=1)
    supplier_invoice_number: str | None = None
    notes: str | None = None


class CoreReturnCreate(BaseModel):
    inventory_id: UUID
    description: str = Field(min_length=1, max_length=200)
    serial_number: str | None = None
    evidence_photo_file_id: UUID | None = None


# --- Labor Tracking Schemas ---


class StaffRateCreate(BaseModel):
    user_id: UUID
    hourly_rate: Decimal = Field(gt=Decimal(0))
    effective_from: date


class TaskLaborCreate(BaseModel):
    user_id: UUID
    minutes_worked: int = Field(gt=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TaskLaborVoid(BaseModel):
    void_reason: str = Field(min_length=1)
    evidence_photo_file_id: UUID | None = None
    credit_amount: Decimal | None = Field(default=None, ge=Decimal(0))
    supplier_third_party_id: UUID | None = None


# ── Response contracts (F7.2) ─────────────────────────────────────────────────
# Mirrors the `service.serialize_*` helpers and the profitability reports so the
# OpenAPI contract exposes a non-empty 2xx schema for every Manager operation.


class SparePartInventoryResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    sku: str
    name: str
    unit: str
    current_quantity: Decimal
    minimum_quantity: Decimal
    average_unit_cost: Decimal | None = None
    status: str
    supplier_name: str | None = None
    supplier_third_party_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class SparePartMovementResponse(BaseModel):
    # `record_spare_part_receipt` returns the ORM row directly.
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    inventory_id: UUID
    movement_type: str
    direction: str
    quantity: Decimal
    balance_after_quantity: Decimal
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    request_reference: str | None = None
    source_type: str | None = None
    source_id: UUID | None = None
    occurred_at: datetime
    recorded_by: UUID | None = None
    notes: str | None = None
    created_at: datetime


class LowStockPartResponse(BaseModel):
    id: UUID
    sku: str
    name: str
    current_quantity: Decimal
    minimum_quantity: Decimal
    reorder_quantity: Decimal | None = None
    supplier_name: str | None = None
    lead_time_days: int | None = None


class LowStockListResponse(BaseModel):
    items: list[LowStockPartResponse]
    total: int


class SerialItemResponse(BaseModel):
    id: UUID
    part_id: UUID
    serial_number: str
    status: str
    vehicle_id: UUID | None = None
    installed_at: datetime | None = None
    scrapped_at: datetime | None = None
    notes: str | None = None
    created_at: datetime


class WorkshopToolResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_critical: bool
    calibration_due_at: datetime | None = None
    status: str
    category: str | None = None
    location: str | None = None
    serial_number: str | None = None
    purchase_date: date | None = None
    purchase_cost: Decimal | None = None
    calibration_interval_days: int | None = None
    created_at: datetime
    updated_at: datetime


class ToolCalibrationResponse(BaseModel):
    id: UUID
    tool_id: UUID
    calibrated_by: UUID | None = None
    calibrated_at: datetime
    next_due_at: datetime
    notes: str | None = None
    created_at: datetime


class ImminentMaintenanceAlertResponse(BaseModel):
    plan_id: UUID
    plan_name: str
    vehicle_id: UUID
    vehicle_plate: str
    next_due_at: datetime | None = None
    next_due_km: int | None = None
    current_km: int | None = None
    trigger_type: str


class WorkOrderProfitabilityResponse(BaseModel):
    work_order_id: UUID
    work_order_number: str
    total_revenue: float
    confirmed_revenue: float
    projected_revenue: float
    total_labor_minutes: int
    total_labor_cost: float
    total_parts_cost: float
    total_cost: float
    gross_profit_mzn: float
    gross_profit_margin_percent: float
    is_profitable: bool


class ProfitabilitySummaryTotals(BaseModel):
    confirmed_revenue: float
    projected_revenue: float
    total_labor_cost: float
    total_parts_cost: float
    total_cost: float
    confirmed_gross_profit: float
    confirmed_gross_margin_pct: float
    negative_margin_count: int
    total_work_orders: int


class ProfitabilitySummaryWorkOrder(BaseModel):
    id: UUID
    wo_number: str
    client: str | None = None
    vehicle: str | None = None
    status: str
    confirmed_revenue: float
    projected_revenue: float
    effective_revenue: float
    labor_cost: float
    parts_cost: float
    total_cost: float
    margin_mzn: float
    margin_pct: float
    is_profitable: bool
    created_at: datetime | None = None


class ProfitabilitySummaryResponse(BaseModel):
    summary: ProfitabilitySummaryTotals
    work_orders: list[ProfitabilitySummaryWorkOrder]
    total_count: int
    limit: int
    offset: int
