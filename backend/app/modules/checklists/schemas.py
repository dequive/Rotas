from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ChecklistTemplateCreate(BaseModel):
    name: str
    type: str
    category: str | None = None
    items: list[dict] = Field(default_factory=list)


class ChecklistCreate(BaseModel):
    trip_id: UUID | None = None
    vehicle_id: UUID
    driver_id: UUID
    template_id: UUID
    type: str
    responses: dict = Field(default_factory=dict)
    location: dict | None = None
    gps_accuracy_m: float | None = None
    gps_source: str | None = None
    client_captured_at: datetime | None = None
    started_at: datetime | None = None


class ChecklistPatch(BaseModel):
    status: str | None = None
    responses: dict | None = None
    location: dict | None = None
    gps_accuracy_m: float | None = None
    gps_source: str | None = None


class CompleteChecklistRequest(BaseModel):
    completed_at: datetime | None = None
    signature_file_id: UUID | None = None


class ResolveChecklistFailureRequest(BaseModel):
    resolution_notes: str
    resolved_at: datetime | None = None


# ── Response contracts (F7.2) ─────────────────────────────────────────────────


class ChecklistRead(BaseModel):
    """Mirrors `service.serialize_checklist`."""

    id: UUID
    tenant_id: UUID
    trip_id: UUID | None = None
    vehicle_id: UUID
    driver_id: UUID | None = None
    template_id: UUID
    type: str
    status: str
    # JSON column: templates map item_id -> answer, but legacy rows store a list.
    responses: dict | list[dict] = Field(default_factory=dict)
    location: dict | None = None
    gps_accuracy_m: float | None = None
    gps_source: str | None = None
    client_captured_at: datetime | None = None
    server_received_at: datetime | None = None
    signature_file_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    created_at: datetime
    blocking_failures: list[dict] = Field(default_factory=list)
