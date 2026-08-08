from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.alerts.models import Alert
from app.modules.audit.models import AuditLog
from app.modules.checklists.models import Checklist
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.models import OperationalException
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Checklist {suffix}", slug=f"checklist-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"CHK-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Checklist {suffix}",
            phone=f"25885{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant, vehicle, driver


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def template_payload():
    return {
        "name": "Pre-partida pesado",
        "type": "pre_partida",
        "category": "pesado",
        "items": [
            {
                "id": "oil_level",
                "label": "Nivel de oleo",
                "type": "boolean",
                "is_blocking": True,
                "requires_photo": False,
            },
            {
                "id": "tires",
                "label": "Pneus",
                "type": "boolean",
                "is_blocking": False,
                "requires_photo": True,
            },
        ],
    }


@pytest.mark.asyncio
async def test_checklist_template_create_and_completion_rules() -> None:
    tenant, vehicle, driver = await seed_entities()

    async with await create_api_client() as client:
        template_response = await client.post(
            "/api/v1/checklist-templates",
            headers=auth_headers(tenant.id),
            json=template_payload(),
        )
        assert template_response.status_code == 200
        template = template_response.json()

        list_templates_response = await client.get(
            "/api/v1/checklist-templates",
            headers=auth_headers(tenant.id),
            params={"type": "pre_partida"},
        )
        assert list_templates_response.status_code == 200
        assert [item["id"] for item in list_templates_response.json()] == [template["id"]]

        checklist_response = await client.post(
            "/api/v1/checklists",
            headers=auth_headers(tenant.id),
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "template_id": template["id"],
                "type": "pre_partida",
                "responses": {
                    "oil_level": {"value": False},
                    "tires": {"value": True},
                },
                "location": {"lat": -25.96, "lng": 32.58},
                "gps_accuracy_m": 12,
                "gps_source": "browser",
            },
        )
        assert checklist_response.status_code == 200
        checklist = checklist_response.json()
        assert checklist["status"] == "in_progress"

        failed_response = await client.post(
            f"/api/v1/checklists/{checklist['id']}/complete",
            headers=auth_headers(tenant.id),
            json={},
        )
        assert failed_response.status_code == 200
        failed = failed_response.json()
        assert failed["status"] == "failed"
        reasons = {item["reason"] for item in failed["blocking_failures"]}
        assert reasons == {"blocking_item_failed", "required_photo_missing"}

        success_response = await client.post(
            "/api/v1/checklists",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "checklist:success:001"},
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "template_id": template["id"],
                "type": "pre_partida",
                "responses": {
                    "oil_level": {"value": True},
                    "tires": {"value": True, "photo_file_id": str(uuid4())},
                },
            },
        )
        assert success_response.status_code == 200
        success = success_response.json()
        success_replay = await client.post(
            "/api/v1/checklists",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "checklist:success:001"},
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "template_id": template["id"],
                "type": "pre_partida",
                "responses": {
                    "oil_level": {"value": True},
                    "tires": {
                        "value": True,
                        "photo_file_id": success["responses"]["tires"]["photo_file_id"],
                    },
                },
            },
        )
        assert success_replay.status_code == 200
        assert success_replay.json()["id"] == success["id"]

        completed_response = await client.post(
            f"/api/v1/checklists/{success['id']}/complete",
            headers=auth_headers(tenant.id),
            json={},
        )
        assert completed_response.status_code == 200
        completed = completed_response.json()
        assert completed["status"] == "completed"
        assert completed["blocking_failures"] == []

        list_checklists_response = await client.get(
            "/api/v1/checklists",
            headers=auth_headers(tenant.id),
            params={"status": "completed", "vehicle_id": str(vehicle.id)},
        )
        assert list_checklists_response.status_code == 200
        assert [item["id"] for item in list_checklists_response.json()] == [success["id"]]

    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(
            select(AuditLog.action).where(AuditLog.tenant_id == tenant.id)
        )
        audit_actions = set(audit_rows.scalars())
        assert {
            "checklist_template.created",
            "checklist.created",
            "checklist.completed",
            "operational_exception.created",
            "alert.created_from_exception",
        }.issubset(audit_actions)

        failed_exception = await db.scalar(
            select(OperationalException).where(
                OperationalException.tenant_id == tenant.id,
                OperationalException.entity_id == UUID(checklist["id"]),
                OperationalException.exception_type == "checklist_failed",
                OperationalException.status == "open",
            )
        )
        assert failed_exception is not None
        failed_context = failed_exception.context
        assert failed_context is not None
        assert failed_context["vehicle_id"] == str(vehicle.id)

    async with await create_api_client() as client:
        resolve_response = await client.post(
            f"/api/v1/checklists/{checklist['id']}/resolve-failure",
            headers=auth_headers(tenant.id),
            json={"resolution_notes": "Falha corrigida pela oficina antes da partida."},
        )
        assert resolve_response.status_code == 200
        assert resolve_response.json()["status"] == "resolved"

    async with AsyncSessionLocal() as db:
        resolved_exception = await db.scalar(
            select(OperationalException).where(
                OperationalException.tenant_id == tenant.id,
                OperationalException.entity_id == UUID(checklist["id"]),
                OperationalException.exception_type == "checklist_failed",
            )
        )
        assert resolved_exception is not None
        assert resolved_exception.status == "resolved"
        alert = await db.scalar(
            select(Alert).where(
                Alert.tenant_id == tenant.id,
                Alert.request_reference == f"exception:{resolved_exception.id}",
            )
        )
        assert alert is not None
        assert alert.status == "dismissed"


@pytest.mark.asyncio
async def test_sync_checklist_create_is_idempotent() -> None:
    tenant, vehicle, driver = await seed_entities()

    async with await create_api_client() as client:
        template_response = await client.post(
            "/api/v1/checklist-templates",
            headers=auth_headers(tenant.id),
            json=template_payload(),
        )
        assert template_response.status_code == 200
        template = template_response.json()

        operation = {
            "local_id": "checklist_local_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "checklist",
            "payload": {
                "vehicleId": str(vehicle.id),
                "driverId": str(driver.id),
                "templateId": template["id"],
                "type": "pre_partida",
                "responses": {
                    "oil_level": {"value": True},
                    "tires": {"value": True, "photo_file_id": str(uuid4())},
                },
            },
        }

        first_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant.id),
            json={"device_id": "driver-phone-checklist", "operations": [operation]},
        )
        assert first_response.status_code == 200
        first = first_response.json()["results"][0]
        assert first["status"] == "processed"

        replay_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant.id),
            json={"device_id": "driver-phone-checklist", "operations": [operation]},
        )
        assert replay_response.status_code == 200
        replay = replay_response.json()["results"][0]
        assert replay["server_id"] == first["server_id"]
        assert replay["message"] == "idempotent_replay"

    async with AsyncSessionLocal() as db:
        count = await db.scalar(
            select(func.count(Checklist.id)).where(
                Checklist.tenant_id == tenant.id,
                Checklist.vehicle_id == vehicle.id,
            )
        )
        assert count == 1
