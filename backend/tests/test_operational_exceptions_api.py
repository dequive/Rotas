from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.operational_exceptions.service import ensure_exception
from app.modules.tenants.models import Tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def create_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_operational_exception_lifecycle_is_auditable_and_idempotent() -> None:
    try:
        suffix = uuid4().hex[:8]
        entity_id = uuid4()
        async with AsyncSessionLocal() as db:
            tenant = Tenant(name=f"Tenant Exception {suffix}", slug=f"exception-{suffix}")
            db.add(tenant)
            await db.flush()
            first = await ensure_exception(
                db,
                tenant.id,
                entity_type="fuel_tank",
                entity_id=entity_id,
                exception_type="fuel_low_stock",
                severity="high",
                title="Stock baixo",
                message="Tanque abaixo do mínimo.",
                source_type="fuel_movement",
            )
            replay = await ensure_exception(
                db,
                tenant.id,
                entity_type="fuel_tank",
                entity_id=entity_id,
                exception_type="fuel_low_stock",
                severity="high",
                title="Stock baixo",
                message="Tanque abaixo do mínimo.",
                source_type="fuel_movement",
            )
            assert replay.id == first.id
            await db.commit()
            tenant_id = tenant.id
            exception_id = first.id

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            listed = await client.get("/api/v1/operational-exceptions", headers=headers)
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [str(exception_id)]
            alerts = await client.get("/api/v1/alerts", headers=headers)
            assert alerts.status_code == 200
            assert len(alerts.json()) == 1
            assert alerts.json()[0]["request_reference"] == f"exception:{exception_id}"
            assert alerts.json()[0]["status"] == "pending"

            acknowledged = await client.post(
                f"/api/v1/operational-exceptions/{exception_id}/acknowledge",
                headers=headers,
            )
            assert acknowledged.status_code == 200
            assert acknowledged.json()["status"] == "acknowledged"

            resolved = await client.post(
                f"/api/v1/operational-exceptions/{exception_id}/resolve",
                headers=headers,
                json={"resolution_notes": "Compra urgente recebida e validada."},
            )
            assert resolved.status_code == 200
            assert resolved.json()["status"] == "resolved"
            assert resolved.json()["resolution_notes"] == "Compra urgente recebida e validada."
            dismissed_alerts = await client.get(
                "/api/v1/alerts",
                headers=headers,
                params={"status": "dismissed"},
            )
            assert dismissed_alerts.status_code == 200
            assert [item["request_reference"] for item in dismissed_alerts.json()] == [
                f"exception:{exception_id}"
            ]
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
