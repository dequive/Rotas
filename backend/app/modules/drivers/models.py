import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Driver(Base):
    __tablename__ = "drivers"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="chk_drivers_score_range"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    emergency_contact_name: Mapped[str | None] = mapped_column(String(160))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(40))
    license_number: Mapped[str | None] = mapped_column(String(80))
    license_category: Mapped[str | None] = mapped_column(String(40))
    license_valid_until: Mapped[date | None] = mapped_column(Date)
    passport_number: Mapped[str | None] = mapped_column(String(80))
    passport_valid_until: Mapped[date | None] = mapped_column(Date)
    bi_number: Mapped[str | None] = mapped_column(String(80))
    bi_valid_until: Mapped[date | None] = mapped_column(Date)
    inss_number: Mapped[str | None] = mapped_column(String(80))
    employment_type: Mapped[str | None] = mapped_column(String(40))
    documents: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="active")
    score: Mapped[int] = mapped_column(Integer, default=100)
    pairing_code_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    pairing_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("files.id", use_alter=True, name="fk_drivers_photo_file_id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DriverDevice(Base):
    __tablename__ = "driver_devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(160), index=True)
    device_name: Mapped[str | None] = mapped_column(String(160))
    platform: Mapped[str | None] = mapped_column(String(80))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DriverSession(Base):
    __tablename__ = "driver_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    device_id: Mapped[str] = mapped_column(String(160), index=True)
    token_hash: Mapped[str] = mapped_column(String(255), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DriverAdvance(Base):
    """Cash advance issued to a driver before a trip (despacho)."""

    __tablename__ = "driver_advances"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_driver_advances_tenant_ref",
        ),
        CheckConstraint("amount_mzn > 0", name="chk_driver_advances_amount_positive"),
        CheckConstraint(
            "status IN ('issued', 'settled', 'voided')",
            name="chk_driver_advances_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    amount_mzn: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    allowance_mzn: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00"
    )
    expenses_mzn: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), server_default="0.00"
    )
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    status: Mapped[str] = mapped_column(String(20), default="issued")
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    request_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)


class TripSettlement(Base):
    """Post-trip financial settlement: advance vs actual costs."""

    __tablename__ = "trip_settlements"
    __table_args__ = (
        UniqueConstraint("trip_id", name="uq_trip_settlements_trip_id"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="chk_trip_settlements_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"))
    advance_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("driver_advances.id"), nullable=True
    )
    total_costs_mzn: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    advance_amount_mzn: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    balance_mzn: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    pdf_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
