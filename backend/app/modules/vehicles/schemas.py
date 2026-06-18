from datetime import date
from uuid import UUID

from pydantic import BaseModel


class VehicleCreate(BaseModel):
    plate: str
    chassis: str | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    color: str | None = None
    category: str = "pesado"
    fuel_type: str = "gasoleo"
    current_km: int = 0
    documents: dict | None = None
    avg_consumption_target: float | None = None
    fuel_limit_daily: float | None = None


class VehiclePatch(BaseModel):
    plate: str | None = None
    chassis: str | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    color: str | None = None
    category: str | None = None
    status: str | None = None
    current_km: int | None = None
    fuel_type: str | None = None
    documents: dict | None = None
    avg_consumption_target: float | None = None
    fuel_limit_daily: float | None = None


class VehicleRead(BaseModel):
    id: UUID
    tenant_id: UUID
    plate: str
    status: str
    current_km: int


class VehicleDocumentRenewalRequest(BaseModel):
    valid_until: date
    file_id: UUID | None = None
    reference: str | None = None
    notes: str | None = None
