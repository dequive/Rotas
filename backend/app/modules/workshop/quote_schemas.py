from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QuoteItemCreate(BaseModel):
    item_type: str = "labor"  # labor | part
    description: str
    part_id: UUID | None = None
    quantity: Decimal = Field(gt=0, default=Decimal("1"))
    unit_price: Decimal = Field(ge=0, default=Decimal("0"))
    warranty_months: int = Field(ge=0, default=0)
    warranty_km: int = Field(ge=0, default=0)

    @field_validator("item_type")
    @classmethod
    def validate_item_type(cls, v: str) -> str:
        if v not in {"labor", "part"}:
            raise ValueError("item_type must be 'labor' or 'part'")
        return v


class QuoteCreate(BaseModel):
    vehicle_id: UUID
    client_id: UUID | None = None
    reception_id: UUID | None = None
    is_supplemental: bool = False
    related_work_order_id: UUID | None = None
    valid_until: datetime | None = None
    tax_total: Decimal = Field(ge=0, default=Decimal("0"))
    notes: str | None = None
    items: list[QuoteItemCreate] = Field(default_factory=list)


class QuoteRejectRequest(BaseModel):
    reason: str | None = None


class QuoteAcceptRequest(BaseModel):
    acceptance_channel: str | None = None  # presencial | whatsapp | telefone | assinatura_digital
    accepted_by_person_name: str | None = None
