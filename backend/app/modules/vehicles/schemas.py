from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


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

    @field_validator("valid_until")
    @classmethod
    def validate_expiry_date(cls, v: date) -> date:
        if v < date.today():
            raise ValueError("Document expiration date must be today or in the future.")
        return v


# ── Insurance schemas ─────────────────────────────────────────────────────────


class VehicleInsuranceCreate(BaseModel):
    policy_number: str = Field(..., max_length=80)
    insurer: str = Field(..., max_length=120)
    coverage_type: str = Field(..., pattern="^(civil_liability|comprehensive|cargo)$")
    premium_amount: Decimal | None = Field(None, gt=0)
    valid_from: date
    valid_until: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_insurance_dates(self) -> "VehicleInsuranceCreate":
        if self.valid_until <= self.valid_from:
            raise ValueError("Insurance valid_until must be after valid_from.")
        return self



class VehicleInsuranceRead(BaseModel):
    id: UUID
    tenant_id: UUID
    vehicle_id: UUID
    policy_number: str
    insurer: str
    coverage_type: str
    premium_amount: Decimal | None
    valid_from: date
    valid_until: date
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InsuranceClaimCreate(BaseModel):
    claim_number: str | None = None
    claim_date: date
    estimated_damage: Decimal | None = None
    incident_id: UUID | None = None
    notes: str | None = None


class InsuranceClaimRead(BaseModel):
    id: UUID
    tenant_id: UUID
    vehicle_id: UUID
    insurance_id: UUID
    incident_id: UUID | None
    claim_number: str | None
    claim_date: date
    estimated_damage: Decimal | None
    status: str
    resolved_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InsuranceClaimStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(open|under_review|paid|rejected)$")
    notes: str | None = None
