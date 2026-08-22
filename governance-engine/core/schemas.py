from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Severity = Literal["baixa", "media", "alta", "critica"]


# ── Occurrences ───────────────────────────────────────────────────────────────


class LinkInputSchema(BaseModel):
    entity_type: str
    external_id: str
    role: str = "sujeito"
    display_name: str = ""
    snapshot: dict = Field(default_factory=dict)


class OccurrenceCreate(BaseModel):
    type_code: str
    severity: Severity
    title: str
    description: str | None = None
    occurred_at: datetime
    links: list[LinkInputSchema] = Field(default_factory=list)
    location_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    supersedes_id: UUID | None = None
    idempotency_key: str | None = None
    payload: dict = Field(default_factory=dict)


class OccurrenceLinkResponse(BaseModel):
    instance_id: UUID
    entity_type: str
    external_id: str
    role: str
    display_name: str
    snapshot: dict


class OccurrenceResponse(BaseModel):
    id: UUID
    numero: str
    type_code: str
    severity: str
    title: str
    description: str | None
    occurred_at: datetime
    recorded_at: datetime
    supersedes_id: UUID | None
    links: list[OccurrenceLinkResponse] = Field(default_factory=list)
    case_id: UUID | None = None
    case_reference: str | None = None


class OccurrenceReverseRequest(BaseModel):
    reason: str = Field(..., min_length=5)
    idempotency_key: str | None = None


# ── Cases ─────────────────────────────────────────────────────────────────────


class CaseCreate(BaseModel):
    case_type_code: str
    occurrence_ids: list[UUID] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
    idempotency_key: str | None = None


class TransitionRequest(BaseModel):
    to_status: str
    payload: dict = Field(default_factory=dict)
    reason: str | None = None
    attachments_present: bool = False
    idempotency_key: str | None = None


class TransitionResponse(BaseModel):
    id: UUID
    case_id: UUID
    from_status: str | None
    to_status: str
    actor_id: UUID
    reason: str | None
    transitioned_at: datetime


class CaseResponse(BaseModel):
    id: UUID
    reference: str
    case_type_code: str
    status: str
    assignee_id: UUID | None
    payload: dict
    sla_due_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AvailableTransition(BaseModel):
    to_status: str
    required_fields: list[str]
    required_attachments: bool
