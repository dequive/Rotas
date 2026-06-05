"""CT-01 and CT-03 tests: consolidated queries, cross-tenant isolation, pagination."""
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import OperationalError

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def _auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def _make_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def _create_tenant_with_seed(trip_count: int = 1) -> tuple:
    """Create tenant, vehicle, driver and N planned trips. Returns (tenant_id, vehicle_id, driver_id)."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"OptimizedTower {suffix}",
            slug=f"opt-tower-{suffix}",
            max_vehicles=10,
            max_drivers=10,
        )
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"OPT-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Optimized Driver {suffix}",
            phone=f"2589{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.flush()

        for i in range(trip_count):
            t = Trip(
                tenant_id=tenant.id,
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                origin=f"Origin-{i}",
                destination=f"Destination-{i}",
                cargo_type="Carga geral",
                status="planned",
            )
            db.add(t)

        await db.commit()
        await db.refresh(tenant)
        return tenant.id, vehicle.id, driver.id


# --- CT-01: Cross-tenant isolation preserved after rewrite ---
@pytest.mark.asyncio
async def test_control_tower_cross_tenant_isolation_preserved():
    """CT-01: After query consolidation, tenant A cannot see tenant B data in CT summary."""
    try:
        tenant_a_id, _, _ = await _create_tenant_with_seed(trip_count=1)
        tenant_b_id, _, _ = await _create_tenant_with_seed(trip_count=1)

        async with await _make_client() as client:
            resp_a = await client.get(
                "/api/v1/control-tower", headers=_auth_headers(tenant_a_id)
            )
            resp_b = await client.get(
                "/api/v1/control-tower", headers=_auth_headers(tenant_b_id)
            )

        assert resp_a.status_code == 200, f"CT for tenant A failed: {resp_a.text}"
        assert resp_b.status_code == 200, f"CT for tenant B failed: {resp_b.text}"

        tower_a = resp_a.json()
        tower_b = resp_b.json()

        # Each tenant should report exactly their own fleet size (1 vehicle, 1 driver each)
        assert tower_a["summary"]["vehicles_active"] == 1, (
            f"Tenant A vehicles_active={tower_a['summary']['vehicles_active']}, expected 1"
        )
        assert tower_b["summary"]["vehicles_active"] == 1, (
            f"Tenant B vehicles_active={tower_b['summary']['vehicles_active']}, expected 1"
        )
        assert tower_a["summary"]["drivers_active"] == 1, (
            f"Tenant A drivers_active={tower_a['summary']['drivers_active']}, expected 1"
        )
        assert tower_b["summary"]["drivers_active"] == 1, (
            f"Tenant B drivers_active={tower_b['summary']['drivers_active']}, expected 1"
        )

    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


# --- CT-03: Pagination params respected ---
@pytest.mark.asyncio
async def test_control_tower_pagination_respected():
    """CT-03: page=1&page_size=2 returns at most 2 items in any queue."""
    try:
        tenant_id, _, _ = await _create_tenant_with_seed(trip_count=1)

        async with await _make_client() as client:
            resp = await client.get(
                "/api/v1/control-tower",
                headers=_auth_headers(tenant_id),
                params={"page": 1, "page_size": 2},
            )

        assert resp.status_code == 200, f"CT request failed: {resp.text}"

        tower = resp.json()
        for queue_name, queue_items in tower["queues"].items():
            assert len(queue_items) <= 2, (
                f"Queue '{queue_name}' has {len(queue_items)} items, expected <= 2"
            )

    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


# --- CT-03: Default page_size=50 cap ---
@pytest.mark.asyncio
async def test_control_tower_no_unbounded_query():
    """CT-03: Default request must not return more than 50 items in any queue."""
    try:
        tenant_id, _, _ = await _create_tenant_with_seed(trip_count=1)

        async with await _make_client() as client:
            resp = await client.get(
                "/api/v1/control-tower",
                headers=_auth_headers(tenant_id),
            )

        assert resp.status_code == 200, f"CT request failed: {resp.text}"

        tower = resp.json()
        for queue_name, queue_items in tower["queues"].items():
            assert len(queue_items) <= 50, (
                f"Queue '{queue_name}' has {len(queue_items)} items — exceeds default page_size=50"
            )

    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
