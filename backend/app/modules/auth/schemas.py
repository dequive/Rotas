from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_slug: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class PasswordResetRequest(BaseModel):
    email: str
    tenant_slug: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("tenant_slug")
    @classmethod
    def normalize_tenant_slug(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None


class PasswordResetCompleteRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("Reset token is required.")
        return token

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must have at least 8 characters.")
        return value


class TokenUser(BaseModel):
    id: UUID
    tenant_id: UUID
    role: str
    full_name: str


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: TokenUser


class MfaChallengeResponse(BaseModel):
    mfa_required: Literal[True]
    mfa_challenge: str
    expires_in: int


class MfaStatusResponse(BaseModel):
    enabled: bool
    confirmed_at: datetime | None = None


class MfaSetupResponse(MfaStatusResponse):
    secret: str | None = None
    otpauth_uri: str | None = None


class PasswordResetResponse(BaseModel):
    ok: bool
    reset_token: str | None = None
    reset_url: str | None = None


class SessionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime
    created_by_ip: str | None = None
    user_agent: str | None = None
    active: bool


class DriverPairRequest(BaseModel):
    pairing_code: str
    device_id: str
    device_name: str | None = None


class TokenDriver(BaseModel):
    id: UUID
    tenant_id: UUID
    full_name: str


class DriverTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    driver: TokenDriver


class SessionRevokeResponse(BaseModel):
    revoked: bool


class MfaCodeRequest(BaseModel):
    code: str

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        code = value.strip().replace(" ", "")
        if len(code) != 6 or not code.isdigit():
            raise ValueError("MFA code must contain 6 digits.")
        return code


class MfaVerifyRequest(MfaCodeRequest):
    challenge_token: str

    @field_validator("challenge_token")
    @classmethod
    def validate_challenge_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("MFA challenge token is required.")
        return token
