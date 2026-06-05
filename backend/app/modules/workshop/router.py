from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.database import get_session
from app.modules.workshop import schemas, service

router = APIRouter(prefix="/workshop", tags=["workshop"])


@router.get("/maintenance-requests")
async def list_maintenance_requests(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
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


@router.post("/maintenance-requests")
async def create_maintenance_request(
    payload: schemas.MaintenanceRequestCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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


@router.get("/work-orders")
async def list_work_orders(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
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


@router.post("/work-orders")
async def create_work_order(
    payload: schemas.WorkOrderCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
        handler=lambda: service.create_work_order(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/work-orders/{work_order_id}/approve")
async def approve_work_order(
    work_order_id: UUID,
    payload: schemas.WorkOrderApproveRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.close_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload,
        actor_id=principal.user_id,
    )


@router.post("/work-orders/{work_order_id}/start")
async def start_work_order(
    work_order_id: UUID,
    payload: schemas.WorkOrderTransitionRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.start_work_order(
        db, principal.tenant_id, work_order_id, payload, actor_id=principal.user_id
    )


@router.post("/work-orders/{work_order_id}/quality-check")
async def send_work_order_to_quality_check(
    work_order_id: UUID,
    payload: schemas.WorkOrderTransitionRequest,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.send_work_order_to_quality_check(
        db, principal.tenant_id, work_order_id, payload, actor_id=principal.user_id
    )


@router.get("/work-orders/{work_order_id}/tasks")
async def list_work_order_tasks(
    work_order_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_work_order_tasks(db, principal.tenant_id, work_order_id)


@router.post("/work-orders/{work_order_id}/tasks")
async def create_work_order_task(
    work_order_id: UUID,
    payload: schemas.WorkOrderTaskCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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


@router.get("/spare-parts")
async def list_spare_parts(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_spare_parts(db, principal.tenant_id)


@router.post("/spare-parts")
async def create_spare_part(
    payload: schemas.SparePartInventoryCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
        handler=lambda: service.create_spare_part(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/spare-parts/receipts")
async def receive_spare_part(
    payload: schemas.SparePartReceiptCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.receive_spare_part(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("/spare-part-movements")
async def list_spare_part_movements(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    inventory_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    return await service.list_spare_part_movements(
        db, principal.tenant_id, inventory_id=inventory_id, limit=limit
    )


@router.post("/work-orders/{work_order_id}/parts")
async def issue_spare_part_to_work_order(
    work_order_id: UUID,
    payload: schemas.MaintenancePartIssueCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.issue_spare_part_to_work_order(
        db,
        principal.tenant_id,
        work_order_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/tools")
async def list_tools(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_tools(db, principal.tenant_id)


@router.post("/tools")
async def create_tool(
    payload: schemas.WorkshopToolCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
        handler=lambda: service.create_tool(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.get("/tool-checkouts")
async def list_tool_checkouts(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    return await service.list_tool_checkouts(
        db, principal.tenant_id, status_filter=status, limit=limit
    )


@router.post("/work-orders/{work_order_id}/tool-checkouts")
async def checkout_tool(
    work_order_id: UUID,
    payload: schemas.ToolCheckoutCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
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
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.return_tool(
        db, principal.tenant_id, checkout_id, payload, actor_id=principal.user_id
    )


@router.get("/maintenance-plans")
async def list_maintenance_plans(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_maintenance_plans(db, principal.tenant_id)


@router.post("/maintenance-plans")
async def create_maintenance_plan(
    payload: schemas.MaintenancePlanCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_maintenance_plan(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get("/maintenance-schedule")
async def list_maintenance_schedule(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
):
    return await service.list_maintenance_schedule(
        db, principal.tenant_id, status_filter=status
    )


@router.post("/maintenance-schedule/evaluate")
async def evaluate_maintenance_schedule(
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.evaluate_maintenance_schedule(
        db, principal.tenant_id, actor_id=principal.user_id
    )


@router.get("/imminent-alerts")
async def get_imminent_maintenance_alerts(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    days_ahead: int = Query(30, ge=1, le=365),
    km_ahead: int = Query(500, ge=0, le=100000),
):
    return await service.get_imminent_maintenance_alerts(
        db, principal.tenant_id, days_ahead=days_ahead, km_ahead=km_ahead
    )
