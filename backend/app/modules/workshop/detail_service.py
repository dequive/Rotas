from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.clients.models import Client
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenancePartUsed,
    SparePartInventory,
    TaskLaborLog,
    ToolCheckout,
    WorkOrder,
    WorkOrderTask,
    WorkshopTool,
)
from app.modules.workshop.quote_models import WorkshopQuote
from app.modules.workshop.reception_models import ReceptionPhoto, VehicleReception


def _money(value: Decimal | None) -> float:
    return float(value or Decimal("0"))


async def get_work_order_detail(db: AsyncSession, tenant_id: UUID, work_order_id: UUID) -> dict:
    wo = await db.scalar(
        select(WorkOrder).where(WorkOrder.id == work_order_id, WorkOrder.tenant_id == tenant_id)
    )
    if wo is None:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    vehicle = None
    if wo.vehicle_id:
        vehicle = await db.scalar(
            select(Vehicle).where(Vehicle.id == wo.vehicle_id, Vehicle.tenant_id == tenant_id)
        )

    reception = None
    photos: list[ReceptionPhoto] = []
    if wo.reception_id:
        reception = await db.scalar(
            select(VehicleReception).where(
                VehicleReception.id == wo.reception_id,
                VehicleReception.tenant_id == tenant_id,
            )
        )
        if reception:
            photo_rows = await db.execute(
                select(ReceptionPhoto)
                .where(
                    ReceptionPhoto.reception_id == reception.id,
                    ReceptionPhoto.tenant_id == tenant_id,
                )
                .order_by(ReceptionPhoto.taken_at)
            )
            photos = list(photo_rows.scalars().all())

    quote_rows = await db.execute(
        select(WorkshopQuote)
        .where(
            WorkshopQuote.tenant_id == tenant_id,
            WorkshopQuote.related_work_order_id == wo.id,
        )
        .order_by(WorkshopQuote.is_supplemental.asc(), WorkshopQuote.created_at.asc())
    )
    quotes = list(quote_rows.scalars().all())
    quote = quotes[0] if quotes else None

    client_id = (
        (reception.client_id if reception else None)
        or (quote.client_id if quote else None)
        or (vehicle.customer_client_id if vehicle else None)
    )
    client = None
    if client_id:
        client = await db.scalar(
            select(Client).where(Client.id == client_id, Client.tenant_id == tenant_id)
        )

    task_rows = await db.execute(
        select(WorkOrderTask)
        .where(WorkOrderTask.tenant_id == tenant_id, WorkOrderTask.work_order_id == wo.id)
        .order_by(WorkOrderTask.created_at)
    )
    tasks = list(task_rows.scalars().all())
    task_ids = [task.id for task in tasks]
    labor_logs: list[TaskLaborLog] = []
    if task_ids:
        labor_rows = await db.execute(
            select(TaskLaborLog)
            .where(TaskLaborLog.tenant_id == tenant_id, TaskLaborLog.work_order_task_id.in_(task_ids))
            .order_by(TaskLaborLog.completed_at)
        )
        labor_logs = list(labor_rows.scalars().all())

    user_ids = {task.assigned_to for task in tasks if task.assigned_to}
    user_ids.update(log.user_id for log in labor_logs)
    users: dict[UUID, str] = {}
    if user_ids:
        user_rows = await db.execute(
            select(User.id, User.full_name).where(User.tenant_id == tenant_id, User.id.in_(user_ids))
        )
        users = {row.id: row.full_name for row in user_rows}
    logs_by_task: dict[UUID, list[TaskLaborLog]] = defaultdict(list)
    for log in labor_logs:
        logs_by_task[log.work_order_task_id].append(log)

    part_rows = await db.execute(
        select(MaintenancePartUsed, SparePartInventory)
        .join(
            SparePartInventory,
            (SparePartInventory.id == MaintenancePartUsed.inventory_id)
            & (SparePartInventory.tenant_id == tenant_id),
        )
        .where(
            MaintenancePartUsed.tenant_id == tenant_id,
            MaintenancePartUsed.work_order_id == wo.id,
        )
        .order_by(MaintenancePartUsed.issued_at)
    )
    parts_grouped: dict[UUID, dict] = {}
    for usage, inventory in part_rows:
        item = parts_grouped.setdefault(
            inventory.id,
            {
                "inventory_id": inventory.id,
                "sku": inventory.sku,
                "name": inventory.name,
                "unit": inventory.unit,
                "issued_quantity": Decimal("0"),
                "returned_quantity": Decimal("0"),
                "net_cost": Decimal("0"),
            },
        )
        item["issued_quantity"] += usage.quantity
        item["returned_quantity"] += usage.returned_quantity or Decimal("0")
        item["net_cost"] += usage.net_total_cost if usage.net_total_cost is not None else (usage.total_cost or 0)

    checkout_rows = await db.execute(
        select(ToolCheckout, WorkshopTool)
        .join(
            WorkshopTool,
            (WorkshopTool.id == ToolCheckout.tool_id) & (WorkshopTool.tenant_id == tenant_id),
        )
        .where(
            ToolCheckout.tenant_id == tenant_id,
            ToolCheckout.work_order_id == wo.id,
            ToolCheckout.status == "checked_out",
        )
        .order_by(ToolCheckout.checked_out_at)
    )
    checked_out_tools = list(checkout_rows.all())

    billing = await db.scalar(
        select(BillingDocument)
        .join(BillingItem, BillingItem.billing_document_id == BillingDocument.id)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingItem.tenant_id == tenant_id,
            BillingItem.work_order_id == wo.id,
        )
        .order_by(BillingDocument.created_at.desc())
        .limit(1)
    )

    task_payload = []
    for task in tasks:
        task_payload.append(
            {
                "id": task.id,
                "description": task.description,
                "status": task.status,
                "assigned_to": task.assigned_to,
                "assigned_mechanic_name": users.get(task.assigned_to) if task.assigned_to else None,
                "estimated_minutes": task.estimated_minutes,
                "actual_minutes": task.actual_minutes,
                "labor_sessions": [
                    {
                        "id": log.id,
                        "user_id": log.user_id,
                        "mechanic_name": users.get(log.user_id, "Utilizador"),
                        "started_at": log.started_at,
                        "completed_at": log.completed_at,
                        "minutes_worked": log.minutes_worked,
                        "hourly_rate_applied": _money(log.hourly_rate_applied),
                        "total_labor_cost": _money(log.total_labor_cost),
                        "voided_at": log.voided_at,
                        "void_reason": log.void_reason,
                    }
                    for log in logs_by_task.get(task.id, [])
                ],
            }
        )

    parts_payload = []
    for item in parts_grouped.values():
        net_quantity = item["issued_quantity"] - item["returned_quantity"]
        parts_payload.append(
            {
                **item,
                "issued_quantity": float(item["issued_quantity"]),
                "returned_quantity": float(item["returned_quantity"]),
                "net_quantity": float(net_quantity),
                "net_cost": float(item["net_cost"]),
            }
        )

    return {
        "work_order": {
            "id": wo.id,
            "work_order_number": wo.work_order_number,
            "status": wo.status,
            "diagnosis": wo.diagnosis,
            "planned_work": wo.planned_work,
            "estimated_cost": _money(wo.estimated_cost) if wo.estimated_cost is not None else None,
            "actual_cost": _money(wo.actual_cost) if wo.actual_cost is not None else None,
            "origin_type": wo.origin_type,
            "billing_status": wo.billing_status,
            "billing_error": wo.billing_error,
            "document_id": billing.id if billing else wo.billing_document_id,
            "invoice_number": billing.invoice_number if billing else None,
            "invoice_status": billing.status if billing else None,
            "approved_at": wo.approved_at,
            "quality_checked_at": wo.quality_checked_at,
            "quality_notes": wo.quality_notes,
            "closed_at": wo.closed_at,
            "close_notes": wo.close_notes,
            "created_at": wo.created_at,
            "updated_at": wo.updated_at,
        },
        "vehicle": (
            {
                "id": vehicle.id,
                "plate": vehicle.plate,
                "brand": vehicle.brand,
                "model": vehicle.model,
                "current_km": vehicle.current_km,
                "odometer_at_reception": reception.odometer_at_reception if reception else None,
            }
            if vehicle
            else None
        ),
        "client": (
            {
                "id": client.id,
                "trading_name": client.trading_name,
                "legal_name": client.legal_name,
                "client_type": client.client_type,
                "nuit": client.nuit,
                "is_fleet_owned": False,
            }
            if client
            else {
                "id": None,
                "trading_name": "Frota propria",
                "legal_name": None,
                "client_type": "organization",
                "nuit": None,
                "is_fleet_owned": True,
            }
        ),
        "reception": (
            {
                "id": reception.id,
                "reception_number": reception.reception_number,
                "reported_issues": reception.reported_issues,
                "client_signature_file_id": reception.client_signature_file_id,
                "photos": [
                    {
                        "id": photo.id,
                        "file_id": photo.file_id,
                        "caption": photo.caption,
                        "taken_at": photo.taken_at,
                        "download_path": f"/api/v1/files/{photo.file_id}/download",
                    }
                    for photo in photos
                ],
            }
            if reception
            else None
        ),
        "quote": (
            {
                "id": quote.id,
                "quote_number": quote.quote_number,
                "status": quote.status,
                "approved_value": _money(quote.total_amount),
                "client_signature_file_id": quote.client_signature_file_id,
                "evidence_photo_file_id": quote.evidence_photo_file_id,
            }
            if quote
            else None
        ),
        "tasks": task_payload,
        "parts_issued": parts_payload,
        "unreturned_tools": [
            {
                "checkout_id": checkout.id,
                "tool_id": tool.id,
                "code": tool.code,
                "name": tool.name,
                "checked_out_at": checkout.checked_out_at,
            }
            for checkout, tool in checked_out_tools
        ],
        "blockers": {
            "incomplete_tasks": sum(task.status in {"pending", "in_progress"} for task in tasks),
            "unreturned_tools": len(checked_out_tools),
        },
    }
