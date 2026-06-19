from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import MaintenanceRequest, WorkOrder, WorkOrderTask

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def create_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Workshop {suffix}", slug=f"workshop-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"WRK-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Workshop {suffix}",
            phone=f"25886{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant.id, vehicle.id, driver.id


async def create_confirmed_order(client: httpx.AsyncClient, headers: dict[str, str]) -> dict:
    order = await client.post(
        "/api/v1/trip-orders",
        headers=headers,
        json={
            "origin": "Matola",
            "destination": "Chimoio",
            "cargo_type": "Carga geral",
            "requested_pickup_date": "2026-06-25",
        },
    )
    assert order.status_code == 200
    confirmed = await client.post(
        f"/api/v1/trip-orders/{order.json()['id']}/confirm",
        headers=headers,
        json={},
    )
    assert confirmed.status_code == 200
    return confirmed.json()


@pytest.mark.asyncio
async def test_active_work_order_blocks_assignment_until_closed() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            maintenance_request = await client.post(
                "/api/v1/workshop/maintenance-requests",
                headers={**headers, "Idempotency-Key": "maintenance-request:brakes:001"},
                json={
                    "vehicle_id": str(vehicle_id),
                    "request_type": "preventive",
                    "priority": "high",
                    "description": "Revisão de travões antes da próxima rota.",
                    "odometer_reading": 125000,
                },
            )
            assert maintenance_request.status_code == 200
            assert maintenance_request.json()["status"] == "open"
            maintenance_request_replay = await client.post(
                "/api/v1/workshop/maintenance-requests",
                headers={**headers, "Idempotency-Key": "maintenance-request:brakes:001"},
                json={
                    "vehicle_id": str(vehicle_id),
                    "request_type": "preventive",
                    "priority": "high",
                    "description": "Revisão de travões antes da próxima rota.",
                    "odometer_reading": 125000,
                },
            )
            assert maintenance_request_replay.status_code == 200
            assert maintenance_request_replay.json()["id"] == maintenance_request.json()["id"]

            work_order = await client.post(
                "/api/v1/workshop/work-orders",
                headers=headers,
                json={
                    "maintenance_request_id": maintenance_request.json()["id"],
                    "vehicle_id": str(vehicle_id),
                    "diagnosis": "Pastilhas dianteiras abaixo do limite.",
                    "planned_work": "Substituir pastilhas e testar travagem.",
                    "estimated_cost": 15000,
                },
            )
            assert work_order.status_code == 200
            assert work_order.json()["status"] == "draft"

            approved = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/approve",
                headers=headers,
                json={"notes": "Intervenção aprovada."},
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"

            task = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/tasks",
                headers=headers,
                json={"description": "Substituir pastilhas dianteiras."},
            )
            assert task.status_code == 200
            assert task.json()["status"] == "pending"

            started = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/start",
                headers=headers,
                json={"notes": "Viatura recebida na oficina."},
            )
            assert started.status_code == 200
            assert started.json()["status"] == "in_progress"

            premature_quality_check = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/quality-check",
                headers=headers,
                json={},
            )
            assert premature_quality_check.status_code == 409
            assert premature_quality_check.json()["error"]["code"] == "work_order_tasks_pending"

            completed_task = await client.post(
                (
                    f"/api/v1/workshop/work-orders/{work_order.json()['id']}"
                    f"/tasks/{task.json()['id']}/complete"
                ),
                headers=headers,
                json={"notes": "Pastilhas substituídas."},
            )
            assert completed_task.status_code == 200
            assert completed_task.json()["status"] == "completed"

            quality_check = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/quality-check",
                headers=headers,
                json={"notes": "Enviar para teste final."},
            )
            assert quality_check.status_code == 200
            assert quality_check.json()["status"] == "quality_check"

            order = await create_confirmed_order(client, headers)
            blocked_assignment = await client.post(
                f"/api/v1/trip-orders/{order['id']}/assign",
                headers=headers,
                json={"vehicle_id": str(vehicle_id), "driver_id": str(driver_id)},
            )
            assert blocked_assignment.status_code == 409
            assert blocked_assignment.json()["error"]["code"] == "vehicle_workshop_blocked"

            blocked_direct_trip = await client.post(
                "/api/v1/trips",
                headers=headers,
                json={
                    "vehicle_id": str(vehicle_id),
                    "driver_id": str(driver_id),
                    "origin": "Matola",
                    "destination": "Chimoio",
                },
            )
            assert blocked_direct_trip.status_code == 409
            assert blocked_direct_trip.json()["error"]["code"] == "vehicle_workshop_blocked"

            tower = await client.get("/api/v1/control-tower", headers=headers)
            assert tower.status_code == 200
            assert tower.json()["summary"]["work_orders_active"] == 1
            assert tower.json()["queues"]["active_work_orders"][0]["vehicle_plate"].startswith(
                "WRK-"
            )

            closed = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/close",
                headers=headers,
                json={"actual_cost": 14250, "notes": "Travões testados e viatura libertada."},
            )
            assert closed.status_code == 200
            assert closed.json()["status"] == "closed"

            assigned = await client.post(
                f"/api/v1/trip-orders/{order['id']}/assign",
                headers=headers,
                json={"vehicle_id": str(vehicle_id), "driver_id": str(driver_id)},
            )
            assert assigned.status_code == 200
            assert assigned.json()["trip"]["status"] == "planned"

        async with AsyncSessionLocal() as db:
            request_count = await db.scalar(
                select(func.count(MaintenanceRequest.id)).where(
                    MaintenanceRequest.tenant_id == tenant_id
                )
            )
            work_order_count = await db.scalar(
                select(func.count(WorkOrder.id)).where(WorkOrder.tenant_id == tenant_id)
            )
            task_count = await db.scalar(
                select(func.count(WorkOrderTask.id)).where(WorkOrderTask.tenant_id == tenant_id)
            )
            audit_actions = set(
                (
                    await db.execute(select(AuditLog.action).where(AuditLog.tenant_id == tenant_id))
                ).scalars()
            )
            assert request_count == 1
            assert work_order_count == 1
            assert task_count == 1
            assert {
                "maintenance_request.created",
                "work_order.created",
                "work_order.approved",
                "work_order.started",
                "work_order_task.created",
                "work_order_task.completed",
                "work_order.quality_check_requested",
                "work_order.closed",
            }.issubset(audit_actions)
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_spare_part_movements_are_idempotent_and_stock_led() -> None:
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            inventory = await client.post(
                "/api/v1/workshop/spare-parts",
                headers=headers,
                json={
                    "sku": f"PAD-{uuid4().hex[:8]}",
                    "name": "Pastilha de travão",
                    "minimum_quantity": 2,
                },
            )
            assert inventory.status_code == 200
            inventory_id = inventory.json()["id"]

            receipt_payload = {
                "inventory_id": inventory_id,
                "request_reference": f"REC-{uuid4().hex[:8]}",
                "quantity": 10,
                "unit_cost": 500,
                "occurred_at": "2026-06-26T08:00:00+00:00",
            }
            receipt = await client.post(
                "/api/v1/workshop/spare-parts/receipts",
                headers=headers,
                json=receipt_payload,
            )
            assert receipt.status_code == 200
            assert float(receipt.json()["balance_after_quantity"]) == 10

            receipt_replay = await client.post(
                "/api/v1/workshop/spare-parts/receipts",
                headers=headers,
                json=receipt_payload,
            )
            assert receipt_replay.status_code == 200
            assert receipt_replay.json()["id"] == receipt.json()["id"]

            receipt_conflict = await client.post(
                "/api/v1/workshop/spare-parts/receipts",
                headers=headers,
                json={**receipt_payload, "quantity": 11},
            )
            assert receipt_conflict.status_code == 409
            assert receipt_conflict.json()["error"]["code"] == "spare_part_request_reference_reused"

            request = await client.post(
                "/api/v1/workshop/maintenance-requests",
                headers=headers,
                json={
                    "vehicle_id": str(vehicle_id),
                    "description": "Substituir pastilhas.",
                },
            )
            work_order = await client.post(
                "/api/v1/workshop/work-orders",
                headers=headers,
                json={
                    "maintenance_request_id": request.json()["id"],
                    "vehicle_id": str(vehicle_id),
                    "planned_work": "Substituir pastilhas dianteiras.",
                },
            )
            approved = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/approve",
                headers=headers,
                json={},
            )
            assert approved.status_code == 200
            started = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/start",
                headers=headers,
                json={},
            )
            assert started.status_code == 200

            issue_payload = {
                "inventory_id": inventory_id,
                "request_reference": f"ISS-{uuid4().hex[:8]}",
                "quantity": 8,
                "occurred_at": "2026-06-26T09:00:00+00:00",
            }
            issue = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/parts",
                headers=headers,
                json=issue_payload,
            )
            assert issue.status_code == 200
            assert float(issue.json()["total_cost"]) == 4000

            issue_replay = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/parts",
                headers=headers,
                json=issue_payload,
            )
            assert issue_replay.status_code == 200
            assert issue_replay.json()["id"] == issue.json()["id"]

            insufficient = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/parts",
                headers=headers,
                json={
                    "inventory_id": inventory_id,
                    "request_reference": f"ISS-{uuid4().hex[:8]}",
                    "quantity": 3,
                    "occurred_at": "2026-06-26T10:00:00+00:00",
                },
            )
            assert insufficient.status_code == 409
            assert insufficient.json()["error"]["code"] == "insufficient_spare_part_stock"

            movements = await client.get(
                "/api/v1/workshop/spare-part-movements",
                headers=headers,
                params={"inventory_id": inventory_id},
            )
            assert movements.status_code == 200
            assert len(movements.json()) == 2
            assert float(movements.json()[0]["balance_after_quantity"]) == 2

            tower = await client.get("/api/v1/control-tower", headers=headers)
            assert tower.status_code == 200
            assert tower.json()["summary"]["spare_parts_low_stock"] == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_tool_checkout_return_and_critical_calibration_controls() -> None:
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            request = await client.post(
                "/api/v1/workshop/maintenance-requests",
                headers=headers,
                json={"vehicle_id": str(vehicle_id), "description": "Verificar sistema eléctrico."},
            )
            work_order = await client.post(
                "/api/v1/workshop/work-orders",
                headers=headers,
                json={
                    "maintenance_request_id": request.json()["id"],
                    "vehicle_id": str(vehicle_id),
                    "planned_work": "Diagnosticar alternador.",
                },
            )
            await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/approve",
                headers=headers,
                json={},
            )
            await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/start",
                headers=headers,
                json={},
            )

            expired_tool = await client.post(
                "/api/v1/workshop/tools",
                headers=headers,
                json={
                    "code": f"MTR-{uuid4().hex[:8]}",
                    "name": "Multímetro crítico",
                    "is_critical": True,
                    "calibration_due_at": "2026-05-01T00:00:00+00:00",
                },
            )
            expired_checkout = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/tool-checkouts",
                headers=headers,
                json={
                    "tool_id": expired_tool.json()["id"],
                    "checkout_reference": f"CHK-{uuid4().hex[:8]}",
                    "checked_out_at": "2026-06-02T08:00:00+00:00",
                },
            )
            assert expired_checkout.status_code == 409
            assert expired_checkout.json()["error"]["code"] == "workshop_tool_calibration_expired"

            tool = await client.post(
                "/api/v1/workshop/tools",
                headers=headers,
                json={"code": f"KEY-{uuid4().hex[:8]}", "name": "Chave dinamométrica"},
            )
            checkout_payload = {
                "tool_id": tool.json()["id"],
                "checkout_reference": f"CHK-{uuid4().hex[:8]}",
                "checked_out_at": "2026-06-02T08:00:00+00:00",
                "due_at": "2026-01-01T09:00:00+00:00",
            }
            checkout = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/tool-checkouts",
                headers=headers,
                json=checkout_payload,
            )
            assert checkout.status_code == 200
            assert checkout.json()["status"] == "checked_out"

            checkout_replay = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/tool-checkouts",
                headers=headers,
                json=checkout_payload,
            )
            assert checkout_replay.status_code == 200
            assert checkout_replay.json()["id"] == checkout.json()["id"]

            second_checkout = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/tool-checkouts",
                headers=headers,
                json={
                    **checkout_payload,
                    "checkout_reference": f"CHK-{uuid4().hex[:8]}",
                },
            )
            assert second_checkout.status_code == 409
            assert second_checkout.json()["error"]["code"] == "workshop_tool_unavailable"

            tower = await client.get("/api/v1/control-tower", headers=headers)
            assert tower.status_code == 200
            assert tower.json()["summary"]["tool_checkouts_overdue"] == 1

            blocked_quality_check = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/quality-check",
                headers=headers,
                json={},
            )
            assert blocked_quality_check.status_code == 409
            assert blocked_quality_check.json()["error"]["code"] == "work_order_tools_checked_out"

            return_payload = {
                "return_reference": f"RET-{uuid4().hex[:8]}",
                "returned_at": "2026-06-02T10:00:00+00:00",
                "return_condition": "damaged",
            }
            returned = await client.post(
                f"/api/v1/workshop/tool-checkouts/{checkout.json()['id']}/return",
                headers=headers,
                json=return_payload,
            )
            assert returned.status_code == 200
            assert returned.json()["return_condition"] == "damaged"

            returned_replay = await client.post(
                f"/api/v1/workshop/tool-checkouts/{checkout.json()['id']}/return",
                headers=headers,
                json=return_payload,
            )
            assert returned_replay.status_code == 200
            assert returned_replay.json()["id"] == returned.json()["id"]

            damaged_checkout = await client.post(
                f"/api/v1/workshop/work-orders/{work_order.json()['id']}/tool-checkouts",
                headers=headers,
                json={
                    **checkout_payload,
                    "checkout_reference": f"CHK-{uuid4().hex[:8]}",
                },
            )
            assert damaged_checkout.status_code == 409
            assert damaged_checkout.json()["error"]["code"] == "workshop_tool_unavailable"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_preventive_maintenance_evaluation_is_idempotent() -> None:
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        reference = f"PLAN-{uuid4().hex[:8]}"
        payload = {
            "vehicle_id": str(vehicle_id),
            "request_reference": reference,
            "name": "Revisão periódica de segurança",
            "interval_km": 10000,
            "next_due_km": 0,
        }
        async with await create_api_client() as client:
            plan = await client.post(
                "/api/v1/workshop/maintenance-plans",
                headers=headers,
                json=payload,
            )
            assert plan.status_code == 200

            replay = await client.post(
                "/api/v1/workshop/maintenance-plans",
                headers=headers,
                json=payload,
            )
            assert replay.status_code == 200
            assert replay.json()["id"] == plan.json()["id"]

            first_evaluation = await client.post(
                "/api/v1/workshop/maintenance-schedule/evaluate",
                headers=headers,
            )
            assert first_evaluation.status_code == 200
            assert first_evaluation.json()["created"] == 1
            assert len(first_evaluation.json()["overdue"]) == 1

            replay_evaluation = await client.post(
                "/api/v1/workshop/maintenance-schedule/evaluate",
                headers=headers,
            )
            assert replay_evaluation.status_code == 200
            assert replay_evaluation.json()["created"] == 0
            assert len(replay_evaluation.json()["overdue"]) == 1

            tower = await client.get("/api/v1/control-tower", headers=headers)
            assert tower.status_code == 200
            assert tower.json()["summary"]["maintenance_overdue"] == 1

            exceptions = await client.get(
                "/api/v1/operational-exceptions",
                headers=headers,
                params={"exception_type": "maintenance_overdue"},
            )
            assert exceptions.status_code == 200
            assert len(exceptions.json()) == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
