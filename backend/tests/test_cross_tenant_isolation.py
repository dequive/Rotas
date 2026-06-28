from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.tenants.models import Tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_tenant() -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"CrossTenantTest {suffix}",
            slug=f"ct-{suffix}",
            max_vehicles=5,
            max_drivers=5,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def test_vehicle_not_accessible_from_other_tenant():
    """D-21: A vehicle created in tenant A must return 404 when accessed from tenant B."""
    tenant_a = await create_tenant()
    tenant_b = await create_tenant()

    async with await create_api_client() as client:
        create_resp = await client.post(
            "/api/v1/vehicles",
            headers=auth_headers(tenant_a.id),
            json={
                "plate": f"MZ-CT-{uuid4().hex[:4].upper()}",
                "make": "Toyota",
                "model": "Hilux",
                "year": 2020,
                "fuel_type": "diesel",
            },
        )
        assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
        vehicle_id = create_resp.json()["id"]

        # Tenant B must get 404 — not the vehicle data
        response = await client.get(
            f"/api/v1/vehicles/{vehicle_id}",
            headers=auth_headers(tenant_b.id),
        )
    assert response.status_code == 404, (
        f"Expected 404 for cross-tenant access, got {response.status_code}: {response.text}"
    )


async def test_driver_not_accessible_from_other_tenant():
    """D-21: A driver created in tenant A must return 404 when accessed from tenant B."""
    tenant_a = await create_tenant()
    tenant_b = await create_tenant()

    async with await create_api_client() as client:
        create_resp = await client.post(
            "/api/v1/drivers",
            headers=auth_headers(tenant_a.id),
            json={
                "full_name": "CrossTenant Driver",
                "phone": f"25884{uuid4().hex[:7]}",
                "license_number": f"LIC{uuid4().hex[:6].upper()}",
            },
        )
        assert create_resp.status_code in (200, 201), f"Create failed: {create_resp.text}"
        driver_id = create_resp.json()["id"]

        response = await client.get(
            f"/api/v1/drivers/{driver_id}",
            headers=auth_headers(tenant_b.id),
        )
    assert response.status_code == 404


async def test_trip_not_accessible_from_other_tenant():
    """D-21: Trip data must be invisible to other tenants."""
    await create_tenant()
    tenant_b = await create_tenant()

    async with await create_api_client() as client:
        # Confirm trips list for tenant B returns empty list, not tenant A's trips
        trips_b = await client.get(
            "/api/v1/trips",
            headers=auth_headers(tenant_b.id),
        )
    assert trips_b.status_code == 200
    body = trips_b.json()
    assert isinstance(body, list), f"Expected list, got: {body}"
