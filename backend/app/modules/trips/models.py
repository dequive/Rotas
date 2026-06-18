import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
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


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trip_orders.id"), index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contracts.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("drivers.id"), index=True)
    origin: Mapped[str] = mapped_column(String(160))
    origin_location: Mapped[dict | None] = mapped_column(JSON)
    destination: Mapped[str] = mapped_column(String(160))
    destination_location: Mapped[dict | None] = mapped_column(JSON)
    cargo_type: Mapped[str | None] = mapped_column(String(120))
    cargo_class: Mapped[str | None] = mapped_column(String(40))
    cargo_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cargo_volume: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    payload_override_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_hazmat: Mapped[bool] = mapped_column(Boolean(), server_default="false", nullable=False, default=False)
    hazmat_class: Mapped[str | None] = mapped_column(String(10), nullable=True)
    un_number: Mapped[str | None] = mapped_column(String(10), nullable=True)
    hazmat_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cargo_volumes: Mapped[int | None] = mapped_column(Integer)
    cargo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    load_state: Mapped[str | None] = mapped_column(String(40))
    requires_load_permit: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_cargo_manifest: Mapped[bool] = mapped_column(Boolean, default=False)
    waybill_number: Mapped[str | None] = mapped_column(String(120))
    km_start: Mapped[int | None] = mapped_column(Integer)
    km_start_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    km_end: Mapped[int | None] = mapped_column(Integer)
    km_end_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    planned_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_departure: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    planned_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recipient_name: Mapped[str | None] = mapped_column(String(160))
    recipient_signature_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    delivery_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    cargo_status: Mapped[str | None] = mapped_column(String(40))
    total_fuel_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_expense_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total_transport_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    actual_revenue: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    actual_margin: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    costs_reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contract_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    billing_status: Mapped[str] = mapped_column(String(40), default="not_billable", index=True)
    billable_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    billing_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing_documents.id")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    operational_close_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        Index(
            "uniq_trips_trip_order",
            "trip_order_id",
            unique=True,
            postgresql_where=trip_order_id.is_not(None),
        ),
        Index(
            "uniq_active_vehicle_trip",
            "tenant_id",
            "vehicle_id",
            unique=True,
            postgresql_where=status.in_(
                ("planned", "dispatch_pending", "dispatched", "in_progress", "delayed", "incident")
            ),
        ),
        Index(
            "uniq_active_driver_trip",
            "tenant_id",
            "driver_id",
            unique=True,
            postgresql_where=status.in_(
                ("planned", "dispatch_pending", "dispatched", "in_progress", "delayed", "incident")
            ),
        ),
    )


class TripStop(Base):
    __tablename__ = "trip_stops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    stop_type: Mapped[str] = mapped_column(String(40), index=True)
    location: Mapped[dict | None] = mapped_column(JSON)
    address: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    expense_category: Mapped[str | None] = mapped_column(String(60))
    stopped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TripCost(Base):
    __tablename__ = "trip_costs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_trip_costs_tenant_request_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    cost_type: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="MZN")
    paid_by: Mapped[str] = mapped_column(String(30), default="company")
    payment_method: Mapped[str | None] = mapped_column(String(60))
    receipt_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"))
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="manual", index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    incurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DispatchClearance(Base):
    __tablename__ = "dispatch_clearances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trip_orders.id"), index=True
    )
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    vehicle_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    driver_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    documents_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    load_permit_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    cargo_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    fuel_advance_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    route_risk_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    clearance_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TripExecutionEvent(Base):
    __tablename__ = "trip_execution_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(50), index=True)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[dict | None] = mapped_column(JSON)
    odometer_reading: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    fuel_level: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    reported_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(40), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TripIncident(Base):
    __tablename__ = "trip_incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id"), index=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id"), index=True)
    driver_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("drivers.id"), index=True)
    incident_type: Mapped[str] = mapped_column(String(50), index=True)
    severity: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    location: Mapped[dict | None] = mapped_column(JSON)
    description: Mapped[str] = mapped_column(Text)
    immediate_action: Mapped[str | None] = mapped_column(Text)
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    financial_impact_estimate: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    delay_minutes: Mapped[int | None] = mapped_column(Integer)
    reported_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class KnownRoute(Base):
    __tablename__ = "known_routes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "origin", "destination", name="uq_known_routes_tenant_od"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    origin: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120))
    distance_km: Mapped[Decimal] = mapped_column(Numeric(10, 1))
    avg_fuel_liters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    despacho_vazio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    despacho_carregado: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
