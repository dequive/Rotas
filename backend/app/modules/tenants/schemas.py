from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    is_active: bool
    timezone: str
    currency: str
    created_at: datetime


class TenantPatch(BaseModel):
    timezone: str | None = None
    currency: str | None = None
    whatsapp_number: str | None = None
    compliance_policy: dict | None = None


class DriverDespachoTableTier(BaseModel):
    min_km: float
    max_km: float | None = None
    amount: float
    label: str | None = None
    code: str | None = None


class DriverDespachoTableUpdate(BaseModel):
    enabled: bool = True
    table_name: str
    table_reference: str | None = None
    currency: str = "MZN"
    effective_from: str | None = None
    min_long_course_km: float = 100
    tiers: list[DriverDespachoTableTier]
