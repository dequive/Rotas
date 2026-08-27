import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


# ── ThirdParty ────────────────────────────────────────────────────────────────


class ThirdPartyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    trade_name: str | None = Field(None, max_length=160)
    legal_type: str | None = Field(None, pattern="^(individual|company)$")
    nuit: str | None = Field(None, max_length=20)
    contact_email: str | None = None
    contact_phone: str | None = Field(None, max_length=30)
    province_code: str | None = Field(None, max_length=10)
    address: str | None = None
    status: str = Field("active", pattern="^(active|inactive|suspended)$")
    notes: str | None = None

    @field_validator("nuit")
    @classmethod
    def validate_nuit(cls, v: str | None) -> str | None:
        return _normalize_nuit(v)

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _normalize_email(v)


class ThirdPartyUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=160)
    trade_name: str | None = Field(None, max_length=160)
    legal_type: str | None = Field(None, pattern="^(individual|company)$")
    nuit: str | None = Field(None, max_length=20)
    contact_email: str | None = None
    contact_phone: str | None = Field(None, max_length=30)
    province_code: str | None = Field(None, max_length=10)
    address: str | None = None
    status: str | None = Field(None, pattern="^(active|inactive|suspended)$")
    is_verified: bool | None = None
    notes: str | None = None

    @field_validator("nuit")
    @classmethod
    def validate_nuit(cls, v: str | None) -> str | None:
        return _normalize_nuit(v)

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("contact_email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _normalize_email(v)


class ThirdPartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    trade_name: str | None
    legal_type: str | None
    nuit: str | None
    contact_email: str | None
    contact_phone: str | None
    province_code: str | None
    address: str | None
    activity_code: str | None = None
    sector: str | None = None
    status: str
    is_verified: bool
    verified_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    average_score: Decimal | None = None


# ── Roles ─────────────────────────────────────────────────────────────────────

VALID_ROLE_TYPES = {
    "client",
    "fuel_supplier",
    "spare_parts_supplier",
    "service_provider",
    "transport_subcontractor",
}


class RoleCreate(BaseModel):
    role_type: str  # validated against VALID_ROLE_TYPES in service
    is_active: bool = True
    certified_at: date | None = None
    certification_ref: str | None = Field(None, max_length=120)


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    third_party_id: UUID
    role_type: str
    is_active: bool
    certified_at: date | None
    certification_ref: str | None
    created_at: datetime


# ── SupplierProfile ───────────────────────────────────────────────────────────


class SupplierProfileCreate(BaseModel):
    payment_terms: str | None = Field(None, max_length=80)
    preferred_currency: str | None = Field("MZN", max_length=3)
    credit_limit: Decimal | None = None
    account_number: str | None = Field(None, max_length=60)
    bank_name: str | None = Field(None, max_length=120)


class SupplierProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    third_party_id: UUID
    payment_terms: str | None
    preferred_currency: str | None
    credit_limit: Decimal | None
    account_number: str | None
    bank_name: str | None
    created_at: datetime
    updated_at: datetime


# ── ServiceProviderProfile ────────────────────────────────────────────────────


class ServiceProviderProfileCreate(BaseModel):
    service_categories: list[str] | None = None
    coverage_province_codes: list[str] | None = None
    response_time_hours: int | None = None
    rate_per_hour: Decimal | None = None


class ServiceProviderProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    third_party_id: UUID
    service_categories: list | None
    coverage_province_codes: list | None
    response_time_hours: int | None
    rate_per_hour: Decimal | None
    created_at: datetime
    updated_at: datetime


# ── Province ──────────────────────────────────────────────────────────────────


class ProvinceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    name_local: str | None
    region: str | None


# ── DriverVehicleAssignment ───────────────────────────────────────────────────


class AssignmentCreate(BaseModel):
    driver_id: UUID
    vehicle_id: UUID
    assignment_type: str | None = Field(None, pattern="^(primary|temporary|maintenance_only)$")
    notes: str | None = None


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    driver_id: UUID
    driver_name: str | None = None
    vehicle_id: UUID
    vehicle_plate: str | None = None
    assigned_at: datetime
    unassigned_at: datetime | None
    assignment_type: str | None
    notes: str | None
    assigned_by: UUID | None
    created_at: datetime


# ── OperationalDocument ───────────────────────────────────────────────────────

VALID_SUBJECT_TYPES = {"driver", "vehicle", "third_party", "client", "contract"}


class DocumentCreate(BaseModel):
    subject_type: str  # validated against VALID_SUBJECT_TYPES in service
    subject_id: UUID
    document_type: str = Field(..., max_length=60)
    file_id: UUID | None = None
    document_number: str | None = Field(None, max_length=80)
    issued_at: date | None = None
    expiry_date: date | None = None
    issuing_authority: str | None = Field(None, max_length=160)
    notes: str | None = None


class DocumentVerify(BaseModel):
    verification_status: str = Field(..., pattern="^(verified|rejected)$")
    notes: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    subject_type: str
    subject_id: UUID
    document_type: str
    file_id: UUID | None
    document_number: str | None
    issued_at: date | None
    expiry_date: date | None
    issuing_authority: str | None
    verification_status: str
    verified_by: UUID | None
    verified_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# ── PartyDirectory ────────────────────────────────────────────────────────────


class PartyDirectoryEntry(BaseModel):
    subject_id: UUID
    subject_type: str
    name: str
    status: str
    roles: list[str] | None = None


# ── Contacts ──────────────────────────────────────────────────────────────────


class ContactCreate(BaseModel):
    name: str
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    is_primary: bool = False


# ── Payments ──────────────────────────────────────────────────────────────────


VALID_CURRENCIES = {"MZN", "USD", "ZAR", "EUR"}


class PaymentCreate(BaseModel):
    amount: Decimal
    currency: str = "MZN"
    payment_date: date | None = None
    description: str | None = None
    fuel_purchase_id: UUID | None = None
    work_order_id: UUID | None = None

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    def model_post_init(self, __context: object) -> None:
        if self.currency not in VALID_CURRENCIES:
            raise ValueError(
                f"currency must be one of {sorted(VALID_CURRENCIES)}, got '{self.currency}'"
            )


# ── Evaluations ───────────────────────────────────────────────────────────────


class EvaluationCriterion(BaseModel):
    name: str
    weight: float  # must sum to 1.0 across all criteria
    score: float  # 0–10 scale


class EvaluationCreate(BaseModel):
    evaluation_date: date | None = None
    criteria: list[dict]  # list of EvaluationCriterion dicts
    notes: str | None = None


# ── Response contracts (F7.2) ─────────────────────────────────────────────────
# Mirrors the `service.serialize_*` helpers so the OpenAPI contract exposes a
# non-empty 2xx schema for every operation the Manager calls.


class ContactOut(BaseModel):
    id: UUID
    third_party_id: UUID
    name: str
    role: str | None = None
    phone: str | None = None
    email: str | None = None
    is_primary: bool
    created_at: datetime


class LedgerEntryOut(BaseModel):
    id: UUID
    third_party_id: UUID
    entry_type: str
    amount: Decimal
    currency: str
    source_type: str | None = None
    source_id: UUID | None = None
    description: str | None = None
    entry_date: date
    created_at: datetime


class PaymentRecordOut(BaseModel):
    id: UUID
    third_party_id: UUID
    entry_type: str
    amount: Decimal
    currency: str
    source_type: str | None = None
    source_id: UUID | None = None
    description: str | None = None
    entry_date: date
    created_at: datetime


PaymentOut = PaymentRecordOut


class LedgerCurrencyBalance(BaseModel):
    total_credits: Decimal
    total_debits: Decimal
    balance: Decimal


class SupplierAccountOut(BaseModel):
    third_party_id: UUID
    total_debits: Decimal
    total_credits: Decimal
    balance: Decimal
    balances: dict[str, LedgerCurrencyBalance]
    entries: list[LedgerEntryOut]
    date_from: date | None = None
    date_to: date | None = None
    opening_balance: Decimal | None = None


class EvaluationOut(BaseModel):
    id: UUID
    third_party_id: UUID
    evaluated_by: UUID | None = None
    evaluation_date: date
    criteria: list[dict]
    score: Decimal
    notes: str | None = None
    created_at: datetime


class EvaluationListOut(BaseModel):
    average_score: Decimal | None = None
    evaluations: list[EvaluationOut]
