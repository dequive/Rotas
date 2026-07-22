from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CatalogItemCreate(BaseModel):
    code: str
    name: str
    category: str = "geral"
    standard_duration_minutes: int = Field(ge=0, default=60)
    base_price: Decimal = Field(ge=0, default=Decimal("0"))
    includes_parts: bool = False
    is_active: bool = True
    notes: str | None = None

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"mecanica", "electricidade", "pintura", "pneus", "ac", "geral"}
        if v.lower() not in allowed:
            raise ValueError(f"category must be one of {sorted(allowed)}")
        return v.lower()


class CatalogItemUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    standard_duration_minutes: int | None = Field(default=None, ge=0)
    base_price: Decimal | None = Field(default=None, ge=0)
    includes_parts: bool | None = None
    is_active: bool | None = None
    notes: str | None = None
