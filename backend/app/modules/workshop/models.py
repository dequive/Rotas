import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
    incident_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trip_incidents.id"), index=True)
    request_type: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[str] = mapped_column(String(30), default="normal", index=True)
    description: Mapped[str] = mapped_column(Text)
    odometer_reading: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MaintenanceRequestNote(Base):
    __tablename__ = "maintenance_request_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    maintenance_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("maintenance_requests.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "work_order_number", name="uq_work_orders_tenant_number"),
        CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'quality_check', 'completed', 'closed', 'cancelled')",
            name="chk_work_orders_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    maintenance_request_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("maintenance_requests.id"), index=True, nullable=True
    )
    governance_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True, nullable=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("maintenance_plans.id"), index=True, nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id"), index=True, nullable=True)
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
    quality_checked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    quality_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_required", server_default="not_required", index=True
    )
    billing_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("billing_documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    billing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_provider_third_party_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), server_default="0", nullable=False)
    reception_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("vehicle_receptions.id"), nullable=True, index=True
    )
    work_bay_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_bays.id"), nullable=True, index=True)
    origin_type: Mapped[str] = mapped_column(
        String(30), server_default="direct", default="direct"
    )  # direct | reception | quote | warranty
    warranty_original_wo_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_orders.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkOrderTask(Base):
    __tablename__ = "work_order_tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name="chk_work_order_tasks_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    completed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", name="fk_work_order_tasks_assigned_to_users"),
        nullable=True,
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SparePartInventory(Base):
    __tablename__ = "spare_parts_inventory"
    __table_args__ = (UniqueConstraint("tenant_id", "sku", name="uq_spare_parts_inventory_tenant_sku"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(30), default="unit")
    current_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), default=0)
    minimum_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3), default=0)
    average_unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    shelf_location: Mapped[str | None] = mapped_column(String(80), nullable=True)
    supplier_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    supplier_third_party_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reorder_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"), index=True)
    movement_type: Mapped[str] = mapped_column(String(40), index=True)
    direction: Mapped[str] = mapped_column(String(10), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3))
    balance_after_quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    source_type: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"), index=True)
    movement_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("spare_part_movements.id"), index=True)
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 3))
    returned_quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 3), nullable=False, default=0, server_default="0"
    )
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    net_total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    issued_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)


class PartReservation(Base):
    """Reserva de stock vinculada a um orçamento aceite ou Ordem de Serviço."""

    __tablename__ = "part_reservations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"), index=True)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_quotes.id"), index=True, nullable=True)
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_orders.id"), index=True, nullable=True)
    quantity_reserved: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="active", index=True
    )  # active | consumed | released | active_backorder
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SparePartRequisition(Base):
    """Requisição interna de peças/óleos de um mecânico ao fiel de armazém para uma OS."""

    __tablename__ = "spare_part_requisitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id"), index=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"), index=True)
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    quantity_requested: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_issued: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending | issued | rejected | cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkshopPurchaseOrder(Base):
    """Encomenda de compra de peças a um Fornecedor Terceiro (ThirdParty)."""

    __tablename__ = "workshop_purchase_orders"
    __table_args__ = (UniqueConstraint("tenant_id", "po_number", name="uq_workshop_purchase_orders_tenant_number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    supplier_third_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("third_parties.id"), index=True)
    po_number: Mapped[str] = mapped_column(String(80), index=True)  # PO-2026-XXXX
    status: Mapped[str] = mapped_column(
        String(30), default="draft", index=True
    )  # draft | ordered | partially_received | received | cancelled
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkshopPurchaseOrderItem(Base):
    """Item de uma encomenda de compra de peças."""

    __tablename__ = "workshop_purchase_order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workshop_purchase_orders.id", ondelete="CASCADE"), index=True
    )
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"), index=True)
    quantity_ordered: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CoreReturnItem(Base):
    """Rastreio de peças velhas substituídas que são devolvidas ao fornecedor para crédito/garantia."""

    __tablename__ = "core_return_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    work_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("work_orders.id"), index=True)
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    evidence_photo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending_return", index=True
    )  # pending_return | returned_to_supplier | credited
    credit_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    supplier_third_party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("third_parties.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkshopTool(Base):
    __tablename__ = "workshop_tools"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_workshop_tools_tenant_code"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    calibration_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="available", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serial_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    calibration_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MaintenancePlan(Base):
    __tablename__ = "maintenance_plans"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_maintenance_plans_tenant_request_reference",
        ),
        CheckConstraint(
            "interval_km IS NOT NULL OR interval_days IS NOT NULL OR service_catalog_item_id IS NOT NULL",
            name="chk_maintenance_plans_interval",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("vehicles.id"), index=True, nullable=True)
    service_catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_catalog_items.id"), index=True, nullable=True
    )
    request_reference: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160))
    interval_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_due_km: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    ownership_scope: Mapped[str] = mapped_column(
        String(20), server_default="fleet", default="fleet"
    )  # fleet | customer | all
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedule"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "plan_id",
            "vehicle_id",
            "status",
            name="uq_maintenance_schedule_tenant_plan_vehicle_status",
        ),
        CheckConstraint(
            "status IN ('pending', 'due', 'overdue', 'converted_to_wo', "
            "'converted_to_quote', 'completed', 'cancelled')",
            name="chk_maintenance_schedule_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("maintenance_plans.id"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workshop_quotes.id"), index=True, nullable=True)
    work_order_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("work_orders.id"), index=True, nullable=True)
    due_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    notified_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notified_overdue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending | due | overdue | converted_to_wo | converted_to_quote | completed | cancelled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkshopStaffRate(Base):
    __tablename__ = "workshop_staff_rates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaskLaborLog(Base):
    """Registo de sessões de mão de obra efetuadas por mecânicos numa tarefa da OS."""

    __tablename__ = "task_labor_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    work_order_task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("work_order_tasks.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    minutes_worked: Mapped[int] = mapped_column(Integer, nullable=False)
    hourly_rate_applied: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    total_labor_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolCalibration(Base):
    __tablename__ = "tool_calibrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    tool_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workshop_tools.id"), index=True)
    calibrated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SparePartSerialItem(Base):
    __tablename__ = "spare_part_serial_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "serial_number", name="uq_spare_part_serial_items_tenant_serial"),
        Index("ix_spare_part_serial_items_tenant_part", "tenant_id", "part_id"),
        Index(
            "ix_spare_part_serial_items_tenant_vehicle",
            "tenant_id",
            "vehicle_id",
            postgresql_where=text("vehicle_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    part_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("spare_parts_inventory.id"))
    serial_number: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="in_stock", nullable=False)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scrapped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
