from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.operational_exceptions.service import ensure_exception
from app.modules.trips.costs import record_trip_cost
from app.modules.trips.models import Trip, TripIncident
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenancePartUsed,
    MaintenancePlan,
    MaintenanceRequest,
    MaintenanceSchedule,
    SparePartInventory,
    SparePartMovement,
    SparePartSerialItem,
    ToolCalibration,
    ToolCheckout,
    WorkOrder,
    WorkOrderTask,
    WorkshopStaffRate,
    WorkshopTool,
)
from app.modules.workshop.schemas import (
    MaintenancePartIssueCreate,
    MaintenancePlanCreate,
    MaintenanceRequestCreate,
    SerialItemCreate,
    SparePartInventoryCreate,
    SparePartReceiptCreate,
    TaskAssignRequest,
    ToolCalibrationCreate,
    ToolCheckoutCreate,
    ToolReturnCreate,
    ToolUpdateRequest,
    WorkOrderApproveRequest,
    WorkOrderCloseRequest,
    WorkOrderCreate,
    WorkOrderTaskCompleteRequest,
    WorkOrderTaskCreate,
    WorkOrderTransitionRequest,
    WorkshopStaffRateCreate,
    WorkshopToolCreate,
)

REQUEST_TYPES = {"corrective", "preventive", "inspection", "breakdown"}
PRIORITIES = {"low", "normal", "high", "urgent"}
ACTIVE_WORK_ORDER_STATUSES = {"approved", "in_progress", "quality_check"}
TOOL_RETURN_CONDITIONS = {"available", "damaged", "lost", "retired"}


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def now_utc() -> datetime:
    return datetime.now(UTC)


def serialize_maintenance_request(item: MaintenanceRequest) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "vehicle_id": item.vehicle_id,
        "trip_id": item.trip_id,
        "incident_id": item.incident_id,
        "request_type": item.request_type,
        "priority": item.priority,
        "description": item.description,
        "odometer_reading": item.odometer_reading,
        "status": item.status,
        "requested_by": item.requested_by,
        "requested_at": item.requested_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_work_order(item: WorkOrder) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "maintenance_request_id": item.maintenance_request_id,
        "vehicle_id": item.vehicle_id,
        "work_order_number": item.work_order_number,
        "diagnosis": item.diagnosis,
        "planned_work": item.planned_work,
        "estimated_cost": item.estimated_cost,
        "actual_cost": item.actual_cost,
        "labor_cost": str(item.labor_cost) if item.labor_cost is not None else "0",
        "status": item.status,
        "approved_by": item.approved_by,
        "approved_at": item.approved_at,
        "closed_by": item.closed_by,
        "closed_at": item.closed_at,
        "close_notes": item.close_notes,
        "service_provider_third_party_id": item.service_provider_third_party_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_work_order_task(item: WorkOrderTask) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "work_order_id": item.work_order_id,
        "description": item.description,
        "status": item.status,
        "completed_by": item.completed_by,
        "completed_at": item.completed_at,
        "completion_notes": item.completion_notes,
        "assigned_to": str(item.assigned_to) if item.assigned_to else None,
        "estimated_minutes": item.estimated_minutes,
        "actual_minutes": item.actual_minutes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_spare_part(item: SparePartInventory) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "sku": item.sku,
        "name": item.name,
        "unit": item.unit,
        "current_quantity": item.current_quantity,
        "minimum_quantity": item.minimum_quantity,
        "average_unit_cost": item.average_unit_cost,
        "status": item.status,
        "supplier_name": item.supplier_name,
        "supplier_third_party_id": item.supplier_third_party_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_spare_part_movement(item: SparePartMovement) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "inventory_id": item.inventory_id,
        "movement_type": item.movement_type,
        "direction": item.direction,
        "quantity": item.quantity,
        "balance_after_quantity": item.balance_after_quantity,
        "unit_cost": item.unit_cost,
        "total_cost": item.total_cost,
        "request_reference": item.request_reference,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "occurred_at": item.occurred_at,
        "recorded_by": item.recorded_by,
        "notes": item.notes,
        "created_at": item.created_at,
    }


def serialize_maintenance_part_used(item: MaintenancePartUsed) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "work_order_id": item.work_order_id,
        "inventory_id": item.inventory_id,
        "movement_id": item.movement_id,
        "request_reference": item.request_reference,
        "quantity": item.quantity,
        "unit_cost": item.unit_cost,
        "total_cost": item.total_cost,
        "issued_by": item.issued_by,
        "issued_at": item.issued_at,
        "notes": item.notes,
    }


def serialize_tool(item: WorkshopTool) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "code": item.code,
        "name": item.name,
        "is_critical": item.is_critical,
        "calibration_due_at": item.calibration_due_at,
        "status": item.status,
        "category": item.category,
        "location": item.location,
        "serial_number": item.serial_number,
        "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
        "purchase_cost": str(item.purchase_cost) if item.purchase_cost else None,
        "calibration_interval_days": item.calibration_interval_days,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_tool_checkout(item: ToolCheckout) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "tool_id": item.tool_id,
        "work_order_id": item.work_order_id,
        "checkout_reference": item.checkout_reference,
        "checked_out_by": item.checked_out_by,
        "checked_out_at": item.checked_out_at,
        "due_at": item.due_at,
        "status": item.status,
        "return_reference": item.return_reference,
        "returned_by": item.returned_by,
        "returned_at": item.returned_at,
        "return_condition": item.return_condition,
        "notes": item.notes,
        "created_at": item.created_at,
    }


def serialize_maintenance_plan(item: MaintenancePlan) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "vehicle_id": item.vehicle_id,
        "request_reference": item.request_reference,
        "name": item.name,
        "interval_km": item.interval_km,
        "interval_days": item.interval_days,
        "next_due_km": item.next_due_km,
        "next_due_at": item.next_due_at,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def serialize_maintenance_schedule(item: MaintenanceSchedule) -> dict:
    return {
        "id": item.id,
        "tenant_id": item.tenant_id,
        "plan_id": item.plan_id,
        "vehicle_id": item.vehicle_id,
        "due_km": item.due_km,
        "due_at": item.due_at,
        "status": item.status,
        "created_at": item.created_at,
    }


class SparePartMovementService:
    """Single writer for spare-part stock."""

    @staticmethod
    async def record(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        inventory_id: UUID,
        movement_type: str,
        direction: str,
        quantity: float | Decimal,
        request_reference: str,
        source_type: str,
        source_id: UUID | None,
        occurred_at: datetime,
        actor_id: UUID | None,
        unit_cost: float | Decimal | None = None,
        notes: str | None = None,
    ) -> SparePartMovement:
        amount = _decimal(quantity)
        if amount <= 0:
            raise ApiError(
                "invalid_spare_part_quantity",
                "Quantity must be positive.",
                status_code=422,
            )
        if direction not in {"in", "out"}:
            raise ApiError(
                "invalid_spare_part_direction",
                "Invalid movement direction.",
                status_code=422,
            )

        existing = await _find_spare_part_movement(db, tenant_id, request_reference)
        if existing:
            _validate_spare_part_replay(
                existing,
                inventory_id,
                movement_type,
                direction,
                amount,
                unit_cost,
            )
            return existing

        inventory = await db.scalar(
            select(SparePartInventory)
            .where(
                SparePartInventory.id == inventory_id,
                SparePartInventory.tenant_id == tenant_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not inventory or inventory.status != "active":
            raise ApiError("spare_part_not_found", "Active spare part not found.", status_code=404)

        existing = await _find_spare_part_movement(db, tenant_id, request_reference)
        if existing:
            _validate_spare_part_replay(
                existing,
                inventory_id,
                movement_type,
                direction,
                amount,
                unit_cost,
            )
            return existing

        previous_balance = _decimal(inventory.current_quantity)
        new_balance = previous_balance + amount if direction == "in" else previous_balance - amount
        if new_balance < 0:
            raise ApiError(
                "insufficient_spare_part_stock",
                "Spare part stock is insufficient.",
                status_code=409,
                details={
                    "inventory_id": str(inventory.id),
                    "available_quantity": str(previous_balance),
                    "requested_quantity": str(amount),
                },
            )

        previous_average_cost = _decimal(inventory.average_unit_cost)
        movement_unit_cost = (
            _decimal(unit_cost)
            if unit_cost is not None
            else previous_average_cost
            if direction == "out"
            else None
        )
        item = SparePartMovement(
            tenant_id=tenant_id,
            inventory_id=inventory.id,
            movement_type=movement_type,
            direction=direction,
            quantity=amount,
            balance_after_quantity=new_balance,
            unit_cost=movement_unit_cost,
            total_cost=movement_unit_cost * amount if movement_unit_cost is not None else None,
            request_reference=request_reference,
            source_type=source_type,
            source_id=source_id,
            occurred_at=occurred_at,
            recorded_by=actor_id,
            notes=notes,
        )
        inventory.current_quantity = new_balance
        if direction == "in" and movement_unit_cost is not None and new_balance > 0:
            inventory.average_unit_cost = (
                (previous_balance * previous_average_cost) + (amount * movement_unit_cost)
            ) / new_balance
        db.add(item)
        await db.flush()
        
        # --- HOOK CONTABILISTICO (Fase 6) ---
        if direction == "out" and item.total_cost and item.total_cost > 0:
            from app.modules.accounting.services import create_journal_entry
            from app.modules.accounting.schemas import JournalEntryCreate, JournalItemCreate
            from app.modules.accounting.models import Account

            vehicle_id_for_cost = None
            if source_type == "vehicle":
                vehicle_id_for_cost = source_id
            elif source_type == "work_order" and source_id:
                from app.modules.workshop.models import WorkOrder
                wo = await db.get(WorkOrder, source_id)
                if wo:
                    vehicle_id_for_cost = wo.vehicle_id

            if vehicle_id_for_cost:
                acct_inv = await db.scalar(select(Account).where(Account.tenant_id == tenant_id, Account.code.like("32%")).limit(1))
                acct_exp = await db.scalar(select(Account).where(Account.tenant_id == tenant_id, Account.code.like("622%")).limit(1))

                if acct_inv and acct_exp:
                    await create_journal_entry(
                        db,
                        tenant_id=tenant_id,
                        payload=JournalEntryCreate(
                            date=occurred_at.date() if hasattr(occurred_at, "date") else occurred_at,
                            journal_type="OD",
                            description=f"Consumo de peca {inventory.sku} no veiculo",
                            lines=[
                                JournalItemCreate(
                                    account_id=acct_exp.id,
                                    description=f"Custo de Manutencao ({inventory.name})",
                                    debit=float(item.total_cost),
                                    credit=0,
                                    vehicle_id=vehicle_id_for_cost
                                ),
                                JournalItemCreate(
                                    account_id=acct_inv.id,
                                    description="Saida de Armazem",
                                    debit=0,
                                    credit=float(item.total_cost)
                                )
                            ]
                        ),
                        actor_id=actor_id
                    )
        # ------------------------------------

        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            action="spare_part_movement.recorded",
            entity_type="spare_part_inventory",
            entity_id=inventory.id,
            old_values={"current_quantity": str(previous_balance)},
            new_values={
                "movement_id": str(item.id),
                "direction": direction,
                "quantity": str(amount),
                "current_quantity": str(new_balance),
            },
        )
        if new_balance <= _decimal(inventory.minimum_quantity):
            await ensure_exception(
                db,
                tenant_id,
                entity_type="spare_part_inventory",
                entity_id=inventory.id,
                exception_type="spare_part_low_stock",
                severity="high",
                title=f"Stock baixo da peca {inventory.sku}",
                message="O stock da peca atingiu ou ficou abaixo do minimo configurado.",
                actor_id=actor_id,
                context={
                    "current_quantity": str(new_balance),
                    "minimum_quantity": str(inventory.minimum_quantity),
                },
                source_type="spare_part_movement",
            )
        return item


async def list_maintenance_requests(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    query = select(MaintenanceRequest).where(MaintenanceRequest.tenant_id == tenant_id)
    if status_filter:
        query = query.where(MaintenanceRequest.status == status_filter)
    if vehicle_id:
        query = query.where(MaintenanceRequest.vehicle_id == vehicle_id)
    rows = await db.execute(query.order_by(MaintenanceRequest.requested_at.desc()).limit(limit))
    return [serialize_maintenance_request(item) for item in rows.scalars()]


async def create_maintenance_request(
    db: AsyncSession,
    tenant_id: UUID,
    payload: MaintenanceRequestCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    if payload.request_type not in REQUEST_TYPES:
        raise ApiError(
            "invalid_maintenance_request_type",
            "Invalid maintenance request type.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed": sorted(REQUEST_TYPES)},
        )
    if payload.priority not in PRIORITIES:
        raise ApiError(
            "invalid_maintenance_priority",
            "Invalid maintenance priority.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed": sorted(PRIORITIES)},
        )
    await _require_vehicle(db, tenant_id, payload.vehicle_id)
    await _validate_trip_and_incident(db, tenant_id, payload)

    item = MaintenanceRequest(tenant_id=tenant_id, requested_by=actor_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="maintenance_request.created",
        entity_type="maintenance_request",
        entity_id=item.id,
        new_values={
            "vehicle_id": str(item.vehicle_id),
            "request_type": item.request_type,
            "priority": item.priority,
        },
    )
    await db.commit()
    await db.refresh(item)
    return serialize_maintenance_request(item)


async def list_work_orders(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    query = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
    if status_filter:
        query = query.where(WorkOrder.status == status_filter)
    if vehicle_id:
        query = query.where(WorkOrder.vehicle_id == vehicle_id)
    rows = await db.execute(query.order_by(WorkOrder.created_at.desc()).limit(limit))
    return [serialize_work_order(item) for item in rows.scalars()]


async def create_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    payload: WorkOrderCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    await _require_vehicle(db, tenant_id, payload.vehicle_id)
    request = None
    if payload.maintenance_request_id:
        request = await _require_maintenance_request(db, tenant_id, payload.maintenance_request_id)
        if request.vehicle_id != payload.vehicle_id:
            raise ApiError(
                "maintenance_request_vehicle_mismatch",
                "Maintenance request and work order vehicles differ.",
                status_code=409,
            )
        if request.status not in {"open", "triaged"}:
            raise ApiError(
                "invalid_maintenance_request_status",
                "Maintenance request cannot create another work order.",
                status_code=409,
            )

    item = WorkOrder(
        tenant_id=tenant_id,
        work_order_number=f"WO-{uuid4().hex[:12].upper()}",
        **payload.model_dump(),
    )
    db.add(item)
    if request:
        request.status = "converted"
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order.created",
        entity_type="work_order",
        entity_id=item.id,
        new_values={
            "vehicle_id": str(item.vehicle_id),
            "work_order_number": item.work_order_number,
            "status": item.status,
        },
    )
    await db.commit()
    await db.refresh(item)
    return serialize_work_order(item)


async def approve_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: WorkOrderApproveRequest,
    *,
    actor_id: UUID | None,
) -> dict:
    item = await _require_work_order(db, tenant_id, work_order_id)
    if item.status == "approved":
        return serialize_work_order(item)
    if item.status != "draft":
        raise ApiError(
            "invalid_work_order_status",
            "Work order cannot be approved.",
            status_code=409,
        )

    item.status = "approved"
    item.approved_by = actor_id
    item.approved_at = now_utc()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order.approved",
        entity_type="work_order",
        entity_id=item.id,
        old_values={"status": "draft"},
        new_values={"status": item.status, "notes": payload.notes},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_work_order(item)


async def start_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: WorkOrderTransitionRequest,
    *,
    actor_id: UUID | None,
) -> dict:
    return await _transition_work_order(
        db,
        tenant_id,
        work_order_id,
        expected_status="approved",
        next_status="in_progress",
        action="work_order.started",
        notes=payload.notes,
        actor_id=actor_id,
    )


async def send_work_order_to_quality_check(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: WorkOrderTransitionRequest,
    *,
    actor_id: UUID | None,
) -> dict:
    pending_task = await db.scalar(
        select(WorkOrderTask.id).where(
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.work_order_id == work_order_id,
            WorkOrderTask.status == "pending",
        )
    )
    if pending_task:
        raise ApiError(
            "work_order_tasks_pending",
            "Work order still has pending tasks.",
            status_code=409,
            details={"task_id": str(pending_task)},
        )
    active_checkout = await db.scalar(
        select(ToolCheckout.id).where(
            ToolCheckout.tenant_id == tenant_id,
            ToolCheckout.work_order_id == work_order_id,
            ToolCheckout.status == "checked_out",
        )
    )
    if active_checkout:
        raise ApiError(
            "work_order_tools_checked_out",
            "Work order still has tools checked out.",
            status_code=409,
            details={"checkout_id": str(active_checkout)},
        )
    return await _transition_work_order(
        db,
        tenant_id,
        work_order_id,
        expected_status="in_progress",
        next_status="quality_check",
        action="work_order.quality_check_requested",
        notes=payload.notes,
        actor_id=actor_id,
    )


async def close_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: WorkOrderCloseRequest,
    *,
    actor_id: UUID | None,
) -> dict:
    item = await _require_work_order(db, tenant_id, work_order_id)
    if item.status == "closed":
        return serialize_work_order(item)
    if item.status != "quality_check":
        raise ApiError("invalid_work_order_status", "Work order cannot be closed.", status_code=409)

    old_status = item.status
    item.status = "closed"
    item.actual_cost = payload.actual_cost
    item.close_notes = payload.notes
    item.closed_by = actor_id
    item.closed_at = now_utc()
    if item.maintenance_request_id and item.actual_cost is not None:
        request = await _require_maintenance_request(db, tenant_id, item.maintenance_request_id)
        if request.trip_id:
            await record_trip_cost(
                db,
                tenant_id,
                trip_id=request.trip_id,
                cost_type="workshop_maintenance",
                amount=item.actual_cost,
                request_reference=f"work-order:{item.id}",
                incurred_at=item.closed_at,
                actor_id=actor_id,
                description=item.close_notes,
                source_type="work_order",
                source_id=item.id,
            )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order.closed",
        entity_type="work_order",
        entity_id=item.id,
        old_values={"status": old_status},
        new_values={"status": item.status, "actual_cost": str(item.actual_cost or 0)},
    )

    # Workshop billing: auto-generate draft invoice for oficina-origin WOs
    invoice_draft = None
    if item.origin_type in ("reception", "quote", "warranty"):
        from app.modules.workshop.workshop_billing_service import create_workshop_invoice
        try:
            invoice_draft = await create_workshop_invoice(
                db, tenant_id, work_order_id, actor_id=actor_id,
            )
        except Exception:
            pass  # Non-blocking: invoice can be generated manually later

    # Preventive Maintenance: Catalog matching & automatic next cycle creation
    try:
        from app.modules.workshop.preventive_service import handle_work_order_completion_preventive_matching
        await handle_work_order_completion_preventive_matching(
            db, tenant_id, work_order_id, actor_id=actor_id,
        )
    except Exception:
        pass  # Non-blocking: preventive cycle auto-advance should not block WO close

    await db.commit()
    await db.refresh(item)
    result = serialize_work_order(item)
    if invoice_draft:
        result["workshop_invoice_draft"] = invoice_draft
    return result


async def list_work_order_tasks(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
) -> list[dict]:
    await _require_work_order(db, tenant_id, work_order_id)
    rows = await db.execute(
        select(WorkOrderTask)
        .where(
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.work_order_id == work_order_id,
        )
        .order_by(WorkOrderTask.created_at)
    )
    return [serialize_work_order_task(item) for item in rows.scalars()]


async def create_work_order_task(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: WorkOrderTaskCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    work_order = await _require_work_order(db, tenant_id, work_order_id)
    if work_order.status not in {"draft", "approved", "in_progress"}:
        raise ApiError(
            "invalid_work_order_status",
            "Work order cannot receive tasks.",
            status_code=409,
        )
    item = WorkOrderTask(tenant_id=tenant_id, work_order_id=work_order_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order_task.created",
        entity_type="work_order_task",
        entity_id=item.id,
        new_values={"work_order_id": str(work_order_id), "status": item.status},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_work_order_task(item)


async def complete_work_order_task(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    task_id: UUID,
    payload: WorkOrderTaskCompleteRequest,
    *,
    actor_id: UUID | None,
) -> dict:
    work_order = await _require_work_order(db, tenant_id, work_order_id)
    if work_order.status != "in_progress":
        raise ApiError(
            "invalid_work_order_status",
            "Work order is not in progress.",
            status_code=409,
        )
    item = await db.get(WorkOrderTask, task_id)
    if not item or item.tenant_id != tenant_id or item.work_order_id != work_order_id:
        raise ApiError("work_order_task_not_found", "Work order task not found.", status_code=404)
    if item.status == "completed":
        return serialize_work_order_task(item)
    item.status = "completed"
    item.completed_by = actor_id
    item.completed_at = now_utc()
    item.completion_notes = payload.notes
    # Labor cost accumulation — only when actual_minutes provided and task has a completer
    if payload.actual_minutes and actor_id:
        item.actual_minutes = payload.actual_minutes
        rate_result = await db.execute(
            select(WorkshopStaffRate)
            .where(
                WorkshopStaffRate.tenant_id == tenant_id,
                WorkshopStaffRate.user_id == actor_id,
                WorkshopStaffRate.effective_from <= func.current_date(),
            )
            .order_by(WorkshopStaffRate.effective_from.desc())
            .limit(1)
        )
        active_rate = rate_result.scalar_one_or_none()
        if active_rate:
            labor_hours = Decimal(str(payload.actual_minutes)) / Decimal("60")
            labor_amount = (labor_hours * active_rate.hourly_rate).quantize(Decimal("0.01"))
            # work_order was already fetched at the start of this function
            work_order.labor_cost = (work_order.labor_cost or Decimal("0")) + labor_amount
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order_task.completed",
        entity_type="work_order_task",
        entity_id=item.id,
        old_values={"status": "pending"},
        new_values={"status": item.status, "work_order_id": str(work_order_id)},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_work_order_task(item)


async def create_breakdown_maintenance_request(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    trip: Trip,
    incident: TripIncident,
    actor_id: UUID | None,
) -> MaintenanceRequest:
    existing = await db.scalar(
        select(MaintenanceRequest).where(
            MaintenanceRequest.tenant_id == tenant_id,
            MaintenanceRequest.incident_id == incident.id,
        )
    )
    if existing:
        return existing
    item = MaintenanceRequest(
        tenant_id=tenant_id,
        vehicle_id=trip.vehicle_id,
        trip_id=trip.id,
        incident_id=incident.id,
        request_type="breakdown",
        priority="urgent" if incident.severity == "critical" else "high",
        description=incident.description,
        requested_by=actor_id,
    )
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="maintenance_request.created_from_breakdown",
        entity_type="maintenance_request",
        entity_id=item.id,
        new_values={"trip_id": str(trip.id), "incident_id": str(incident.id)},
    )
    return item


async def _transition_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    *,
    expected_status: str,
    next_status: str,
    action: str,
    notes: str | None,
    actor_id: UUID | None,
) -> dict:
    item = await _require_work_order(db, tenant_id, work_order_id)
    if item.status == next_status:
        return serialize_work_order(item)
    if item.status != expected_status:
        raise ApiError(
            "invalid_work_order_status",
            "Invalid work order transition.",
            status_code=409,
        )
    item.status = next_status
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action=action,
        entity_type="work_order",
        entity_id=item.id,
        old_values={"status": expected_status},
        new_values={"status": next_status, "notes": notes},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_work_order(item)


async def list_spare_parts(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    rows = await db.execute(
        select(SparePartInventory)
        .where(SparePartInventory.tenant_id == tenant_id)
        .order_by(SparePartInventory.sku)
    )
    return [serialize_spare_part(item) for item in rows.scalars()]


async def create_spare_part(
    db: AsyncSession,
    tenant_id: UUID,
    payload: SparePartInventoryCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    existing = await db.scalar(
        select(SparePartInventory.id).where(
            SparePartInventory.tenant_id == tenant_id,
            SparePartInventory.sku == payload.sku,
        )
    )
    if existing:
        raise ApiError("spare_part_sku_exists", "Spare part SKU already exists.", status_code=409)
    item = SparePartInventory(tenant_id=tenant_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="spare_part_inventory.created",
        entity_type="spare_part_inventory",
        entity_id=item.id,
        new_values={"sku": item.sku, "minimum_quantity": str(item.minimum_quantity)},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_spare_part(item)


async def receive_spare_part(
    db: AsyncSession,
    tenant_id: UUID,
    payload: SparePartReceiptCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    movement = await SparePartMovementService.record(
        db,
        tenant_id,
        inventory_id=payload.inventory_id,
        movement_type="receipt",
        direction="in",
        quantity=payload.quantity,
        request_reference=payload.request_reference,
        source_type="spare_part_receipt",
        source_id=None,
        occurred_at=payload.occurred_at,
        actor_id=actor_id,
        unit_cost=payload.unit_cost,
        notes=payload.notes,
    )
    await db.commit()
    await db.refresh(movement)
    return serialize_spare_part_movement(movement)


async def list_spare_part_movements(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    inventory_id: UUID | None = None,
    limit: int = 100,
) -> list[dict]:
    query = select(SparePartMovement).where(SparePartMovement.tenant_id == tenant_id)
    if inventory_id:
        query = query.where(SparePartMovement.inventory_id == inventory_id)
    rows = await db.execute(query.order_by(SparePartMovement.occurred_at.desc()).limit(limit))
    return [serialize_spare_part_movement(item) for item in rows.scalars()]


async def issue_spare_part_to_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: MaintenancePartIssueCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    existing = await db.scalar(
        select(MaintenancePartUsed).where(
            MaintenancePartUsed.tenant_id == tenant_id,
            MaintenancePartUsed.request_reference == payload.request_reference,
        )
    )
    if existing:
        _validate_maintenance_part_replay(existing, work_order_id, payload)
        return serialize_maintenance_part_used(existing)

    work_order = await _require_work_order(db, tenant_id, work_order_id)
    if work_order.status != "in_progress":
        raise ApiError(
            "invalid_work_order_status",
            "Spare parts can only be issued while work is in progress.",
            status_code=409,
        )
    usage = MaintenancePartUsed(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        inventory_id=payload.inventory_id,
        request_reference=payload.request_reference,
        quantity=_decimal(payload.quantity),
        issued_by=actor_id,
        notes=payload.notes,
    )
    db.add(usage)
    await db.flush()
    movement = await SparePartMovementService.record(
        db,
        tenant_id,
        inventory_id=payload.inventory_id,
        movement_type="work_order_issue",
        direction="out",
        quantity=payload.quantity,
        request_reference=payload.request_reference,
        source_type="maintenance_part_used",
        source_id=usage.id,
        occurred_at=payload.occurred_at,
        actor_id=actor_id,
        notes=payload.notes,
    )
    usage.movement_id = movement.id
    usage.unit_cost = movement.unit_cost
    usage.total_cost = movement.total_cost
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="maintenance_part.issued",
        entity_type="work_order",
        entity_id=work_order_id,
        new_values={
            "maintenance_part_used_id": str(usage.id),
            "inventory_id": str(payload.inventory_id),
            "quantity": str(payload.quantity),
        },
    )
    await db.commit()
    await db.refresh(usage)
    return serialize_maintenance_part_used(usage)


async def list_tools(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    rows = await db.execute(
        select(WorkshopTool).where(WorkshopTool.tenant_id == tenant_id).order_by(WorkshopTool.code)
    )
    return [serialize_tool(item) for item in rows.scalars()]


async def create_tool(
    db: AsyncSession,
    tenant_id: UUID,
    payload: WorkshopToolCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    existing = await db.scalar(
        select(WorkshopTool.id).where(
            WorkshopTool.tenant_id == tenant_id,
            WorkshopTool.code == payload.code,
        )
    )
    if existing:
        raise ApiError(
            "workshop_tool_code_exists",
            "Workshop tool code already exists.",
            status_code=409,
        )
    item = WorkshopTool(tenant_id=tenant_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_tool.created",
        entity_type="workshop_tool",
        entity_id=item.id,
        new_values={"code": item.code, "is_critical": item.is_critical},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_tool(item)


async def list_tool_checkouts(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    limit: int = 100,
) -> list[dict]:
    query = select(ToolCheckout).where(ToolCheckout.tenant_id == tenant_id)
    if status_filter:
        query = query.where(ToolCheckout.status == status_filter)
    rows = await db.execute(query.order_by(ToolCheckout.checked_out_at.desc()).limit(limit))
    return [serialize_tool_checkout(item) for item in rows.scalars()]


async def checkout_tool(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    payload: ToolCheckoutCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    existing = await db.scalar(
        select(ToolCheckout).where(
            ToolCheckout.tenant_id == tenant_id,
            ToolCheckout.checkout_reference == payload.checkout_reference,
        )
    )
    if existing:
        _validate_tool_checkout_replay(existing, work_order_id, payload)
        return serialize_tool_checkout(existing)

    work_order = await _require_work_order(db, tenant_id, work_order_id)
    if work_order.status != "in_progress":
        raise ApiError(
            "invalid_work_order_status",
            "Tools can only be checked out while work is in progress.",
            status_code=409,
        )
    tool = await db.scalar(
        select(WorkshopTool)
        .where(WorkshopTool.id == payload.tool_id, WorkshopTool.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not tool:
        raise ApiError("workshop_tool_not_found", "Workshop tool not found.", status_code=404)
    if tool.status != "available":
        raise ApiError(
            "workshop_tool_unavailable",
            "Workshop tool is not available for checkout.",
            status_code=409,
            details={"tool_status": tool.status},
        )
    if tool.is_critical and tool.calibration_due_at and tool.calibration_due_at <= now_utc():
        raise ApiError(
            "workshop_tool_calibration_expired",
            "Critical workshop tool calibration is expired.",
            status_code=409,
        )

    item = ToolCheckout(
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        checked_out_by=actor_id,
        **payload.model_dump(),
    )
    tool.status = "checked_out"
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_tool.checked_out",
        entity_type="workshop_tool",
        entity_id=tool.id,
        old_values={"status": "available"},
        new_values={"status": tool.status, "checkout_id": str(item.id)},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_tool_checkout(item)


async def return_tool(
    db: AsyncSession,
    tenant_id: UUID,
    checkout_id: UUID,
    payload: ToolReturnCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    if payload.return_condition not in TOOL_RETURN_CONDITIONS:
        raise ApiError(
            "invalid_tool_return_condition",
            "Invalid tool return condition.",
            status_code=422,
        )
    item = await db.scalar(
        select(ToolCheckout)
        .where(ToolCheckout.id == checkout_id, ToolCheckout.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not item:
        raise ApiError("tool_checkout_not_found", "Tool checkout not found.", status_code=404)
    if item.status == "returned":
        if (
            item.return_reference != payload.return_reference
            or item.returned_at != payload.returned_at
            or item.return_condition != payload.return_condition
        ):
            raise ApiError(
                "tool_return_reference_reused",
                "Tool checkout was already returned with another reference.",
                status_code=409,
            )
        return serialize_tool_checkout(item)

    tool = await db.scalar(
        select(WorkshopTool)
        .where(WorkshopTool.id == item.tool_id, WorkshopTool.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not tool:
        raise ApiError("workshop_tool_not_found", "Workshop tool not found.", status_code=404)
    item.status = "returned"
    item.return_reference = payload.return_reference
    item.returned_by = actor_id
    item.returned_at = payload.returned_at
    item.return_condition = payload.return_condition
    item.notes = payload.notes or item.notes
    old_status = tool.status
    tool.status = payload.return_condition
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="workshop_tool.returned",
        entity_type="workshop_tool",
        entity_id=tool.id,
        old_values={"status": old_status},
        new_values={
            "status": tool.status,
            "checkout_id": str(item.id),
            "return_condition": payload.return_condition,
        },
    )
    await db.commit()
    await db.refresh(item)
    return serialize_tool_checkout(item)


async def list_maintenance_plans(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    rows = await db.execute(
        select(MaintenancePlan)
        .where(MaintenancePlan.tenant_id == tenant_id)
        .order_by(MaintenancePlan.created_at.desc())
    )
    return [serialize_maintenance_plan(item) for item in rows.scalars()]


async def create_maintenance_plan(
    db: AsyncSession,
    tenant_id: UUID,
    payload: MaintenancePlanCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    if payload.interval_km is None and payload.interval_days is None:
        raise ApiError(
            "maintenance_plan_interval_required",
            "Maintenance plan requires a kilometer or day interval.",
            status_code=422,
        )
    await _require_vehicle(db, tenant_id, payload.vehicle_id)
    existing = await db.scalar(
        select(MaintenancePlan).where(
            MaintenancePlan.tenant_id == tenant_id,
            MaintenancePlan.request_reference == payload.request_reference,
        )
    )
    if existing:
        if (
            existing.vehicle_id != payload.vehicle_id
            or existing.name != payload.name
            or existing.interval_km != payload.interval_km
            or existing.interval_days != payload.interval_days
            or existing.next_due_km != payload.next_due_km
            or existing.next_due_at != payload.next_due_at
        ):
            raise ApiError(
                "maintenance_plan_request_reference_reused",
                "Maintenance plan reference was reused with a different payload.",
                status_code=409,
            )
        return serialize_maintenance_plan(existing)
    item = MaintenancePlan(tenant_id=tenant_id, **payload.model_dump())
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="maintenance_plan.created",
        entity_type="maintenance_plan",
        entity_id=item.id,
        new_values={"vehicle_id": str(item.vehicle_id), "name": item.name},
    )
    await db.commit()
    await db.refresh(item)
    return serialize_maintenance_plan(item)


async def list_maintenance_schedule(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
) -> list[dict]:
    query = select(MaintenanceSchedule).where(MaintenanceSchedule.tenant_id == tenant_id)
    if status_filter:
        query = query.where(MaintenanceSchedule.status == status_filter)
    rows = await db.execute(query.order_by(MaintenanceSchedule.created_at.desc()))
    return [serialize_maintenance_schedule(item) for item in rows.scalars()]


async def evaluate_maintenance_schedule(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    actor_id: UUID | None,
) -> dict:
    rows = await db.execute(
        select(MaintenancePlan, Vehicle)
        .join(Vehicle, Vehicle.id == MaintenancePlan.vehicle_id)
        .where(
            MaintenancePlan.tenant_id == tenant_id,
            MaintenancePlan.status == "active",
        )
    )
    created: list[MaintenanceSchedule] = []
    for plan, vehicle in rows:
        overdue = (plan.next_due_km is not None and vehicle.current_km >= plan.next_due_km) or (
            plan.next_due_at is not None and plan.next_due_at <= now_utc()
        )
        if not overdue:
            continue
        schedule = await db.scalar(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.tenant_id == tenant_id,
                MaintenanceSchedule.plan_id == plan.id,
                MaintenanceSchedule.status == "overdue",
            )
        )
        if not schedule:
            schedule = MaintenanceSchedule(
                tenant_id=tenant_id,
                plan_id=plan.id,
                vehicle_id=plan.vehicle_id,
                due_km=plan.next_due_km,
                due_at=plan.next_due_at,
            )
            db.add(schedule)
            await db.flush()
            created.append(schedule)
            await record_audit_log(
                db,
                tenant_id=tenant_id,
                user_id=actor_id,
                action="maintenance_schedule.overdue",
                entity_type="maintenance_plan",
                entity_id=plan.id,
                new_values={"schedule_id": str(schedule.id), "vehicle_id": str(vehicle.id)},
            )
        await ensure_exception(
            db,
            tenant_id,
            entity_type="maintenance_plan",
            entity_id=plan.id,
            exception_type="maintenance_overdue",
            severity="high",
            title=f"Manutencao preventiva vencida: {plan.name}",
            message="A viatura possui manutencao preventiva vencida por data ou quilometragem.",
            actor_id=actor_id,
            context={
                "vehicle_id": str(vehicle.id),
                "current_km": str(vehicle.current_km),
                "next_due_km": str(plan.next_due_km) if plan.next_due_km is not None else None,
            },
            source_type="maintenance_schedule",
            source_id=schedule.id,
        )
        # D-02: create WorkOrder automatically for this plan+vehicle
        await _trigger_maintenance_work_order(db, tenant_id, plan, vehicle, actor_id)

        # D-03: create next-cycle MaintenanceSchedule with status='pending'
        # UniqueConstraint(tenant_id, plan_id, status) protects against duplicates
        existing_pending = await db.scalar(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.tenant_id == tenant_id,
                MaintenanceSchedule.plan_id == plan.id,
                MaintenanceSchedule.status == "pending",
            )
        )
        if not existing_pending:
            from datetime import timedelta

            next_km = (
                (vehicle.current_km + plan.interval_km)
                if (plan.interval_km is not None and vehicle.current_km is not None)
                else None
            )
            next_at = (
                (now_utc() + timedelta(days=plan.interval_days))
                if plan.interval_days is not None
                else None
            )
            next_schedule = MaintenanceSchedule(
                tenant_id=tenant_id,
                plan_id=plan.id,
                vehicle_id=plan.vehicle_id,
                due_km=next_km,
                due_at=next_at,
                status="pending",
            )
            db.add(next_schedule)
            await db.flush()
    await db.commit()
    return {
        "created": len(created),
        "overdue": await list_maintenance_schedule(db, tenant_id, status_filter="overdue"),
    }


async def _trigger_maintenance_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    plan: MaintenancePlan,
    vehicle: Vehicle,
    actor_id: UUID | None,
) -> WorkOrder | None:
    """Create WorkOrder if no open one exists for this plan+vehicle (D-04 de-dupe)."""
    import logging
    import time

    logger = logging.getLogger(__name__)

    # D-04: check for existing open work order linked to this plan
    existing = await db.scalar(
        select(WorkOrder).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.vehicle_id == plan.vehicle_id,
            WorkOrder.plan_id == plan.id,
            WorkOrder.status.not_in(["closed", "cancelled"]),
        )
    )
    if existing:
        logger.info(
            "Skip WO creation: open WO %s for plan %s vehicle %s",
            existing.id,
            plan.id,
            plan.vehicle_id,
        )
        return None

    # Generate work order number: MAINT-{plan_id_short}-{timestamp}
    wo_number = f"MAINT-{str(plan.id)[:8].upper()}-{int(time.time())}"

    work_order = WorkOrder(
        tenant_id=tenant_id,
        vehicle_id=plan.vehicle_id,
        plan_id=plan.id,
        work_order_number=wo_number,
        planned_work=f"Manutencao preventiva: {plan.name}",
        status="draft",
    )
    db.add(work_order)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="work_order.created_from_maintenance_plan",
        entity_type="work_order",
        entity_id=work_order.id,
        new_values={
            "plan_id": str(plan.id),
            "vehicle_id": str(plan.vehicle_id),
            "vehicle_plate": vehicle.plate,
            "work_order_number": wo_number,
        },
    )
    return work_order


async def list_spare_parts(tenant_id: UUID, db: AsyncSession):
    result = await db.execute(
        select(SparePartInventory).where(SparePartInventory.tenant_id == tenant_id).order_by(SparePartInventory.name)
    )
    return list(result.scalars().all())


async def create_spare_part(
    tenant_id: UUID,
    payload: SparePartInventoryCreate,
    db: AsyncSession
) -> SparePartInventory:
    stmt = select(SparePartInventory).where(
        SparePartInventory.tenant_id == tenant_id,
        SparePartInventory.sku == payload.sku
    )
    existing = await db.scalar(stmt)
    if existing:
        raise ApiError("SKU_EXISTS", status.HTTP_400_BAD_REQUEST, "Já existe uma peça com este SKU.")
        
    part = SparePartInventory(
        tenant_id=tenant_id,
        sku=payload.sku,
        name=payload.name,
        unit=payload.unit,
        minimum_quantity=_decimal(payload.minimum_quantity),
        current_quantity=0,
        average_unit_cost=0
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return part


async def record_spare_part_receipt(
    tenant_id: UUID,
    payload: SparePartReceiptCreate,
    actor_id: UUID,
    db: AsyncSession
) -> SparePartMovement:
    part = await db.get(SparePartInventory, payload.inventory_id)
    if not part or part.tenant_id != tenant_id:
        raise ApiError("PART_NOT_FOUND", status.HTTP_404_NOT_FOUND, "Peça não encontrada.")
        
    old_qty = part.current_quantity
    new_qty = old_qty + _decimal(payload.quantity)
    total_cost = _decimal(payload.quantity) * _decimal(payload.unit_cost)
    
    old_total_value = old_qty * part.average_unit_cost
    new_total_value = old_total_value + total_cost
    if new_qty > 0:
        part.average_unit_cost = new_total_value / new_qty
        
    part.current_quantity = new_qty
    
    movement = SparePartMovement(
        tenant_id=tenant_id,
        inventory_id=part.id,
        movement_type="receipt",
        direction="in",
        quantity=_decimal(payload.quantity),
        balance_after_quantity=new_qty,
        unit_cost=_decimal(payload.unit_cost),
        total_cost=total_cost,
        request_reference=payload.request_reference,
        source_type="manual_receipt",
        source_id=None,
        occurred_at=payload.occurred_at,
        recorded_by=actor_id,
        notes=payload.notes
    )
    db.add(movement)
    await db.commit()
    await db.refresh(movement)
    return movement


async def evaluate_maintenance_schedule_all_tenants(
    db: AsyncSession,
) -> dict:
    """Called by ARQ daily cron. Runs evaluate_maintenance_schedule for all active tenants.
    Uses BYPASSRLS DB connection (rotas_admin role via ADMIN_DATABASE_URL).
    """
    from app.modules.tenants.models import Tenant

    result = await db.execute(select(Tenant).where(Tenant.status == "active"))
    tenants = result.scalars().all()
    total_created = 0
    for tenant in tenants:
        r = await evaluate_maintenance_schedule(db, tenant.id, actor_id=None)
        total_created += r.get("created", 0)
    return {"tenants_checked": len(tenants), "work_orders_created": total_created}


async def get_imminent_maintenance_alerts(
    db: AsyncSession,
    tenant_id: UUID,
    days_ahead: int = 30,
    km_ahead: int = 500,
) -> list[dict]:
    """D-06: Return vehicles with maintenance due within days_ahead days or km_ahead km."""
    from datetime import timedelta

    from sqlalchemy import or_

    now = now_utc()
    threshold_date = now + timedelta(days=days_ahead)

    rows = await db.execute(
        select(MaintenancePlan, Vehicle)
        .join(Vehicle, Vehicle.id == MaintenancePlan.vehicle_id)
        .where(
            MaintenancePlan.tenant_id == tenant_id,
            MaintenancePlan.status == "active",
            or_(
                MaintenancePlan.next_due_at <= threshold_date,
                # due_km within km_ahead of current odometer
                (
                    (MaintenancePlan.next_due_km.isnot(None))
                    & (Vehicle.current_km + km_ahead >= MaintenancePlan.next_due_km)
                ),
            ),
        )
    )
    alerts = []
    for plan, vehicle in rows:
        overdue = (plan.next_due_at is not None and plan.next_due_at < now) or (
            plan.next_due_km is not None
            and vehicle.current_km is not None
            and vehicle.current_km >= plan.next_due_km
        )
        trigger_type = (
            "overdue"
            if overdue
            else (
                "calendar"
                if (plan.next_due_at is not None and plan.next_due_at <= threshold_date)
                else "odometer"
            )
        )
        alerts.append(
            {
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "vehicle_id": str(vehicle.id),
                "vehicle_plate": vehicle.plate,
                "next_due_at": plan.next_due_at.isoformat() if plan.next_due_at else None,
                "next_due_km": plan.next_due_km,
                "current_km": vehicle.current_km,
                "trigger_type": trigger_type,
            }
        )
    return alerts


# ---------------------------------------------------------------------------
# Task 1A: Staff pillar service functions
# ---------------------------------------------------------------------------


def serialize_staff_rate(rate: WorkshopStaffRate) -> dict:
    return {
        "id": str(rate.id),
        "tenant_id": str(rate.tenant_id),
        "user_id": str(rate.user_id),
        "hourly_rate": str(rate.hourly_rate),
        "effective_from": rate.effective_from.isoformat(),
        "created_at": rate.created_at.isoformat(),
    }


async def assign_task_to_mechanic(
    task_id: UUID,
    data: TaskAssignRequest,
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    result = await db.execute(
        select(WorkOrderTask).where(
            WorkOrderTask.id == task_id,
            WorkOrderTask.tenant_id == tenant_id,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise ApiError("task_not_found", "Task not found", status.HTTP_404_NOT_FOUND)
    task.assigned_to = data.assigned_to
    task.estimated_minutes = data.estimated_minutes
    await db.commit()
    await db.refresh(task)
    return serialize_work_order_task(task)


async def get_workshop_staff_rates(tenant_id: UUID, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(WorkshopStaffRate)
        .where(WorkshopStaffRate.tenant_id == tenant_id)
        .order_by(WorkshopStaffRate.effective_from.desc())
    )
    return [serialize_staff_rate(r) for r in result.scalars().all()]


async def create_staff_rate(
    data: WorkshopStaffRateCreate,
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    rate = WorkshopStaffRate(
        tenant_id=tenant_id,
        user_id=data.user_id,
        hourly_rate=data.hourly_rate,
        effective_from=data.effective_from,
    )
    db.add(rate)
    await db.commit()
    await db.refresh(rate)
    return serialize_staff_rate(rate)


async def get_workshop_kpis(tenant_id: UUID, db: AsyncSession) -> dict:
    # Open work orders count
    open_wo_result = await db.execute(
        select(func.count())
        .select_from(WorkOrder)
        .where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.not_in(["closed", "cancelled"]),
        )
    )
    open_work_orders = open_wo_result.scalar() or 0

    # Pending tasks count
    pending_tasks_result = await db.execute(
        select(func.count())
        .select_from(WorkOrderTask)
        .where(
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.status == "pending",
        )
    )
    pending_tasks = pending_tasks_result.scalar() or 0

    # Total labor hours from actual_minutes
    labor_minutes_result = await db.execute(
        select(func.coalesce(func.sum(WorkOrderTask.actual_minutes), 0)).where(
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.actual_minutes.isnot(None),
        )
    )
    total_labor_minutes = labor_minutes_result.scalar() or 0
    total_labor_hours = float(total_labor_minutes) / 60.0

    # Total labor cost from work_orders.labor_cost
    labor_cost_result = await db.execute(
        select(func.coalesce(func.sum(WorkOrder.labor_cost), 0)).where(
            WorkOrder.tenant_id == tenant_id,
        )
    )
    total_labor_cost = str(labor_cost_result.scalar() or 0)

    # Work orders by mechanic (JOIN users for name field)
    mechanic_result = await db.execute(
        sa_text("""
            SELECT wot.assigned_to::text AS user_id,
                   u.full_name AS name,
                   COUNT(DISTINCT wo.id) AS work_order_count,
                   COALESCE(SUM(wot.actual_minutes), 0) / 60.0 AS total_hours
            FROM work_order_tasks wot
            JOIN users u ON u.id = wot.assigned_to
            JOIN work_orders wo ON wo.id = wot.work_order_id
            WHERE wot.tenant_id = :tenant_id AND wot.assigned_to IS NOT NULL
            GROUP BY wot.assigned_to, u.full_name
        """),
        {"tenant_id": str(tenant_id)},
    )
    work_orders_by_mechanic = [
        {
            "user_id": row.user_id,
            "name": row.name,
            "work_order_count": row.work_order_count,
            "total_hours": float(row.total_hours),
        }
        for row in mechanic_result.fetchall()
    ]

    return {
        "open_work_orders": open_work_orders,
        "pending_tasks": pending_tasks,
        "total_labor_hours": total_labor_hours,
        "total_labor_cost": total_labor_cost,
        "work_orders_by_mechanic": work_orders_by_mechanic,
    }


# ---------------------------------------------------------------------------
# Task 1B: Tools pillar service functions
# ---------------------------------------------------------------------------


def serialize_tool_calibration(cal: ToolCalibration) -> dict:
    return {
        "id": str(cal.id),
        "tool_id": str(cal.tool_id),
        "calibrated_by": str(cal.calibrated_by) if cal.calibrated_by else None,
        "calibrated_at": cal.calibrated_at.isoformat(),
        "next_due_at": cal.next_due_at.isoformat(),
        "notes": cal.notes,
        "created_at": cal.created_at.isoformat(),
    }


async def record_tool_calibration(
    tool_id: UUID,
    data: ToolCalibrationCreate,
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    tool_result = await db.execute(
        select(WorkshopTool).where(
            WorkshopTool.id == tool_id,
            WorkshopTool.tenant_id == tenant_id,
        )
    )
    tool = tool_result.scalar_one_or_none()
    if tool is None:
        raise ApiError("tool_not_found", "Tool not found", status.HTTP_404_NOT_FOUND)

    cal = ToolCalibration(
        tenant_id=tenant_id,
        tool_id=tool_id,
        calibrated_by=data.calibrated_by,
        calibrated_at=data.calibrated_at,
        next_due_at=data.next_due_at,
        notes=data.notes,
    )
    db.add(cal)

    # Update tool.calibration_due_at to next_due_at
    tool.calibration_due_at = data.next_due_at

    # Auto-alert: ONLY when ALL THREE conditions are true:
    # 1. tool is critical
    # 2. calibration_interval_days is NOT None (tool has a defined interval)
    # 3. next_due_at falls within 30 days from now
    if (
        tool.is_critical
        and tool.calibration_interval_days is not None
        and data.next_due_at <= now_utc() + timedelta(days=30)
    ):
        await ensure_exception(
            db,
            tenant_id,
            entity_type="workshop_tool",
            entity_id=tool_id,
            exception_type="tool_calibration_due",
            severity="high",
            title="Calibracao da ferramenta critica vence em menos de 30 dias",
            message=(f"Calibracao vence em: {data.next_due_at.date().isoformat()}"),
            source_type="tool_calibration",
        )

    await db.commit()
    await db.refresh(cal)
    return serialize_tool_calibration(cal)


async def list_tool_calibration_history(
    tool_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> list[dict]:
    result = await db.execute(
        select(ToolCalibration)
        .where(
            ToolCalibration.tool_id == tool_id,
            ToolCalibration.tenant_id == tenant_id,
        )
        .order_by(ToolCalibration.calibrated_at.desc())
    )
    return [serialize_tool_calibration(c) for c in result.scalars().all()]


async def update_tool(
    tool_id: UUID,
    data: ToolUpdateRequest,
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    result = await db.execute(
        select(WorkshopTool).where(
            WorkshopTool.id == tool_id,
            WorkshopTool.tenant_id == tenant_id,
        )
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise ApiError("tool_not_found", "Tool not found", status.HTTP_404_NOT_FOUND)
    if data.status is not None:
        tool.status = data.status
    if data.location is not None:
        tool.location = data.location
    if data.calibration_interval_days is not None:
        tool.calibration_interval_days = data.calibration_interval_days
    if data.category is not None:
        tool.category = data.category
    await db.commit()
    await db.refresh(tool)
    return serialize_tool(tool)


# ---------------------------------------------------------------------------
# Task 1C: Serial parts service functions
# ---------------------------------------------------------------------------


def serialize_serial_item(item: SparePartSerialItem) -> dict:
    return {
        "id": str(item.id),
        "part_id": str(item.part_id),
        "serial_number": item.serial_number,
        "status": item.status,
        "vehicle_id": str(item.vehicle_id) if item.vehicle_id else None,
        "installed_at": item.installed_at.isoformat() if item.installed_at else None,
        "scrapped_at": item.scrapped_at.isoformat() if item.scrapped_at else None,
        "notes": item.notes,
        "created_at": item.created_at.isoformat(),
    }


async def register_serial_item(
    part_id: UUID,
    data: SerialItemCreate,
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    part_result = await db.execute(
        select(SparePartInventory).where(
            SparePartInventory.id == part_id,
            SparePartInventory.tenant_id == tenant_id,
        )
    )
    if part_result.scalar_one_or_none() is None:
        raise ApiError("part_not_found", "Spare part not found", status.HTTP_404_NOT_FOUND)

    item = SparePartSerialItem(
        tenant_id=tenant_id,
        part_id=part_id,
        serial_number=data.serial_number,
        notes=data.notes,
        status="in_stock",
    )
    try:
        db.add(item)
        await db.commit()
        await db.refresh(item)
    except Exception as exc:
        await db.rollback()
        raise ApiError(
            "serial_number_exists",
            "Serial number already registered for this tenant",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return serialize_serial_item(item)


async def install_serial_item(
    serial_id: UUID,
    vehicle_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> dict:
    result = await db.execute(
        select(SparePartSerialItem).where(
            SparePartSerialItem.id == serial_id,
            SparePartSerialItem.tenant_id == tenant_id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise ApiError("serial_item_not_found", "Serial item not found", status.HTTP_404_NOT_FOUND)
    if item.status != "in_stock":
        raise ApiError(
            "serial_item_not_in_stock",
            "Serial item is not available for installation",
            status.HTTP_409_CONFLICT,
        )

    item.status = "installed"
    item.vehicle_id = vehicle_id
    item.installed_at = now_utc()

    part_result = await db.execute(
        select(SparePartInventory).where(SparePartInventory.id == item.part_id)
    )
    part = part_result.scalar_one()
    new_quantity = (part.current_quantity or Decimal("0")) - Decimal("1")
    movement = SparePartMovement(
        tenant_id=tenant_id,
        inventory_id=item.part_id,
        movement_type="serial_install",
        direction="out",
        quantity=Decimal("1"),
        balance_after_quantity=new_quantity,
        unit_cost=part.average_unit_cost,
        total_cost=part.average_unit_cost,
        request_reference=f"serial-install-{serial_id}",
        source_type="spare_part_serial_item",
        source_id=serial_id,
        occurred_at=now_utc(),
    )
    db.add(movement)
    part.current_quantity = new_quantity

    await db.commit()
    await db.refresh(item)
    return serialize_serial_item(item)


async def get_installed_parts_for_vehicle(
    vehicle_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> list[dict]:
    result = await db.execute(
        select(SparePartSerialItem).where(
            SparePartSerialItem.tenant_id == tenant_id,
            SparePartSerialItem.vehicle_id == vehicle_id,
            SparePartSerialItem.status == "installed",
        )
    )
    return [serialize_serial_item(i) for i in result.scalars().all()]


async def list_low_stock_parts(tenant_id: UUID, db: AsyncSession) -> dict:
    result = await db.execute(
        select(SparePartInventory).where(
            SparePartInventory.tenant_id == tenant_id,
            SparePartInventory.status == "active",
            SparePartInventory.current_quantity <= SparePartInventory.minimum_quantity,
        )
    )
    items = result.scalars().all()
    serialized = [
        {
            "id": str(p.id),
            "sku": p.sku,
            "name": p.name,
            "current_quantity": str(p.current_quantity),
            "minimum_quantity": str(p.minimum_quantity),
            "reorder_quantity": p.reorder_quantity,
            "supplier_name": p.supplier_name,
            "lead_time_days": p.lead_time_days,
        }
        for p in items
    ]
    return {"items": serialized, "total": len(serialized)}


async def _find_spare_part_movement(
    db: AsyncSession,
    tenant_id: UUID,
    request_reference: str,
) -> SparePartMovement | None:
    return await db.scalar(
        select(SparePartMovement).where(
            SparePartMovement.tenant_id == tenant_id,
            SparePartMovement.request_reference == request_reference,
        )
    )


def _validate_spare_part_replay(
    item: SparePartMovement,
    inventory_id: UUID,
    movement_type: str,
    direction: str,
    quantity: Decimal,
    unit_cost: float | Decimal | None,
) -> None:
    expected_unit_cost = _decimal(unit_cost) if unit_cost is not None else None
    if (
        item.inventory_id != inventory_id
        or item.movement_type != movement_type
        or item.direction != direction
        or _decimal(item.quantity) != quantity
        or (expected_unit_cost is not None and _decimal(item.unit_cost or 0) != expected_unit_cost)
    ):
        raise ApiError(
            "spare_part_request_reference_reused",
            "Request reference was reused with a different payload.",
            status_code=409,
        )


def _validate_maintenance_part_replay(
    item: MaintenancePartUsed,
    work_order_id: UUID,
    payload: MaintenancePartIssueCreate,
) -> None:
    if (
        item.work_order_id != work_order_id
        or item.inventory_id != payload.inventory_id
        or _decimal(item.quantity) != _decimal(payload.quantity)
    ):
        raise ApiError(
            "maintenance_part_request_reference_reused",
            "Request reference was reused with a different payload.",
            status_code=409,
        )


def _validate_tool_checkout_replay(
    item: ToolCheckout,
    work_order_id: UUID,
    payload: ToolCheckoutCreate,
) -> None:
    if (
        item.work_order_id != work_order_id
        or item.tool_id != payload.tool_id
        or item.checked_out_at != payload.checked_out_at
        or item.due_at != payload.due_at
    ):
        raise ApiError(
            "tool_checkout_reference_reused",
            "Checkout reference was reused with a different payload.",
            status_code=409,
        )


async def _require_vehicle(db: AsyncSession, tenant_id: UUID, vehicle_id: UUID) -> Vehicle:
    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)
    return vehicle


async def _require_maintenance_request(
    db: AsyncSession,
    tenant_id: UUID,
    request_id: UUID,
) -> MaintenanceRequest:
    item = await db.get(MaintenanceRequest, request_id)
    if not item or item.tenant_id != tenant_id:
        raise ApiError(
            "maintenance_request_not_found",
            "Maintenance request not found.",
            status_code=404,
        )
    return item


async def _require_work_order(db: AsyncSession, tenant_id: UUID, item_id: UUID) -> WorkOrder:
    item = await db.get(WorkOrder, item_id)
    if not item or item.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)
    return item


async def _validate_trip_and_incident(
    db: AsyncSession,
    tenant_id: UUID,
    payload: MaintenanceRequestCreate,
) -> None:
    if payload.trip_id:
        trip = await db.get(Trip, payload.trip_id)
        if not trip or trip.tenant_id != tenant_id or trip.vehicle_id != payload.vehicle_id:
            raise ApiError("trip_not_found", "Trip not found for vehicle.", status_code=404)
    if payload.incident_id:
        incident = await db.get(TripIncident, payload.incident_id)
        if (
            not incident
            or incident.tenant_id != tenant_id
            or incident.vehicle_id != payload.vehicle_id
            or (payload.trip_id and incident.trip_id != payload.trip_id)
        ):
            raise ApiError(
                "trip_incident_not_found",
                "Trip incident not found for vehicle.",
                status_code=404,
            )


# ── Maintenance Request Notes & Status ──────────────────────────────────────────────

from app.modules.workshop.models import MaintenanceRequestNote
from app.modules.workshop.schemas import MaintenanceRequestNoteCreate, MaintenanceRequestStatusUpdate


def serialize_maintenance_request_note(item: MaintenanceRequestNote) -> dict:
    return {
        "id": item.id,
        "author_id": item.author_id,
        "body": item.body,
        "created_at": item.created_at,
    }


async def add_maintenance_request_note(
    db: AsyncSession,
    tenant_id: UUID,
    request_id: UUID,
    payload: MaintenanceRequestNoteCreate,
    actor_id: UUID,
) -> dict:
    req = await _require_maintenance_request(db, tenant_id, request_id)
    note = MaintenanceRequestNote(
        tenant_id=tenant_id,
        maintenance_request_id=req.id,
        author_id=actor_id,
        body=payload.body,
    )
    db.add(note)
    
    await record_audit_log(
        db,
        tenant_id,
        actor_id,
        "workshop.maintenance_request.note_added",
        "maintenance_request",
        req.id,
        {"body": payload.body},
    )
    
    await db.commit()
    await db.refresh(note)
    return serialize_maintenance_request_note(note)


async def list_maintenance_request_notes(
    db: AsyncSession,
    tenant_id: UUID,
    request_id: UUID,
) -> list[dict]:
    req = await _require_maintenance_request(db, tenant_id, request_id)
    stmt = (
        select(MaintenanceRequestNote)
        .where(
            MaintenanceRequestNote.tenant_id == tenant_id,
            MaintenanceRequestNote.maintenance_request_id == req.id,
        )
        .order_by(MaintenanceRequestNote.created_at.desc())
    )
    result = await db.execute(stmt)
    return [serialize_maintenance_request_note(r) for r in result.scalars().all()]


async def update_maintenance_request_status(
    db: AsyncSession,
    tenant_id: UUID,
    request_id: UUID,
    payload: MaintenanceRequestStatusUpdate,
    actor_id: UUID,
) -> dict:
    req = await _require_maintenance_request(db, tenant_id, request_id)
    old_status = req.status
    req.status = payload.status
    
    await record_audit_log(
        db,
        tenant_id,
        actor_id,
        "workshop.maintenance_request.status_updated",
        "maintenance_request",
        req.id,
        {"old_status": old_status, "new_status": payload.status},
    )
    
    await db.commit()
    await db.refresh(req)
    return serialize_maintenance_request(req)

