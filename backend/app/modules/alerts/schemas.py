from uuid import UUID

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    request_reference: str = Field(min_length=1, max_length=120)
    alert_type: str
    priority: str = "medium"
    entity_type: str | None = None
    entity_id: UUID | None = None
    title: str
    message: str | None = None
    channel: str = "dashboard"


class AlertStatusPatch(BaseModel):
    status: str
