import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LoadPermit(Base):
    __tablename__ = "load_permits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    client_name: Mapped[str | None] = mapped_column(String(160))
    client_reference: Mapped[str | None] = mapped_column(String(120))
    permit_number: Mapped[str | None] = mapped_column(String(120), index=True)
    issuer_type: Mapped[str] = mapped_column(String(40), default="client")
    issuer_name: Mapped[str | None] = mapped_column(String(160))
    district: Mapped[str | None] = mapped_column(String(120), index=True)
    location_name: Mapped[str | None] = mapped_column(String(160))
    origin: Mapped[str | None] = mapped_column(String(160))
    destination: Mapped[str | None] = mapped_column(String(160))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    leg_type: Mapped[str] = mapped_column(String(40), default="single")
    load_state: Mapped[str] = mapped_column(String(40), default="loaded")
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CargoManifest(Base):
    __tablename__ = "cargo_manifests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    manifest_number: Mapped[str | None] = mapped_column(String(120), index=True)
    issuer_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    client_name: Mapped[str | None] = mapped_column(String(160))
    shipper_name: Mapped[str | None] = mapped_column(String(160))
    recipient_name: Mapped[str | None] = mapped_column(String(160))
    cargo_description: Mapped[str | None] = mapped_column(Text)
    cargo_type: Mapped[str | None] = mapped_column(String(120))
    cargo_class: Mapped[str | None] = mapped_column(String(40))
    package_count: Mapped[int | None] = mapped_column(Integer)
    gross_weight: Mapped[float | None] = mapped_column(Numeric(12, 2))
    origin: Mapped[str | None] = mapped_column(String(160))
    destination: Mapped[str | None] = mapped_column(String(160))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    is_hazmat: Mapped[bool] = mapped_column(
        Boolean(), server_default="false", nullable=False, default=False
    )
    hazmat_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    un_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hazmat_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TransportDocument(Base):
    __tablename__ = "transport_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    document_type: Mapped[str] = mapped_column(String(40), index=True)
    document_number: Mapped[str | None] = mapped_column(String(120), index=True)
    issuer: Mapped[str | None] = mapped_column(String(160))
    client_name: Mapped[str | None] = mapped_column(String(160))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origin: Mapped[str | None] = mapped_column(String(160))
    destination: Mapped[str | None] = mapped_column(String(160))
    district: Mapped[str | None] = mapped_column(String(120))
    location_name: Mapped[str | None] = mapped_column(String(160))
    # OPDOC-01: recipient fields for Guia de Remessa
    recipient_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    recipient_nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # OPDOC-01: flexible metadata per document type (border_post, sadc_cpi_number, etc.)
    extra_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DeliveryProof(Base):
    __tablename__ = "delivery_proofs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    load_permit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("load_permits.id"))
    load_permit_number: Mapped[str | None] = mapped_column(String(120), index=True)
    document_number: Mapped[str | None] = mapped_column(String(120), index=True)
    proof_type: Mapped[str] = mapped_column(String(50), default="client_discharge_note")
    client_type: Mapped[str] = mapped_column(String(30), default="company")
    receiver_name: Mapped[str | None] = mapped_column(String(160))
    receiver_contact: Mapped[str | None] = mapped_column(String(80))
    delivery_location: Mapped[str | None] = mapped_column(String(200))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cargo_condition: Mapped[str] = mapped_column(String(30), default="intact")
    quantity_delivered: Mapped[float | None] = mapped_column(Numeric(12, 2))
    validation_method: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    created_by_driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("drivers.id"))
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    # SM-03: State machine fields
    # Valid status values: pending | accepted | rejected | disputed | resolved
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    dispute_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
