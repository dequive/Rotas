import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
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


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "plate", name="uq_vehicles_tenant_plate"),
        CheckConstraint("current_km >= 0", name="chk_vehicles_current_km_non_negative"),
        CheckConstraint(
            "max_payload_kg IS NULL OR max_payload_kg >= 0",
            name="chk_vehicles_max_payload_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    plate: Mapped[str] = mapped_column(String(40), index=True)
    chassis: Mapped[str | None] = mapped_column(String(80))
    brand: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str | None] = mapped_column(String(80))
    year: Mapped[int | None] = mapped_column(Integer)
    color: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(30), default="pesado")
    status: Mapped[str] = mapped_column(String(30), default="active")
    current_km: Mapped[int] = mapped_column(Integer, default=0)
    fuel_type: Mapped[str] = mapped_column(String(30), default="gasoleo")
    documents: Mapped[dict | None] = mapped_column(JSON)
    qr_code_hash: Mapped[str | None] = mapped_column(String(255), index=True)
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    avg_consumption_target: Mapped[float | None] = mapped_column(Numeric(10, 2))
    fuel_limit_daily: Mapped[float | None] = mapped_column(Numeric(10, 2))
    max_payload_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class VehicleInsurance(Base):
    __tablename__ = "vehicle_insurances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    policy_number: Mapped[str] = mapped_column(String(80))
    insurer: Mapped[str] = mapped_column(String(120))
    coverage_type: Mapped[str] = mapped_column(String(40))  # civil_liability|comprehensive|cargo
    premium_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    valid_from: Mapped[date] = mapped_column(Date())
    valid_until: Mapped[date] = mapped_column(Date(), index=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    insurance_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vehicle_insurances.id"), index=True
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trip_incidents.id"), nullable=True, index=True
    )
    claim_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    claim_date: Mapped[date] = mapped_column(Date())
    estimated_damage: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    # open | under_review | paid | rejected
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
