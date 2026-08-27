from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmailNotificationCreate(BaseModel):
    request_reference: str = Field(min_length=1, max_length=160)
    recipient: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    body_text: str = Field(min_length=1)
    body_html: str | None = None
    template: str | None = Field(default=None, max_length=80)
    payload: dict | None = None


class NotificationRead(BaseModel):
    id: UUID
    tenant_id: UUID
    request_reference: str
    channel: str
    recipient: str
    subject: str
    body_text: str
    body_html: str | None = None
    template: str | None = None
    payload: dict | None = None
    status: str
    attempts: int
    last_error: str | None = None
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
