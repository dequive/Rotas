from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.deps import get_session
from app.core.errors import ApiError
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import (
    BILLING_ISSUE,
    WORKSHOP_APPROVE,
    WORKSHOP_CLOSE,
    WORKSHOP_EXECUTE,
    WORKSHOP_FINANCE_READ,
    WORKSHOP_INVENTORY_ADJUST,
    WORKSHOP_PARTS_ISSUE,
    WORKSHOP_QUALITY_CHECK,
    WORKSHOP_READ,
    WORKSHOP_RELEASE,
    WORKSHOP_WRITE,
    require_permission,
)
from app.modules.tenants.models import TenantDocumentProfile
from app.modules.vehicles.models import Vehicle
from app.modules.workshop import schemas, service
from app.modules.workshop.detail_schemas import WorkOrderDetailResponse
from app.modules.workshop.exporters import render_spare_part_movement, render_work_order
from app.modules.workshop.models import WorkOrder, WorkOrderTask

router = APIRouter(prefix="/workshop", tags=["workshop"])


@router.get(
    "/maintenance-requests",
    response_model=list[schemas.MaintenanceRequestResponse],
)
async def list_maintenance_requests(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    return await service.list_maintenance_requests(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        limit=limit,
    )


@router.post(
    "/maintenance-requests",
    response_model=schemas.MaintenanceRequestResponse,
)
async def create_maintenance_request(
    payload: schemas.MaintenanceRequestCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="workshop.maintenance_request.create",
        entity_type="maintenance_request",
        payload=payload,
        handler=lambda: service.create_maintenance_request(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.get(
    "/maintenance-requests/{request_id}",
    response_model=schemas.MaintenanceRequestResponse,
)
async def get_maintenance_request(
    request_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_maintenance_request(db, principal.tenant_id, request_id)


@router.get("/work-orders", response_model=list[schemas.WorkOrderResponse])
async def list_work_orders(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    return await service.list_work_orders(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        limit=limit,
    )


@router.get("/work-orders/{work_order_id}", response_model=WorkOrderDetailResponse)
async def get_work_order_detail(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    from app.modules.workshop.detail_service import get_work_order_detail as _get_detail

    return await _get_detail(db, principal.tenant_id, work_order_id)


@router.post("/work-orders", response_model=schemas.WorkOrderResponse)
async def create_work_order(
    payload: schemas.WorkOrderCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="workshop.work_order.create",
        entity_type="work_order",
        payload=payload,
        handler=lambda: service.create_work_order(db, principal.tenant_id, payload, actor_id=principal.user_id),
    )


@router.post("/work-orders/{work_order_id}/approve")
async def approve_work_order(
    work_order_id: UUID,
    payload: schemas.WorkOrderApproveRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_APPROVE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.approve_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post("/work-orders/{work_order_id}/close")
async def close_work_order(
    work_order_id: UUID,
    payload: schemas.WorkOrderCloseRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_CLOSE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.close_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post("/work-orders/{work_order_id}/billing/retry")
async def retry_work_order_billing(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_CLOSE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.retry_work_order_billing(
        db,
        principal.tenant_id,
        work_order_id,
        actor_id=principal.user_id,
    )


@router.post("/work-orders/{work_order_id}/invoice")
async def generate_workshop_invoice(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """POST /workshop/work-orders/{id}/invoice — Gerar rascunho de fatura fiscal a partir de OS concluída."""
    from app.modules.workshop.workshop_billing_service import create_workshop_invoice

    return await create_workshop_invoice(
        db,
        principal.tenant_id,
        work_order_id,
        actor_id=principal.user_id,
    )


@router.post("/invoices/{document_id}/confirm")
async def confirm_workshop_invoice(
    document_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(BILLING_ISSUE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """POST /workshop/invoices/{id}/confirm — Emitir fiscalmente a fatura (atribui número sequencial, imutável)."""
    from app.modules.workshop.workshop_billing_service import confirm_workshop_invoice as _confirm

    return await _confirm(
        db,
        principal.tenant_id,
        document_id,
        actor_id=principal.user_id,
    )


@router.post("/work-orders/{work_order_id}/start")
async def start_work_order(
    work_order_id: UUID,
    payload: schemas.WorkOrderTransitionRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_EXECUTE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.start_work_order(db, principal.tenant_id, work_order_id, payload, actor_id=principal.user_id)


@router.post("/work-orders/{work_order_id}/quality-check")
async def send_work_order_to_quality_check(
    work_order_id: UUID,
    payload: schemas.WorkOrderTransitionRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_QUALITY_CHECK))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.send_work_order_to_quality_check(
        db, principal.tenant_id, work_order_id, payload, actor_id=principal.user_id
    )


@router.get("/work-orders/{work_order_id}/tasks")
async def list_work_order_tasks(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_work_order_tasks(db, principal.tenant_id, work_order_id)


@router.post("/work-orders/{work_order_id}/tasks")
async def create_work_order_task(
    work_order_id: UUID,
    payload: schemas.WorkOrderTaskCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_EXECUTE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="workshop.work_order_task.create",
        entity_type="work_order_task",
        payload={"work_order_id": work_order_id, **payload.model_dump()},
        handler=lambda: service.create_work_order_task(
            db, principal.tenant_id, work_order_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/work-orders/{work_order_id}/tasks/{task_id}/complete")
async def complete_work_order_task(
    work_order_id: UUID,
    task_id: UUID,
    payload: schemas.WorkOrderTaskCompleteRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_EXECUTE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.complete_work_order_task(
        db,
        principal.tenant_id,
        work_order_id,
        task_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/spare-parts", response_model=list[schemas.SparePartInventoryResponse])
async def list_spare_parts(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_spare_parts(db, principal.tenant_id)


@router.post("/spare-parts", response_model=schemas.SparePartInventoryResponse)
async def create_spare_part(
    payload: schemas.SparePartInventoryCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="workshop.spare_part.create",
        entity_type="spare_part_inventory",
        payload=payload,
        handler=lambda: service.create_spare_part(db, principal.tenant_id, payload, actor_id=principal.user_id),
    )


@router.post("/spare-parts/receipts")
async def receive_spare_part(
    payload: schemas.SparePartReceiptCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.receive_spare_part(db, principal.tenant_id, payload, actor_id=principal.user_id)


@router.get("/spare-part-movements")
async def list_spare_part_movements(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    inventory_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    return await service.list_spare_part_movements(db, principal.tenant_id, inventory_id=inventory_id, limit=limit)


@router.get("/spare-part-movements/{movement_id}/pdf")
async def download_spare_part_movement_pdf(
    movement_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    from app.modules.workshop.models import SparePartInventory, SparePartMovement

    movement = await db.scalar(
        select(SparePartMovement).where(
            SparePartMovement.id == movement_id,
            SparePartMovement.tenant_id == principal.tenant_id,
        )
    )
    if movement is None:
        raise HTTPException(status_code=404, detail="Movement not found")

    part = await db.scalar(
        select(SparePartInventory).where(
            SparePartInventory.id == movement.inventory_id,
            SparePartInventory.tenant_id == principal.tenant_id,
        )
    )

    prof_row = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == principal.tenant_id)
    )
    profile = (
        {
            "legal_name": prof_row.legal_name,
            "address_line1": prof_row.address_line1,
            "address_line2": prof_row.address_line2,
            "city": prof_row.city,
            "phone": prof_row.phone,
            "email": prof_row.email,
        }
        if prof_row
        else None
    )

    pdf_bytes = render_spare_part_movement(movement, part, profile=profile)

    mov_type = movement.movement_type or "movement"
    prefix = "req-interna" if mov_type == "work_order_issue" else "req-externa"
    ref = (movement.request_reference or str(movement_id))[:30].replace(" ", "-")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={prefix}-{ref}.pdf"},
    )


@router.post("/work-orders/{work_order_id}/parts")
async def issue_spare_part_to_work_order(
    work_order_id: UUID,
    payload: schemas.MaintenancePartIssueCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.issue_spare_part_to_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/tools", response_model=list[schemas.WorkshopToolResponse])
async def list_tools(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_tools(db, principal.tenant_id)


@router.post("/tools")
async def create_tool(
    payload: schemas.WorkshopToolCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="workshop.tool.create",
        entity_type="workshop_tool",
        payload=payload,
        handler=lambda: service.create_tool(db, principal.tenant_id, payload, actor_id=principal.user_id),
    )


@router.get("/tool-checkouts")
async def list_tool_checkouts(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    return await service.list_tool_checkouts(db, principal.tenant_id, status_filter=status, limit=limit)


@router.post("/work-orders/{work_order_id}/tool-checkouts")
async def checkout_tool(
    work_order_id: UUID,
    payload: schemas.ToolCheckoutCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.checkout_tool(
        db,
        principal.tenant_id,
        work_order_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post("/tool-checkouts/{checkout_id}/return")
async def return_tool(
    checkout_id: UUID,
    payload: schemas.ToolReturnCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.return_tool(db, principal.tenant_id, checkout_id, payload, actor_id=principal.user_id)


@router.get("/maintenance-plans")
async def list_maintenance_plans(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_maintenance_plans(db, principal.tenant_id)


@router.post("/maintenance-plans")
async def create_maintenance_plan(
    payload: schemas.MaintenancePlanCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_maintenance_plan(db, principal.tenant_id, payload, actor_id=principal.user_id)


@router.get("/maintenance-schedule")
async def list_maintenance_schedule(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
):
    return await service.list_maintenance_schedule(db, principal.tenant_id, status_filter=status)


@router.post("/maintenance-schedule/evaluate")
async def evaluate_maintenance_schedule(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.evaluate_maintenance_schedule(db, principal.tenant_id, actor_id=principal.user_id)


@router.get(
    "/imminent-alerts",
    response_model=list[schemas.ImminentMaintenanceAlertResponse],
)
async def get_imminent_maintenance_alerts(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    days_ahead: int = Query(30, ge=1, le=365),
    km_ahead: int = Query(500, ge=0, le=100000),
):
    return await service.get_imminent_maintenance_alerts(
        db, principal.tenant_id, days_ahead=days_ahead, km_ahead=km_ahead
    )


# ---------------------------------------------------------------------------
# New endpoints — Task 2A (Wave 3)
# All mutations use WORKSHOP_WRITE (includes mechanic).
# Reads use WORKSHOP_READ (includes viewer + mechanic).
# Existing 18 endpoints above are unchanged.
# ---------------------------------------------------------------------------


@router.get("/kpis")
async def get_workshop_kpis(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_workshop_kpis(principal.tenant_id, db)


@router.patch("/work-orders/{work_order_id}/tasks/{task_id}")
async def assign_task(
    work_order_id: UUID,
    task_id: UUID,
    payload: schemas.TaskAssignRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_EXECUTE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.assign_task_to_mechanic(task_id, payload, principal.tenant_id, db)


@router.get("/staff-rates")
async def list_staff_rates(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_workshop_staff_rates(principal.tenant_id, db)


@router.post("/staff-rates", status_code=201)
async def create_staff_rate(
    payload: schemas.WorkshopStaffRateCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_staff_rate(payload, principal.tenant_id, db)


@router.post("/tools/{tool_id}/calibrations", status_code=201)
async def record_calibration(
    tool_id: UUID,
    payload: schemas.ToolCalibrationCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.record_tool_calibration(tool_id, payload, principal.tenant_id, db)


@router.get(
    "/tools/{tool_id}/calibration-history",
    response_model=list[schemas.ToolCalibrationResponse],
)
async def get_calibration_history(
    tool_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_tool_calibration_history(tool_id, principal.tenant_id, db)


@router.patch("/tools/{tool_id}")
async def patch_tool(
    tool_id: UUID,
    payload: schemas.ToolUpdateRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.update_tool(tool_id, payload, principal.tenant_id, db)


# IMPORTANT: /spare-parts/low-stock MUST appear before /spare-parts/{part_id}/serials
# so FastAPI does not attempt to parse "low-stock" as a UUID path parameter.
@router.get("/spare-parts/low-stock", response_model=schemas.LowStockListResponse)
async def get_low_stock(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_low_stock_parts(principal.tenant_id, db)


@router.post("/spare-parts/{part_id}/serials", status_code=201)
async def register_serial(
    part_id: UUID,
    payload: schemas.SerialItemCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.register_serial_item(part_id, payload, principal.tenant_id, db)


@router.post("/spare-parts/serials/{serial_id}/install")
async def install_serial(
    serial_id: UUID,
    payload: schemas.SerialItemInstallRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.install_serial_item(serial_id, payload.vehicle_id, principal.tenant_id, db)


@router.get(
    "/vehicles/{vehicle_id}/installed-parts",
    response_model=list[schemas.SerialItemResponse],
)
async def get_installed_parts(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_installed_parts_for_vehicle(vehicle_id, principal.tenant_id, db)


# ── WORKSHOP_RELEASE: vehicle release after maintenance ───────────────────────
# Note: No explicit release-vehicle endpoint exists in current router.
# WORKSHOP_RELEASE is reserved for future use when such an endpoint is added.
# The constant is imported and available via app.core.rbac.
_ = WORKSHOP_RELEASE  # keep import live for future endpoint


@router.get("/work-orders/{work_order_id}/pdf")
async def download_work_order_pdf(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    wo_row = await db.execute(
        select(WorkOrder).where(WorkOrder.id == work_order_id, WorkOrder.tenant_id == principal.tenant_id)
    )
    work_order = wo_row.scalar_one_or_none()
    if work_order is None:
        raise HTTPException(status_code=404, detail="Work order not found")

    vehicle = None
    if work_order.vehicle_id:
        v_row = await db.execute(select(Vehicle).where(Vehicle.id == work_order.vehicle_id))
        vehicle = v_row.scalar_one_or_none()

    tasks_row = await db.execute(
        select(WorkOrderTask).where(WorkOrderTask.work_order_id == work_order_id).order_by(WorkOrderTask.created_at)
    )
    tasks = list(tasks_row.scalars().all())

    prof_row = await db.execute(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == principal.tenant_id)
    )
    prof_obj = prof_row.scalar_one_or_none()
    profile = (
        {
            "legal_name": prof_obj.legal_name,
            "address_line1": prof_obj.address_line1,
            "address_line2": prof_obj.address_line2,
            "city": prof_obj.city,
            "phone": prof_obj.phone,
            "email": prof_obj.email,
        }
        if prof_obj
        else None
    )

    vehicle_dict = (
        {
            "plate": vehicle.plate,
            "brand": vehicle.brand,
            "model": vehicle.model,
            "current_km": vehicle.current_km,
        }
        if vehicle
        else None
    )

    pdf_bytes = render_work_order(work_order, tasks=tasks, vehicle=vehicle_dict, profile=profile)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ordem-servico-{work_order_id}.pdf"},
    )


@router.post(
    "/maintenance-requests/{request_id}/notes",
    response_model=schemas.MaintenanceRequestNoteResponse,
)
async def add_maintenance_request_note(
    request_id: UUID,
    payload: schemas.MaintenanceRequestNoteCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    actor_id = principal.user_id
    if actor_id is None:
        raise ApiError(
            "user_identity_required",
            "A user identity is required to author a maintenance request note.",
            status_code=403,
        )
    return await service.add_maintenance_request_note(
        db,
        principal.tenant_id,
        request_id,
        payload,
        actor_id=actor_id,
    )


@router.get(
    "/maintenance-requests/{request_id}/notes",
    response_model=list[schemas.MaintenanceRequestNoteResponse],
)
async def list_maintenance_request_notes(
    request_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_maintenance_request_notes(db, principal.tenant_id, request_id)


@router.patch(
    "/maintenance-requests/{request_id}/status",
    response_model=schemas.MaintenanceRequestResponse,
)
async def update_maintenance_request_status(
    request_id: UUID,
    payload: schemas.MaintenanceRequestStatusUpdate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.update_maintenance_request_status(
        db,
        principal.tenant_id,
        request_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post(
    "/spare-parts/{part_id}/movements",
    status_code=201,
    response_model=schemas.SparePartMovementResponse,
)
async def record_spare_part_receipt(
    part_id: UUID,
    payload: schemas.SparePartReceiptCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # Ensure payload.inventory_id matches URL param to avoid confusion
    payload.inventory_id = part_id
    return await service.record_spare_part_receipt(principal.tenant_id, payload, principal.user_id, db)


# --- Advanced Inventory & Requisition Endpoints ---


@router.post("/work-orders/{work_order_id}/parts/issue")
async def issue_parts_for_work_order(
    work_order_id: UUID,
    payload: schemas.PartIssueRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_PARTS_ISSUE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Entregar peças/óleos com lock FOR UPDATE e verificação de aprovação."""
    from app.modules.workshop import inventory_service

    return await inventory_service.issue_parts_for_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload.inventory_id,
        payload.quantity,
        actor_id=principal.user_id,
        notes=payload.notes,
    )


@router.post("/work-orders/{work_order_id}/parts/return")
async def return_part_from_work_order(
    work_order_id: UUID,
    payload: schemas.PartReturnRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_PARTS_ISSUE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Devolver sobras ao stock; bloqueia com 409 se a OS estiver fechada/facturada."""
    from app.modules.workshop import inventory_service

    return await inventory_service.return_part_from_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload.inventory_id,
        payload.quantity,
        reason=payload.reason,
        actor_id=principal.user_id,
    )


@router.post("/work-orders/{work_order_id}/cancel")
async def cancel_work_order(
    work_order_id: UUID,
    reason: Annotated[str, Query(min_length=1)],
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Cancelar OS, libertar reservas órfãs e anular eventual invoice draft."""
    from app.modules.workshop import inventory_service

    return await inventory_service.cancel_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        reason=reason,
        actor_id=principal.user_id,
    )


@router.post("/spare-parts/adjust")
async def record_inventory_adjustment(
    payload: schemas.InventoryAdjustmentRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_INVENTORY_ADJUST))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Ajustar stock por perda residual; requer WORKSHOP_INVENTORY_ADJUST."""
    from app.modules.workshop import inventory_service

    return await inventory_service.record_inventory_adjustment(
        db,
        principal.tenant_id,
        payload.inventory_id,
        payload.quantity,
        payload.direction,
        payload.reason,
        actor_id=principal.user_id,
    )


@router.get("/spare-parts/reorder-suggestions")
async def get_reorder_suggestions(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Listar peças em risco de rotura com rastreabilidade de orçamentos."""
    from app.modules.workshop import inventory_service

    return await inventory_service.get_reorder_suggestions(db, principal.tenant_id)


@router.get("/spare-parts/valuation")
async def get_inventory_valuation_summary(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """GET /workshop/spare-parts/valuation — Balancete de valorização de stock total e por categoria."""
    from app.modules.workshop import inventory_service

    return await inventory_service.get_inventory_valuation_summary(db, principal.tenant_id)


# --- Preventive Maintenance Endpoints ---


@router.post("/preventive/plans", status_code=201)
async def create_preventive_plan(
    payload: schemas.MaintenancePlanCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """POST /workshop/preventive/plans — Criar novo plano de manutenção preventiva."""
    from app.modules.workshop import preventive_service

    return await preventive_service.create_maintenance_plan(
        db,
        principal.tenant_id,
        payload.name,
        service_catalog_item_id=payload.service_catalog_item_id,
        vehicle_id=payload.vehicle_id,
        interval_km=payload.interval_km,
        interval_days=payload.interval_days,
        ownership_scope=payload.ownership_scope,
        actor_id=principal.user_id,
    )


@router.get("/preventive/plans")
async def list_preventive_plans(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    ownership_scope: str | None = Query(default=None),
):
    """GET /workshop/preventive/plans — Listar planos de manutenção preventiva."""
    from app.modules.workshop import preventive_service

    return await preventive_service.list_maintenance_plans(db, principal.tenant_id, ownership_scope=ownership_scope)


@router.post("/preventive/schedules", status_code=201)
async def schedule_preventive_maintenance(
    payload: schemas.PreventiveScheduleCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """POST /workshop/preventive/schedules — Agendar manutenção preventiva (com dedup estrito)."""
    from app.modules.workshop import preventive_service

    return await preventive_service.schedule_preventive_maintenance(
        db,
        principal.tenant_id,
        payload.vehicle_id,
        payload.plan_id,
        actor_id=principal.user_id,
    )


@router.post("/preventive/schedules/{schedule_id}/convert")
async def convert_schedule_to_action(
    schedule_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Converter agendamento em OS de frota ou orçamento draft de cliente."""
    from app.modules.workshop import preventive_service

    return await preventive_service.convert_schedule_to_action(
        db, principal.tenant_id, schedule_id, actor_id=principal.user_id
    )


# --- Labor Tracking & OS Profitability Endpoints ---


@router.post("/tasks/{task_id}/labor", status_code=201)
async def add_task_labor_session(
    task_id: UUID,
    payload: schemas.TaskLaborCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_EXECUTE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """POST /workshop/tasks/{task_id}/labor — Registrar sessão de mão de obra efetuada numa tarefa."""
    from app.modules.workshop import labor_service

    return await labor_service.add_task_labor_session(
        db,
        principal.tenant_id,
        task_id,
        payload.user_id,
        payload.minutes_worked,
        started_at=payload.started_at,
        completed_at=payload.completed_at,
        actor_id=principal.user_id,
    )


@router.post("/labor-logs/{labor_log_id}/void")
async def void_task_labor_session(
    labor_log_id: UUID,
    payload: schemas.TaskLaborVoid,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_EXECUTE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Estornar sessão de mão de obra errónea com justificativa."""
    from app.modules.workshop import labor_service

    return await labor_service.void_task_labor_session(
        db, principal.tenant_id, labor_log_id, payload.void_reason, actor_id=principal.user_id
    )


@router.get(
    "/work-orders/{work_order_id}/profitability",
    response_model=schemas.WorkOrderProfitabilityResponse,
)
async def get_work_order_profitability(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_FINANCE_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Obter relatório de margem bruta e rentabilidade direta da OS."""
    from app.modules.workshop import labor_service

    return await labor_service.get_work_order_profitability(db, principal.tenant_id, work_order_id)


@router.get("/profitability/summary", response_model=schemas.ProfitabilitySummaryResponse)
async def get_workshop_profitability_summary(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_FINANCE_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    client_id: UUID | None = Query(None),
    vehicle_id: UUID | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """GET /api/v1/workshop/profitability/summary — Relatório consolidado de rentabilidade da oficina."""
    from app.modules.workshop import labor_service

    return await labor_service.get_workshop_profitability_summary(
        db,
        principal.tenant_id,
        start_date=start_date,
        end_date=end_date,
        client_id=client_id,
        vehicle_id=vehicle_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )
