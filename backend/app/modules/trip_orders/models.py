import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TripOrder(Base):
    __tablename__ = "trip_orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    customer_reference: Mapped[str | None] = mapped_column(String(160), index=True)
    origin: Mapped[str] = mapped_column(String(160))
    destination: Mapped[str] = mapped_column(String(160))
    cargo_type: Mapped[str | None] = mapped_column(String(120))
    cargo_description: Mapped[str | None] = mapped_column(Text)
    estimated_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_volume: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cargo_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    cargo_risk_level: Mapped[str] = mapped_column(String(30), default="normal")
    requested_pickup_date: Mapped[date] = mapped_column(Date, index=True)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date)
    sla_pickup_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_delivery_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicles.id"), index=True
    )
    assigned_driver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drivers.id"), index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    # SM-04: DispatchClearance state machine fields
    rejection_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    clearance_sla_hours: Mapped[int | None] = mapped_column(Integer(), nullable=True, default=24)
    priority: Mapped[str] = mapped_column(String(30), default="normal", index=True)
    estimated_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_fuel_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_toll_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    estimated_revenue: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    source: Mapped[str] = mapped_column(String(40), default="manual")
    load_permit_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("load_permits.id"), index=True
    )
    requires_load_permit: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_police_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_customs_clearance: Mapped[bool] = mapped_column(Boolean, default=False)
    operational_notes: Mapped[str | None] = mapped_column(Text)
    commercial_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
