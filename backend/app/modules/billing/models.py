import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BillingDocument(Base):
    __tablename__ = "billing_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    client_name: Mapped[str] = mapped_column(String(160), index=True)
    contract_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    billing_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    billing_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillingItem(Base):
    __tablename__ = "billing_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    billing_document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("billing_documents.id"), index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    load_permit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("load_permits.id"))
    cargo_manifest_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("cargo_manifests.id"))
    transport_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transport_documents.id")
    )
    delivery_proof_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("delivery_proofs.id"))
    client_reference: Mapped[str | None] = mapped_column(String(120))
    origin: Mapped[str | None] = mapped_column(String(160))
    destination: Mapped[str | None] = mapped_column(String(160))
    district: Mapped[str | None] = mapped_column(String(120))
    cargo_description: Mapped[str | None] = mapped_column(Text)
    cargo_class: Mapped[str | None] = mapped_column(String(40))
    load_state: Mapped[str | None] = mapped_column(String(40))
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
