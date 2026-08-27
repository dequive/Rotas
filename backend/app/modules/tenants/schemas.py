from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

UUIDType = UUID


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    plan: str
    product_modules: list[str] = ["tms"]
    max_vehicles: int | None = None
    max_drivers: int | None = None
    max_users: int | None = None
    is_active: bool
    is_trial: bool
    trial_ends_at: datetime | None = None
    whatsapp_number: str | None = None
    timezone: str
    currency: str
    compliance_policy: dict | None = None
    created_at: datetime
    updated_at: datetime


class TenantPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: str | None = None
    currency: str | None = None
    whatsapp_number: str | None = None
    compliance_policy: dict | None = None


class ProductModulesUpdate(BaseModel):
    product_modules: list[str]


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


class DriverDespachoTableRead(BaseModel):
    """Stored despacho table.

    Adds the provenance fields the service stamps on write (`entry_mode`) or that
    other writers may carry (`source`). `extra="allow"` keeps the stored JSON
    intact — the table lives inside `tenant.compliance_policy` and must never be
    silently truncated by the response contract.
    """

    model_config = ConfigDict(extra="allow")

    enabled: bool = True
    table_name: str
    table_reference: str | None = None
    currency: str = "MZN"
    effective_from: str | None = None
    min_long_course_km: float = 100
    tiers: list[DriverDespachoTableTier]
    entry_mode: str | None = None
    source: str | None = None


class DriverDespachoTableResponse(BaseModel):
    """Current despacho table for the tenant; `table` is null until configured."""

    configured: bool
    table: DriverDespachoTableRead | None = None


class TenantDocumentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUIDType
    tenant_id: UUIDType
    logo_file_id: UUIDType | None = None
    legal_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    province: str | None = None
    country: str = "Moçambique"
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bank_nib: str | None = None
    invoice_prefix: str = ""
    invoice_seq_padding: int = 4
    invoice_start_seq: int = 1
    per_type_sequences: bool = False
    payment_conditions: str = "Pronto"
    invoice_footer: str | None = None
    show_bank_details: bool = True
    show_logo: bool = True
    created_at: datetime
    updated_at: datetime


class TenantDocumentProfileUpdate(BaseModel):
    logo_file_id: UUIDType | None = None
    legal_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bank_nib: str | None = None
    invoice_prefix: str | None = None
    invoice_seq_padding: int | None = None
    invoice_start_seq: int | None = None
    per_type_sequences: bool | None = None
    payment_conditions: str | None = None
    invoice_footer: str | None = None
    show_bank_details: bool | None = None
    show_logo: bool | None = None
