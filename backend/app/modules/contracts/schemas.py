from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ContractCreate(BaseModel):
    client_name: str
    contract_reference: str
    title: str | None = None
    service_type: str = "cargo_transport"
    billing_cycle: str = "monthly"
    billing_basis: str = "trip"
    currency: str = "MZN"
    default_unit_price: float | None = None
    requires_load_permit: bool = True
    requires_delivery_proof: bool = True
    requires_cargo_manifest_for_manufactured_goods: bool = True
    pricing_rules: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    notes: str | None = None


class ContractPatch(BaseModel):
    client_name: str | None = None
    title: str | None = None
    status: str | None = None
    billing_cycle: str | None = None
    billing_basis: str | None = None
    default_unit_price: float | None = None
    requires_load_permit: bool | None = None
    requires_delivery_proof: bool | None = None
    requires_cargo_manifest_for_manufactured_goods: bool | None = None
    pricing_rules: dict | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    notes: str | None = None


class ContractResponse(ContractCreate):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
