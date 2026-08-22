from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkOrderDetailCore(BaseModel):
    id: UUID
    work_order_number: str
    status: str
    diagnosis: str | None = None
    planned_work: str
    estimated_cost: float | None = None
    actual_cost: float | None = None
    origin_type: str
    billing_status: str
    billing_error: str | None = None
    document_id: UUID | None = None
    invoice_number: str | None = None
    invoice_status: str | None = None
    approved_at: datetime | None = None
    quality_checked_at: datetime | None = None
    quality_notes: str | None = None
    closed_at: datetime | None = None
    close_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class VehicleDetail(BaseModel):
    id: UUID
    plate: str
    brand: str | None = None
    model: str | None = None
    current_km: int
    odometer_at_reception: int | None = None


class ClientDetail(BaseModel):
    id: UUID | None = None
    trading_name: str
    legal_name: str | None = None
    client_type: str
    nuit: str | None = None
    is_fleet_owned: bool = False


class ReceptionPhotoDetail(BaseModel):
    id: UUID
    file_id: UUID
    caption: str | None = None
    taken_at: datetime
    download_path: str


class ReceptionDetail(BaseModel):
    id: UUID
    reception_number: str
    reported_issues: str | None = None
    client_signature_file_id: UUID | None = None
    photos: list[ReceptionPhotoDetail] = Field(default_factory=list)


class QuoteDetail(BaseModel):
    id: UUID
    quote_number: str
    status: str
    approved_value: float
    client_signature_file_id: UUID | None = None
    evidence_photo_file_id: UUID | None = None


class LaborSessionDetail(BaseModel):
    id: UUID
    user_id: UUID
    mechanic_name: str
    started_at: datetime | None = None
    completed_at: datetime
    minutes_worked: int
    hourly_rate_applied: float
    total_labor_cost: float
    voided_at: datetime | None = None
    void_reason: str | None = None


class TaskDetail(BaseModel):
    id: UUID
    description: str
    status: str
    assigned_to: UUID | None = None
    assigned_mechanic_name: str | None = None
    estimated_minutes: int | None = None
    actual_minutes: int | None = None
    labor_sessions: list[LaborSessionDetail] = Field(default_factory=list)


class PartIssuedDetail(BaseModel):
    inventory_id: UUID
    sku: str
    name: str
    unit: str
    issued_quantity: float
    returned_quantity: float
    net_quantity: float
    net_cost: float


class UnreturnedToolDetail(BaseModel):
    checkout_id: UUID
    tool_id: UUID
    code: str
    name: str
    checked_out_at: datetime


class WorkOrderBlockers(BaseModel):
    incomplete_tasks: int = 0
    unreturned_tools: int = 0


class WorkOrderDetailResponse(BaseModel):
    work_order: WorkOrderDetailCore
    vehicle: VehicleDetail | None = None
    client: ClientDetail
    reception: ReceptionDetail | None = None
    quote: QuoteDetail | None = None
    tasks: list[TaskDetail] = Field(default_factory=list)
    parts_issued: list[PartIssuedDetail] = Field(default_factory=list)
    unreturned_tools: list[UnreturnedToolDetail] = Field(default_factory=list)
    blockers: WorkOrderBlockers
