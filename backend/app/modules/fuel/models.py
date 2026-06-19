import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FuelLog(Base):
    __tablename__ = "fuel_logs"
    __table_args__ = (
        CheckConstraint("liters > 0", name="chk_fuel_logs_liters_positive"),
        CheckConstraint("total_cost >= 0", name="chk_fuel_logs_total_cost_non_negative"),
        CheckConstraint("km_at_refuel >= 0", name="chk_fuel_logs_km_at_refuel_non_negative"),
        CheckConstraint(
            "km_since_last IS NULL OR km_since_last >= 0",
            name="chk_fuel_logs_km_since_last_non_negative",
        ),
        CheckConstraint(
            "consumption_l_per_100km IS NULL OR consumption_l_per_100km >= 0",
            name="chk_fuel_logs_consumption_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    fuel_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    station_name: Mapped[str | None] = mapped_column(String(160))
    station_location: Mapped[dict | None] = mapped_column(JSON)
    fuel_type: Mapped[str] = mapped_column(String(30), default="gasoleo")
    liters: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_per_liter: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    km_at_refuel: Mapped[int] = mapped_column(Integer)
    km_since_last: Mapped[int | None] = mapped_column(Integer)
    consumption_l_per_100km: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    odometer_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    payment_method: Mapped[str | None] = mapped_column(String(60))
    payment_reference: Mapped[str | None] = mapped_column(String(120))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    client_captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FuelTank(Base):
    __tablename__ = "fuel_tanks"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_fuel_tanks_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(120))
    fuel_type: Mapped[str] = mapped_column(String(30), default="gasoleo", index=True)
    capacity_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    minimum_stock_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    current_stock_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    average_unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FuelPurchase(Base):
    __tablename__ = "fuel_purchases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "purchase_reference",
            name="uq_fuel_purchases_tenant_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    supplier_name: Mapped[str] = mapped_column(String(160))
    supplier_third_party_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purchase_reference: Mapped[str] = mapped_column(String(100), index=True)
    fuel_type: Mapped[str] = mapped_column(String(30), default="gasoleo", index=True)
    ordered_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(16, 2))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FuelReceipt(Base):
    __tablename__ = "fuel_receipts"
    __table_args__ = (
        Index(
            "uq_fuel_receipts_tenant_purchase_delivery_note",
            "tenant_id",
            "purchase_id",
            "delivery_note_number",
            unique=True,
            postgresql_where=text("delivery_note_number IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuel_purchases.id"), index=True)
    tank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuel_tanks.id"), index=True)
    received_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    delivery_note_number: Mapped[str | None] = mapped_column(String(120))
    delivery_note_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[str] = mapped_column(String(30), default="verified", index=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fuel_movements.id", use_alter=True, name="fk_fuel_receipts_movement_id")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FuelMovement(Base):
    __tablename__ = "fuel_movements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    tank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuel_tanks.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    direction: Mapped[str] = mapped_column(String(10), index=True)
    liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    balance_after_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VehicleRefuel(Base):
    __tablename__ = "vehicle_refuels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    tank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuel_tanks.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trips.id"), index=True)
    liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    odometer_reading: Mapped[int] = mapped_column(Integer)
    refueled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("fuel_movements.id", use_alter=True, name="fk_vehicle_refuels_movement_id")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FuelStockCount(Base):
    __tablename__ = "fuel_stock_counts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    tank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fuel_tanks.id"), index=True)
    theoretical_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    measured_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    variance_liters: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    counted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    counted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    adjustment_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    adjustment_movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(
            "fuel_movements.id",
            use_alter=True,
            name="fk_fuel_stock_counts_adjustment_movement_id",
        )
    )
    adjustment_approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    adjustment_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
