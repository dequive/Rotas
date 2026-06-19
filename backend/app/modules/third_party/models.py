import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MzProvince(Base):
    __tablename__ = "mz_provinces"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    name_local: Mapped[str | None] = mapped_column(String(80), nullable=True)
    region: Mapped[str | None] = mapped_column(String(30), nullable=True)


class ThirdParty(Base):
    __tablename__ = "third_parties"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nuit", name="uq_third_parties_tenant_nuit"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    legal_type: Mapped[str | None] = mapped_column(
        String(40), nullable=True, server_default="company"
    )
    nuit: Mapped[str | None] = mapped_column(String(9), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    province_code: Mapped[str | None] = mapped_column(
        String(10), ForeignKey("mz_provinces.code"), nullable=True
    )
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default="active"
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ThirdPartyRole(Base):
    __tablename__ = "third_party_roles"
    __table_args__ = (
        UniqueConstraint(
            "third_party_id", "role_type", name="uq_third_party_roles_tp_role"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    third_party_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("third_parties.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Valid role_type values: fuel_supplier | spare_parts_supplier | service_provider | transport_subcontractor
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    certified_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    certification_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SupplierProfile(Base):
    __tablename__ = "supplier_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    third_party_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("third_parties.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    payment_terms: Mapped[str | None] = mapped_column(String(60), nullable=True)
    preferred_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True, server_default="MZN"
    )
    credit_limit: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    account_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ServiceProviderProfile(Base):
    __tablename__ = "service_provider_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False
    )
    third_party_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("third_parties.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    service_categories: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    coverage_province_codes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    response_time_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rate_per_hour: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
