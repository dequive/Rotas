from uuid import UUID

from pydantic import BaseModel


class PresignRequest(BaseModel):
    entity_type: str
    entity_id: UUID | None = None
    file_type: str
    original_name: str
    mime_type: str
    size_bytes: int
    sha256_hash: str


class PresignResponse(BaseModel):
    file_id: UUID
    upload_url: str
    storage_key: str
    expires_in: int


class ConfirmUploadRequest(BaseModel):
    file_id: UUID
    entity_type: str | None = None
    entity_id: UUID | None = None


class FileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    entity_type: str | None = None
    entity_id: UUID | None = None
    file_type: str
    original_name: str
    storage_key: str
    storage_provider: str
    mime_type: str
    size_bytes: int
    sha256_hash: str
    confirmed_at: str | None = None
