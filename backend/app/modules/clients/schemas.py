import re
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.modules.drivers.schemas import _normalize_email, _normalize_phone


def _normalize_nuit(v: str | None) -> str | None:
    if v is None:
        return v
    if not v.strip():
        return None
    cleaned = re.sub(r"\D", "", v)
    if len(cleaned) != 9:
        raise ValueError("NUIT must be exactly 9 digits.")
    return cleaned


class ClientCreate(BaseModel):
    trading_name: str = Field(..., min_length=1, max_length=160)
    legal_name: str | None = None
    nuit: str = Field(..., min_length=1, max_length=20)
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    client_type: str = Field("individual", pattern="^(individual|organization)$")
    payment_terms_days: int = Field(30, ge=1, le=365)
    credit_limit: Decimal | None = None

    @field_validator("nuit")
    @classmethod
    def validate_nuit(cls, v: str) -> str:
        res = _normalize_nuit(v)
        if not res:
            raise ValueError("NUIT cannot be empty.")
        return res

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _normalize_email(v)


class ClientPatch(BaseModel):
    trading_name: str | None = Field(None, min_length=1, max_length=160)
    legal_name: str | None = None
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    payment_terms_days: int | None = Field(None, ge=1, le=365)
    credit_limit: Decimal | None = None
    is_active: bool | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _normalize_email(v)
