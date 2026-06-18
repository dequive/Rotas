from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    driver_id: UUID | None
    action: str
    entity_type: str
    entity_id: UUID | None
    correlation_id: str | None
    created_at: datetime
