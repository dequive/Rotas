from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WarrantyCreate(BaseModel):
    work_order_id: UUID
    vehicle_id: UUID
    client_id: UUID | None = None
    warranty_type: str = "full_service"  # parts | labor | full_service
    duration_months: int = Field(ge=1, default=6)
    duration_km: int | None = Field(ge=0, default=None)
    km_at_service: int = Field(ge=0, default=0)
    notes: str | None = None

    @field_validator("warranty_type")
    @classmethod
    def validate_warranty_type(cls, v: str) -> str:
        allowed = {"parts", "labor", "full_service"}
        if v.lower() not in allowed:
            raise ValueError(f"warranty_type must be one of {sorted(allowed)}")
        return v.lower()


class WarrantyClaimRequest(BaseModel):
    current_km: int = Field(ge=0)
    claim_reason: str
