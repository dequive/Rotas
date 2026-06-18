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
