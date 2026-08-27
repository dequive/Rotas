from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class OperationalWaiverCreate(BaseModel):
    entity_type: str
    entity_id: UUID
    waiver_type: str
    reason: str
    risk_level: str = "medium"
    expires_at: datetime | None = None


class OperationalWaiverRevokeRequest(BaseModel):
    reason: str | None = None


# ── Response contracts (F7.2) ─────────────────────────────────────────────────


class OperationalWaiverRead(BaseModel):
    """Mirrors `service.serialize_waiver`."""

    id: UUID
    tenant_id: UUID
    entity_type: str
    entity_id: UUID
    waiver_type: str
    reason: str
    risk_level: str | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    expires_at: datetime | None = None
    status: str
    created_at: datetime
