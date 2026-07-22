import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TenantSequence(Base):
    """Contador de sequência atómico por tenant para documentos não-fiscais (recepções, OSs).
    Usa UPDATE ... RETURNING para zero lock contention e sem janela de corrida.
    """

    __tablename__ = "tenant_sequences"
    __table_args__ = (UniqueConstraint("tenant_id", "entity_type", name="uq_tenant_sequences_entity"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)  # "reception" | "work_order" | "quote"
    current_value: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VehicleReception(Base):
    """Check-in de viatura na oficina."""

    __tablename__ = "vehicle_receptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    reception_number: Mapped[str] = mapped_column(String(80), index=True)  # Sequência leve REC-2026-XXXX
    received_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    odometer_at_reception: Mapped[int] = mapped_column(Integer, default=0)
    reported_issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    personal_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    fuel_level: Mapped[str] = mapped_column(String(20), default="half")  # empty|quarter|half|three_quarter|full
    delivered_by_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    delivered_by_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pickup_authorized_by_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    pickup_authorized_by_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    client_signature_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    estimated_completion_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assigned_work_bay_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_bays.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="received", index=True)
    # received | in_service | ready | delivered | returned_no_service
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReceptionPhoto(Base):
    """Registo append-only de fotos da recepção — prova de estado à entrada."""

    __tablename__ = "reception_photos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    reception_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_receptions.id"), index=True)
    file_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id"))
    caption: Mapped[str | None] = mapped_column(String(200), nullable=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VehicleRelease(Base):
    """Check-out / entrega da viatura ao cliente."""

    __tablename__ = "vehicle_releases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    reception_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicle_receptions.id"), index=True)
    released_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    released_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    odometer_at_release: Mapped[int] = mapped_column(Integer, default=0)
    condition_at_release: Mapped[str | None] = mapped_column(Text, nullable=True)
    picked_up_by_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    picked_up_by_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    override_unauthorized_pickup: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_signature_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    release_type: Mapped[str] = mapped_column(String(30), default="after_service")  # after_service | no_service
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
