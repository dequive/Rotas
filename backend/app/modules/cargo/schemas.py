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


# OPDOC-02: Guia de Remessa
class GuiaRemessaCreate(BaseModel):
    contract_id: UUID | None = None
    client_name: str = Field(..., min_length=1, max_length=160)
    recipient_name: str = Field(..., min_length=1, max_length=160)
    recipient_nuit: str | None = Field(None, max_length=20)
    origin: str = Field(..., min_length=1, max_length=160)
    destination: str = Field(..., min_length=1, max_length=160)
    issuer: str | None = Field(None, max_length=160)
    document_number: str | None = Field(None, max_length=80)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    notes: str | None = None
    cargo_description: str | None = None
    package_count: int | None = None
    gross_weight: float | None = None


# OPDOC-03: Carta de Porte Internacional
class CartaPorteCreate(BaseModel):
    contract_id: UUID | None = None
    client_name: str = Field(..., min_length=1, max_length=160)
    recipient_name: str | None = Field(None, max_length=160)
    recipient_nuit: str | None = Field(None, max_length=20)
    origin: str = Field(..., min_length=1, max_length=160)
    destination: str = Field(..., min_length=1, max_length=160)
    issuer: str | None = Field(None, max_length=160)
    document_number: str | None = Field(None, max_length=80)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    notes: str | None = None
    sadc_cpi_number: str | None = Field(None, max_length=80)
    border_post: str | None = Field(None, max_length=80)
    country_destination: str | None = Field(None, max_length=80)


# OPDOC-04: DAV / Declaração de Aprovação de Viagem (digital record, no PDF)
class DAVCreate(BaseModel):
    contract_id: UUID | None = None
    document_number: str | None = Field(None, max_length=80)
    issuer: str | None = Field(None, max_length=160)
    authorization_code: str = Field(..., min_length=1, max_length=80)
    origin: str | None = Field(None, max_length=160)
    destination: str | None = Field(None, max_length=160)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    notes: str | None = None


# Declaração de Carga Perigosa — INATTER/hazmat declaration (digital record, no PDF)
class DeclaracaoCargaPerisgosaCreate(BaseModel):
    contract_id: UUID | None = None
    document_number: str | None = Field(None, max_length=80)
    issuer: str | None = Field(None, max_length=160)
    hazmat_class: str = Field(..., min_length=1, max_length=10, description="ADR class e.g. '3', '8'")
    un_number: str | None = Field(None, max_length=10, description="UN number e.g. 'UN1203'")
    hazmat_description: str = Field(..., min_length=1, max_length=300)
    authorization_code: str | None = Field(None, max_length=80)
    origin: str | None = Field(None, max_length=160)
    destination: str | None = Field(None, max_length=160)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    notes: str | None = None
