import re as _re
import uuid
from datetime import datetime

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
    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role: str
    is_active: bool


_SLUG_RE = _re.compile(r"^[a-z0-9_-]{1,80}$")


class TenantRoleCreate(BaseModel):
    name: str
    slug: str
    permissions: list[str]


class TenantRoleUpdate(BaseModel):
    name: str | None = None
    permissions: list[str] | None = None


class TenantRoleRead(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    permissions: list[str]
    is_system: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AssignCustomRoleRequest(BaseModel):
    custom_role_id: uuid.UUID | None  # None = revert to standard role
