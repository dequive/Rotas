from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class KnownRouteCreate(BaseModel):
    origin: str
    destination: str
    distance_km: float
    avg_fuel_liters: float | None = None
    despacho_vazio: float | None = None
    despacho_carregado: float | None = None
    notes: str | None = None
    is_active: bool = True


class KnownRoutePatch(BaseModel):
    origin: str | None = None
    destination: str | None = None
    distance_km: float | None = None
    avg_fuel_liters: float | None = None
    despacho_vazio: float | None = None
    despacho_carregado: float | None = None
    notes: str | None = None
    is_active: bool | None = None


class KnownRouteRead(BaseModel):
    id: UUID
    tenant_id: UUID
    origin: str
    destination: str
    distance_km: float
    avg_fuel_liters: float | None
    despacho_vazio: float | None
    despacho_carregado: float | None
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnownRouteDeleteRead(BaseModel):
    deleted: bool
