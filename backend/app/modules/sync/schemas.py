from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SyncOperation(BaseModel):
    local_id: str
    idempotency_key: str
    operation: str
    entity_type: str
    payload: dict[str, Any]
    client_timestamp: datetime | None = None  # for clock skew handling (ROADMAP)


class SyncBatchRequest(BaseModel):
    device_id: str
    operations: list[SyncOperation]


class SyncResult(BaseModel):
    local_id: str
    server_id: str | None = None
    status: str
    entity_type: str
    error_code: str | None = None
    message: str | None = None
    server_timestamp: datetime | None = None  # returned in result for clock skew


class SyncBatchResponse(BaseModel):
    results: list[SyncResult]
