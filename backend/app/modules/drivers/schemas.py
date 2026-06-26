import re
from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_validator


def _normalize_phone(v: str | None) -> str | None:
    if not v:
        return v
    cleaned = re.sub(r"[\s\-\(\)]", "", v)
    if not cleaned:
        return None
    
    # If 9 digits starting with Moz operator
    if len(cleaned) == 9 and cleaned[:2] in {"82", "83", "84", "85", "86", "87"}:
        return f"+258{cleaned}"
    # If starts with 258 and 12 digits
    if cleaned.startswith("258") and len(cleaned) == 12:
        return f"+{cleaned}"
    
    # Generic validation: check it's alphanumeric/plus and reasonable length
    if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
        raise ValueError("Invalid phone number format. Must be a valid number.")
    return cleaned


def _normalize_email(v: str | None) -> str | None:
    if not v:
        return v
    cleaned = v.strip().lower()
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", cleaned):
        raise ValueError("Invalid email address format.")
    return cleaned


def _validate_future_date(v: date | None) -> date | None:
    if v is not None and v < date.today():
        raise ValueError("Date must be today or in the future.")
    return v


class DriverCreate(BaseModel):
    full_name: str
    phone: str | None = None
    email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    license_number: str | None = None
    license_category: str | None = None
    license_valid_until: date | None = None
    passport_number: str | None = None
    passport_valid_until: date | None = None
    bi_number: str | None = None
    bi_valid_until: date | None = None
    inss_number: str | None = None
    employment_type: str | None = None
    documents: dict | None = None

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _normalize_email(v)

    @field_validator("license_valid_until", "passport_valid_until", "bi_valid_until")
    @classmethod
    def validate_dates(cls, v: date | None) -> date | None:
        return _validate_future_date(v)


class DriverPatch(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    status: str | None = None
    license_number: str | None = None
    license_category: str | None = None
    license_valid_until: date | None = None
    passport_number: str | None = None
    passport_valid_until: date | None = None
    bi_number: str | None = None
    bi_valid_until: date | None = None
    inss_number: str | None = None
    employment_type: str | None = None
    documents: dict | None = None

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        return _normalize_phone(v)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        return _normalize_email(v)

    @field_validator("license_valid_until", "passport_valid_until", "bi_valid_until")
    @classmethod
    def validate_dates(cls, v: date | None) -> date | None:
        return _validate_future_date(v)


class DriverRead(BaseModel):
    id: UUID
    tenant_id: UUID
    full_name: str
    status: str


class DriverDocumentRenewalRequest(BaseModel):
    valid_until: date
    file_id: UUID | None = None
    reference: str | None = None
    notes: str | None = None

    @field_validator("valid_until")
    @classmethod
    def validate_expiry_date(cls, v: date) -> date:
        return _validate_future_date(v)

