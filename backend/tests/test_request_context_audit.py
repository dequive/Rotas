from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.tenants.models import Tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_tenant() -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Request Context {suffix}", slug=f"request-context-{suffix}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


def auth_headers(tenant_id: UUID, request_id: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }
    if request_id:
        headers["X-Request-Id"] = request_id
    return headers


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_request_id_is_returned_and_persisted_in_audit_log() -> None:
    tenant = await create_tenant()
    request_id = "fleet-import-2026-06-03-001"

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/vehicles",
            headers=auth_headers(tenant.id, request_id),
            json={"plate": f"RID-{uuid4().hex[:6]}", "category": "pesado"},
        )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == request_id
    vehicle_id = UUID(response.json()["id"])

    async with AsyncSessionLocal() as db:
        audit_log = await db.scalar(
            select(AuditLog).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_type == "vehicle",
                AuditLog.entity_id == vehicle_id,
                AuditLog.action == "vehicle.created",
            )
        )
        assert audit_log is not None
        assert audit_log.correlation_id == request_id


@pytest.mark.asyncio
async def test_error_response_generates_request_id_when_header_is_absent() -> None:
    tenant = await create_tenant()

    async with await create_api_client() as client:
        response = await client.get(
            f"/api/v1/vehicles/{uuid4()}",
            headers=auth_headers(tenant.id),
        )

    assert response.status_code == 404
    response_request_id = response.headers["x-request-id"]
    assert response_request_id
    assert response.json()["error"]["request_id"] == response_request_id
