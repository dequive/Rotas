from datetime import date
from uuid import UUID

from pydantic import BaseModel


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
