# ruff: noqa: E402
import os
import uuid
from uuid import uuid4

import httpx
import pytest
from sqlalchemy.exc import OperationalError

os.environ.setdefault("DEV_TEST_TOKEN", "test-token")

from app.database import AsyncSessionLocal, engine, import_all_models  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.drivers.models import Driver  # noqa: E402
from app.modules.tenants.models import Tenant  # noqa: E402
from app.modules.vehicles.models import Vehicle  # noqa: E402
from app.modules.workshop.models import MaintenanceRequest  # noqa: E402

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
        tenant = Tenant(name=f"Tenant History {suffix}", slug=f"history-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"HIS-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver History {suffix}",
            phone=f"25890{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant.id, vehicle.id, driver.id


async def seed_maintenance_request(tenant_id: uuid.UUID, vehicle_id: uuid.UUID) -> str:
    """Insert a MaintenanceRequest directly in DB and return its ID."""
    async with AsyncSessionLocal() as db:
        mr = MaintenanceRequest(
            tenant_id=tenant_id,
            vehicle_id=vehicle_id,
            request_type="corrective",
            priority="normal",
            description="Test maintenance for history",
            status="open",
        )
        db.add(mr)
        await db.commit()
        await db.refresh(mr)
        return str(mr.id)


async def seed_work_order_with_task(
    client: httpx.AsyncClient, headers: dict, vehicle_id
) -> tuple[str, str]:
    """Create maintenance request + work order + one task. Returns (wo_id, task_id)."""
    mr = await client.post(
        "/api/v1/workshop/maintenance-requests",
        headers=headers,
        json={
            "vehicle_id": str(vehicle_id),
            "request_type": "corrective",
            "priority": "normal",
            "description": "Test maintenance for vehicle history",
        },
    )
    assert mr.status_code == 200, f"MR creation failed: {mr.text}"
    mr_id = mr.json()["id"]

    wo = await client.post(
        "/api/v1/workshop/work-orders",
        headers=headers,
        json={
            "maintenance_request_id": mr_id,
            "vehicle_id": str(vehicle_id),
            "planned_work": "Test work for vehicle history",
        },
    )
    assert wo.status_code == 200, f"WO creation failed: {wo.text}"
    wo_id = wo.json()["id"]

    task = await client.post(
        f"/api/v1/workshop/work-orders/{wo_id}/tasks",
        headers=headers,
        json={
            "description": "Test task",
        },
    )
    assert task.status_code == 200, f"Task creation failed: {task.text}"

    return wo_id, task.json()["id"]


@pytest.mark.asyncio
async def test_vehicle_history_empty() -> None:
    """GET /api/v1/vehicles/{vehicle_id}/history with types param returns 200, events=[]."""
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)

        async with await create_api_client() as client:
            resp = await client.get(
                f"/api/v1/vehicles/{vehicle_id}/history?types=maintenance_request",
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "events" in data
            assert isinstance(data["events"], list)
            # No maintenance requests seeded, so events should be empty
            assert len(data["events"]) == 0
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_work_order_in_vehicle_history() -> None:
    """Create WO for vehicle -> GET history with types=work_order -> event_type=work_order present."""
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)

        async with await create_api_client() as client:
            wo_id, _ = await seed_work_order_with_task(client, headers, vehicle_id)

            hist_resp = await client.get(
                f"/api/v1/vehicles/{vehicle_id}/history?types=work_order",
                headers=headers,
            )
            assert hist_resp.status_code == 200, hist_resp.text
            data = hist_resp.json()
            assert "events" in data
            assert any(e["event_type"] == "work_order" for e in data["events"]), (
                f"Expected work_order event, got: {[e['event_type'] for e in data['events']]}"
            )
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_vehicle_history_pagination() -> None:
    """Create 55 maintenance requests -> first page next_cursor not null;
    second page has remainder.
    """
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)

        # Seed 55 maintenance requests directly in DB
        async with AsyncSessionLocal() as db:
            for i in range(55):
                mr = MaintenanceRequest(
                    tenant_id=tenant_id,
                    vehicle_id=vehicle_id,
                    request_type="corrective",
                    priority="normal",
                    description=f"History event {i}",
                    status="open",
                )
                db.add(mr)
            await db.commit()

        async with await create_api_client() as client:
            # Fetch first page of 50 (uses cursor pagination via types param)
            r1 = await client.get(
                f"/api/v1/vehicles/{vehicle_id}/history?types=maintenance_request&limit=50",
                headers=headers,
            )
            assert r1.status_code == 200, r1.text
            d1 = r1.json()
            assert len(d1["events"]) == 50
            assert d1["next_cursor"] is not None, "Expected next_cursor for 55 events with limit=50"

            # Fetch second page using the cursor
            r2 = await client.get(
                f"/api/v1/vehicles/{vehicle_id}/history?types=maintenance_request&limit=50&cursor={d1['next_cursor']}",
                headers=headers,
            )
            assert r2.status_code == 200, r2.text
            d2 = r2.json()
            assert len(d2["events"]) == 5, (
                f"Expected 5 events on second page, got {len(d2['events'])}"
            )

            # Ensure no overlap between pages
            ids_1 = {e["reference_id"] for e in d1["events"]}
            ids_2 = {e["reference_id"] for e in d2["events"]}
            assert ids_1.isdisjoint(ids_2), "Cursor pagination returned duplicate events"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_vehicle_history_type_filter() -> None:
    """With types=work_order filter, only work_order events are returned."""
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)

        # Seed a maintenance request (should be excluded by type filter)
        await seed_maintenance_request(tenant_id, vehicle_id)

        async with await create_api_client() as client:
            # Create a work order too
            wo_id, _ = await seed_work_order_with_task(client, headers, vehicle_id)

            resp = await client.get(
                f"/api/v1/vehicles/{vehicle_id}/history?types=work_order",
                headers=headers,
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            for event in data["events"]:
                assert event["event_type"] == "work_order", (
                    f"Got unexpected event_type '{event['event_type']}'"
                    " when filtering by work_order"
                )
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_vehicle_history_cross_tenant() -> None:
    """Vehicle from tenant A returns empty events (or 404) when accessed as tenant B."""
    try:
        tenant_a_id, vehicle_a_id, _ = await seed_entities()
        tenant_b_id, _, _ = await seed_entities()
        headers_b = auth_headers(tenant_b_id)

        # Seed some data on vehicle A
        await seed_maintenance_request(tenant_a_id, vehicle_a_id)

        async with await create_api_client() as client:
            resp = await client.get(
                f"/api/v1/vehicles/{vehicle_a_id}/history?types=maintenance_request",
                headers=headers_b,
            )
            # get_vehicle_history filters by tenant_id so returns empty events (not 404)
            # The legacy endpoint calls _require_vehicle which would 404
            if resp.status_code == 200:
                data = resp.json()
                assert len(data["events"]) == 0, (
                    f"Tenant B should see 0 events for tenant A's vehicle,"
                    f" got {len(data['events'])}"
                )
            else:
                assert resp.status_code == 404
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")
