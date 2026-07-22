from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReceptionCreate(BaseModel):
    vehicle_id: UUID
    client_id: UUID | None = None
    odometer_at_reception: int = Field(ge=0, default=0)
    reported_issues: str | None = None
    visual_condition: str | None = None
    personal_items: str | None = None
    fuel_level: str = "half"
    delivered_by_name: str | None = None
    delivered_by_phone: str | None = None
    pickup_authorized_by_name: str | None = None
    pickup_authorized_by_phone: str | None = None
    client_signature_file_id: UUID | None = None
    estimated_completion_at: datetime | None = None

    @field_validator("fuel_level")
    @classmethod
    def validate_fuel_level(cls, v: str) -> str:
        allowed = {"empty", "quarter", "half", "three_quarter", "full"}
        if v not in allowed:
            raise ValueError(f"fuel_level must be one of {sorted(allowed)}")
        return v


class ReceptionPhotoCreate(BaseModel):
    file_id: UUID
    caption: str | None = None


class ReceptionStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"received", "in_service", "ready", "delivered", "returned_no_service"}
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v


class VehicleReleaseCreate(BaseModel):
    odometer_at_release: int = Field(ge=0, default=0)
    condition_at_release: str | None = None
    picked_up_by_name: str | None = None
    picked_up_by_phone: str | None = None
    override_unauthorized_pickup: bool = False
    override_reason: str | None = None
    client_signature_file_id: UUID | None = None
    release_type: str = "after_service"
    notes: str | None = None

    @field_validator("release_type")
    @classmethod
    def validate_release_type(cls, v: str) -> str:
        allowed = {"after_service", "no_service"}
        if v not in allowed:
            raise ValueError(f"release_type must be one of {sorted(allowed)}")
        return v
