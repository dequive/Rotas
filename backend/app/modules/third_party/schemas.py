from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


# ── ThirdParty ────────────────────────────────────────────────────────────────


class ThirdPartyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    trade_name: Optional[str] = Field(None, max_length=160)
    legal_type: Optional[str] = Field(None, pattern="^(individual|company)$")
    nuit: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = Field(None, max_length=30)
    province_code: Optional[str] = Field(None, max_length=10)
    address: Optional[str] = None
    status: str = Field("active", pattern="^(active|inactive|suspended)$")
    notes: Optional[str] = None


class ThirdPartyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=160)
    trade_name: Optional[str] = Field(None, max_length=160)
    legal_type: Optional[str] = Field(None, pattern="^(individual|company)$")
    nuit: Optional[str] = Field(None, max_length=20)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = Field(None, max_length=30)
    province_code: Optional[str] = Field(None, max_length=10)
    address: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|inactive|suspended)$")
    is_verified: Optional[bool] = None
    notes: Optional[str] = None


class ThirdPartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    trade_name: Optional[str]
    legal_type: Optional[str]
    nuit: Optional[str]
    contact_email: Optional[str]
    contact_phone: Optional[str]
    province_code: Optional[str]
    address: Optional[str]
    status: str
    is_verified: bool
    verified_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── Roles ─────────────────────────────────────────────────────────────────────

VALID_ROLE_TYPES = {
    "fuel_supplier",
    "spare_parts_supplier",
    "service_provider",
    "transport_subcontractor",
}


class RoleCreate(BaseModel):
    role_type: str  # validated against VALID_ROLE_TYPES in service
    is_active: bool = True
    certified_at: Optional[date] = None
    certification_ref: Optional[str] = Field(None, max_length=120)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    third_party_id: UUID
    role_type: str
    is_active: bool
    certified_at: Optional[date]
    certification_ref: Optional[str]
    created_at: datetime


# ── SupplierProfile ───────────────────────────────────────────────────────────


class SupplierProfileCreate(BaseModel):
    payment_terms: Optional[str] = Field(None, max_length=80)
    preferred_currency: Optional[str] = Field("MZN", max_length=3)
    credit_limit: Optional[Decimal] = None
    account_number: Optional[str] = Field(None, max_length=60)
    bank_name: Optional[str] = Field(None, max_length=120)


class SupplierProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    third_party_id: UUID
    payment_terms: Optional[str]
    preferred_currency: Optional[str]
    credit_limit: Optional[Decimal]
    account_number: Optional[str]
    bank_name: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── ServiceProviderProfile ────────────────────────────────────────────────────


class ServiceProviderProfileCreate(BaseModel):
    service_categories: Optional[list[str]] = None
    coverage_province_codes: Optional[list[str]] = None
    response_time_hours: Optional[int] = None
    rate_per_hour: Optional[Decimal] = None


class ServiceProviderProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    third_party_id: UUID
    service_categories: Optional[list]
    coverage_province_codes: Optional[list]
    response_time_hours: Optional[int]
    rate_per_hour: Optional[Decimal]
    created_at: datetime
    updated_at: datetime


# ── Province ──────────────────────────────────────────────────────────────────


class ProvinceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    name_local: Optional[str]
    region: Optional[str]


# ── DriverVehicleAssignment ───────────────────────────────────────────────────


class AssignmentCreate(BaseModel):
    driver_id: UUID
    vehicle_id: UUID
    assignment_type: Optional[str] = Field(
        None, pattern="^(primary|temporary|maintenance_only)$"
    )
    notes: Optional[str] = None


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    driver_id: UUID
    vehicle_id: UUID
    assigned_at: datetime
    unassigned_at: Optional[datetime]
    assignment_type: Optional[str]
    notes: Optional[str]
    assigned_by: Optional[UUID]
    created_at: datetime


# ── OperationalDocument ───────────────────────────────────────────────────────

VALID_SUBJECT_TYPES = {"driver", "vehicle", "third_party", "client", "contract"}


class DocumentCreate(BaseModel):
    subject_type: str  # validated against VALID_SUBJECT_TYPES in service
    subject_id: UUID
    document_type: str = Field(..., max_length=60)
    file_id: Optional[UUID] = None
    document_number: Optional[str] = Field(None, max_length=80)
    issued_at: Optional[date] = None
    expiry_date: Optional[date] = None
    issuing_authority: Optional[str] = Field(None, max_length=160)
    notes: Optional[str] = None


class DocumentVerify(BaseModel):
    verification_status: str = Field(..., pattern="^(verified|rejected)$")
    notes: Optional[str] = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    subject_type: str
    subject_id: UUID
    document_type: str
    file_id: Optional[UUID]
    document_number: Optional[str]
    issued_at: Optional[date]
    expiry_date: Optional[date]
    issuing_authority: Optional[str]
    verification_status: str
    verified_by: Optional[UUID]
    verified_at: Optional[datetime]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


# ── PartyDirectory ────────────────────────────────────────────────────────────


class PartyDirectoryEntry(BaseModel):
    subject_id: UUID
    subject_type: str
    name: str
    status: str
