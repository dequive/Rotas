import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
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
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    trip_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trips.id"), index=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("trip_incidents.id"), index=True
    )
    request_type: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal", index=True)
    description: Mapped[str] = mapped_column(Text)
    odometer_reading: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "work_order_number", name="uq_work_orders_tenant_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    maintenance_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("maintenance_requests.id"), index=True
    )
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("maintenance_plans.id"), index=True, nullable=True
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    work_order_number: Mapped[str] = mapped_column(String(80), index=True)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    planned_work: Mapped[str] = mapped_column(Text)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    actual_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkOrderTask(Base):
    __tablename__ = "work_order_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SparePartInventory(Base):
    __tablename__ = "spare_parts_inventory"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_spare_parts_inventory_tenant_sku"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(30), default="unit")
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    minimum_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    average_unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SparePartMovement(Base):
    __tablename__ = "spare_part_movements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_spare_part_movements_tenant_request_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spare_parts_inventory.id"), index=True
    )
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    direction: Mapped[str] = mapped_column(String(10), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    balance_after_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MaintenancePartUsed(Base):
    __tablename__ = "maintenance_parts_used"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_maintenance_parts_used_tenant_request_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id"), index=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("spare_parts_inventory.id"), index=True
    )
    movement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("spare_part_movements.id"), index=True
    )
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    notes: Mapped[str | None] = mapped_column(Text)


class WorkshopTool(Base):
    __tablename__ = "workshop_tools"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_workshop_tools_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    calibration_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ToolCheckout(Base):
    __tablename__ = "tool_checkouts"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "checkout_reference",
            name="uq_tool_checkouts_tenant_checkout_reference",
        ),
        Index(
            "uq_tool_checkouts_active_tool",
            "tenant_id",
            "tool_id",
            unique=True,
            postgresql_where=text("status = 'checked_out'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    tool_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop_tools.id"), index=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id"), index=True)
    checkout_reference: Mapped[str] = mapped_column(String(120), index=True)
    checked_out_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    checked_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="checked_out", index=True)
    return_reference: Mapped[str | None] = mapped_column(String(120), index=True)
    returned_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_condition: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MaintenancePlan(Base):
    __tablename__ = "maintenance_plans"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_maintenance_plans_tenant_request_reference",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160))
    interval_km: Mapped[int | None] = mapped_column(Integer)
    interval_days: Mapped[int | None] = mapped_column(Integer)
    next_due_km: Mapped[int | None] = mapped_column(Integer, index=True)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedule"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "plan_id",
            "status",
            name="uq_maintenance_schedule_tenant_plan_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maintenance_plans.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    due_km: Mapped[int | None] = mapped_column(Integer)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="overdue", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
