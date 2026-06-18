from decimal import Decimal

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    trading_name: str = Field(..., min_length=1, max_length=160)
    legal_name: str | None = None
    nuit: str = Field(..., pattern=r"^\d{9}$")
    address: str | None = None
    city: str | None = None
    phone: str | None = None
    email: str | None = None
    payment_terms_days: int = Field(30, ge=1, le=365)
    credit_limit: Decimal | None = None


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
