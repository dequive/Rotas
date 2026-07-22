import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WorkshopQuote(Base):
    """Orçamento de reparação/manutenção da oficina."""
    __tablename__ = "workshop_quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clients.id"), nullable=True, index=True)
    reception_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicle_receptions.id"), nullable=True, index=True)
    quote_number: Mapped[str] = mapped_column(String(80), index=True)  # ORC-2026-XXXX
    is_supplemental: Mapped[bool] = mapped_column(default=False)
    related_work_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # draft | sent | approved | rejected | expired | converted
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    labor_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    parts_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tax_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_photo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    client_signature_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    acceptance_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)  # presencial | whatsapp | telefone | assinatura_digital
    accepted_by_person_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkshopQuoteItem(Base):
    """Item individual do orçamento (mão de obra ou peça)."""
    __tablename__ = "workshop_quote_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    quote_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop_quotes.id", ondelete="CASCADE"), index=True)
    item_type: Mapped[str] = mapped_column(String(20), default="labor")  # labor | part
    description: Mapped[str] = mapped_column(String(255))
    part_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spare_parts_inventory.id"), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    warranty_months: Mapped[int] = mapped_column(Integer, default=0)
    warranty_km: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
