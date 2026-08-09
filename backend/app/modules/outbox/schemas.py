from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OutboxReplayRequest(BaseModel):
    reason: str = Field(min_length=10, max_length=1000)


class OutboxOperationalEvent(BaseModel):
    id: UUID
    tenant_id: UUID
    aggregate_type: str | None
    aggregate_id: UUID | None
    event_type: str | None
    status: str
    attempt_count: int
    total_attempt_count: int
    last_error: str | None
    created_at: datetime
    dead_lettered_at: datetime | None
    replay_count: int
    last_replayed_at: datetime | None
    replayed_by: str | None
    replay_reason: str | None


class OutboxReplayResponse(BaseModel):
    id: UUID
    status: str
    replay_count: int
    next_attempt_at: datetime | None
    last_replayed_at: datetime | None


class OutboxHealthResponse(BaseModel):
    statuses: dict[str, int]
    due_pending: int
    stale_claims: int
    unreconciled_sent: int
    oldest_pending_at: datetime | None
    checked_at: datetime
