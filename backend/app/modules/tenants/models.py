import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(40), default="trial")
    max_vehicles: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    max_drivers: Mapped[int | None] = mapped_column(Integer, nullable=True, default=5)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True, default=3)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_trial: Mapped[bool] = mapped_column(Boolean, default=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_number: Mapped[str | None] = mapped_column(String(40))
    timezone: Mapped[str] = mapped_column(String(80), default="Africa/Maputo")
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    compliance_policy: Mapped[dict | None] = mapped_column(JSON)
    nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TenantDocumentProfile(Base):
    __tablename__ = "tenant_document_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), unique=True, index=True)
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(160), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    province: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="Moçambique")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(160), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bank_nib: Mapped[str | None] = mapped_column(String(60), nullable=True)
    invoice_prefix: Mapped[str] = mapped_column(String(10), default="")
    invoice_seq_padding: Mapped[int] = mapped_column(Integer, default=4)
    invoice_start_seq: Mapped[int] = mapped_column(Integer, default=1)
    per_type_sequences: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_conditions: Mapped[str] = mapped_column(String(80), default="Pronto")
    invoice_footer: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_bank_details: Mapped[bool] = mapped_column(Boolean, default=True)
    show_logo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
