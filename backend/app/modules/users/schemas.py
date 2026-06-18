from uuid import UUID

from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str | None = None
    role: str = "viewer"


class UserPatch(BaseModel):
    email: str | None = None
    full_name: str | None = None
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None


class UserRead(BaseModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool
