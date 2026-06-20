from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlatformLoginRequest(BaseModel):
    email: str
    password: str


class PlatformUserRead(BaseModel):
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlatformTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: PlatformUserRead


class PlatformChangePlanRequest(BaseModel):
    plan: str


class PlatformCreateUserRequest(BaseModel):
    email: str
    role: str
    password: str
