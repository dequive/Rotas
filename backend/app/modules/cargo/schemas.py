from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class LoadPermitCreate(BaseModel):
    contract_id: UUID | None = None
    client_name: str | None = None
    client_reference: str | None = None
    permit_number: str | None = None
    issuer_type: str = "client"
    issuer_name: str | None = None
    district: str | None = None
    location_name: str | None = None
    origin: str | None = None
    destination: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    leg_type: str = "single"
    load_state: str = "loaded"
    file_id: UUID | None = None
    notes: str | None = None


class CargoManifestCreate(BaseModel):
    contract_id: UUID | None = None
    manifest_number: str | None = None
    client_name: str | None = None
    shipper_name: str | None = None
    recipient_name: str | None = None
    cargo_description: str | None = None
    cargo_type: str | None = None
    cargo_class: str | None = None
    package_count: int | None = None
    gross_weight: float | None = None
    origin: str | None = None
    destination: str | None = None
    issued_at: datetime | None = None
    file_id: UUID | None = None


class TransportDocumentCreate(BaseModel):
    contract_id: UUID | None = None
    document_type: str
    document_number: str | None = None
    issuer: str | None = None
    client_name: str | None = None
    issued_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    origin: str | None = None
    destination: str | None = None
    district: str | None = None
    location_name: str | None = None
    file_id: UUID | None = None
    notes: str | None = None


class DeliveryProofCreate(BaseModel):
    contract_id: UUID | None = None
    load_permit_id: UUID | None = None
    load_permit_number: str | None = None
    document_number: str | None = None
    proof_type: str = "client_discharge_note"
    client_type: str = "company"
    receiver_name: str | None = None
    receiver_contact: str | None = None
    delivery_location: str | None = None
    delivered_at: datetime
    cargo_condition: str = "intact"
    quantity_delivered: float | None = None
    validation_method: str | None = None
    notes: str | None = None
    file_id: UUID | None = None


class ValidateDeliveryProofRequest(BaseModel):
    validation_method: str = "manual_review"
    notes: str | None = None


class DisputeDeliveryProofRequest(BaseModel):
    reason: str
    dispute_type: str = Field(..., max_length=50)
    notes: str | None = Field(None, max_length=500)


class DeliveryProofRejectRequest(BaseModel):
    rejection_reason: str = Field(..., min_length=10, max_length=1000)


class ResolveDeliveryProofDisputeRequest(BaseModel):
    outcome: str
    resolution_notes: str
    validation_method: str = "dispute_resolution"
