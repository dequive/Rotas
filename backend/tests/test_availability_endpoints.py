"""Tests for GET /availability/drivers and GET /availability/vehicles endpoints.

Covers (plan 16-03):
  AV-01: /availability/drivers returns 200 with {total, items, limit, offset}
  AV-02: /availability/vehicles returns 200 with computed_status on each item
  AV-03: status filter ?status=available returns only available drivers
  AV-04: vehicle 'in_maintenance' has active_work_order_id populated
  AV-05: Redis cache populated on first request, served on second (mock redis)
  AV-06: Falls back to DB when redis is None (no cache)
  AV-07: Cross-tenant isolation — only current tenant's entities returned
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.database import AsyncSessionLocal, import_all_models
from app.main import app
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder

import_all_models()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def _create_tenant() -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        t = Tenant(name=f"Avail Test {suffix}", slug=f"avail-{suffix}")
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return t


async def _create_vehicle(tenant_id, *, status="active") -> Vehicle:
    async with AsyncSessionLocal() as db:
        v = Vehicle(
            tenant_id=tenant_id,
            plate=f"AV-{uuid4().hex[:6].upper()}",
            status=status,
        )
        db.add(v)
        await db.commit()
        await db.refresh(v)
        return v


async def _create_driver(tenant_id, *, status="active") -> Driver:
    async with AsyncSessionLocal() as db:
        d = Driver(
            tenant_id=tenant_id,
            full_name=f"Driver Avail {uuid4().hex[:6]}",
            status=status,
        )
        db.add(d)
        await db.commit()
        await db.refresh(d)
        return d


async def _create_work_order(tenant_id, vehicle_id, *, wo_status="in_progress") -> WorkOrder:
    async with AsyncSessionLocal() as db:
        wo = WorkOrder(
            tenant_id=tenant_id,
            vehicle_id=vehicle_id,
            work_order_number=f"WO-{uuid4().hex[:8].upper()}",
            planned_work="Test maintenance work",
            status=wo_status,
        )
        db.add(wo)
        await db.commit()
        await db.refresh(wo)
        return wo


async def _create_active_trip(tenant_id, vehicle_id, driver_id) -> Trip:
    async with AsyncSessionLocal() as db:
        from datetime import UTC, datetime

        t = Trip(
            tenant_id=tenant_id,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            origin="Maputo",
            destination="Beira",
            status="in_progress",
            actual_departure=datetime.now(UTC),
        )
        db.add(t)
        await db.commit()
        await db.refresh(t)
        return t


# ---------------------------------------------------------------------------
# AV-01: /availability/drivers returns 200 with correct shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_driver_availability_returns_correct_shape():
    tenant = await _create_tenant()
    await _create_driver(tenant.id)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/availability/drivers", headers=_auth(tenant.id))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert "total" in body
    assert "limit" in body
    assert "offset" in body
    assert isinstance(body["items"], list)
    assert body["total"] >= 1

    item = body["items"][0]
    assert "driver_id" in item
    assert "driver_name" in item
    assert "available" in item
    assert "availability_status" in item
    assert "hos_status" in item


# ---------------------------------------------------------------------------
# AV-02: /availability/vehicles returns 200 with computed_status on each item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_vehicle_availability_returns_computed_status():
    tenant = await _create_tenant()
    await _create_vehicle(tenant.id)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/availability/vehicles", headers=_auth(tenant.id))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert body["total"] >= 1

    item = body["items"][0]
    assert "vehicle_id" in item
    assert "plate_number" in item
    assert "computed_status" in item
    assert item["computed_status"] in ("available", "in_trip", "in_maintenance", "unavailable")


# ---------------------------------------------------------------------------
# AV-03: status filter ?status=available returns only available drivers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_driver_status_filter_available():
    tenant = await _create_tenant()
    # Create two drivers — one available, one in an active trip
    driver_free = await _create_driver(tenant.id)
    driver_busy = await _create_driver(tenant.id)
    vehicle = await _create_vehicle(tenant.id)
    # Put driver_busy on an active trip
    await _create_active_trip(tenant.id, vehicle.id, driver_busy.id)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/availability/drivers?status=available",
            headers=_auth(tenant.id),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {i["driver_id"] for i in body["items"]}
    assert str(driver_free.id) in ids, "Free driver should be in available results"
    assert str(driver_busy.id) not in ids, "Busy driver should NOT be in available results"


# ---------------------------------------------------------------------------
# AV-04: vehicle 'in_maintenance' has active_work_order_id populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vehicle_in_maintenance_has_work_order_id():
    tenant = await _create_tenant()
    vehicle = await _create_vehicle(tenant.id)
    wo = await _create_work_order(tenant.id, vehicle.id, wo_status="in_progress")

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/availability/vehicles?status=in_maintenance",
            headers=_auth(tenant.id),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1, "Expected at least one in_maintenance vehicle"

    matching = [i for i in body["items"] if i["vehicle_id"] == str(vehicle.id)]
    assert matching, f"Vehicle {vehicle.id} not found in in_maintenance results"
    item = matching[0]
    assert item["computed_status"] == "in_maintenance"
    assert item["active_work_order_id"] == str(wo.id), (
        f"Expected work_order_id={wo.id}, got {item.get('active_work_order_id')}"
    )


# ---------------------------------------------------------------------------
# AV-05: Redis cache populated on first request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_driver_availability_populates_redis_cache():
    tenant = await _create_tenant()
    await _create_driver(tenant.id)

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # cache miss
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.delete = AsyncMock(return_value=1)

    original_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/availability/drivers", headers=_auth(tenant.id))

        assert resp.status_code == 200, resp.text
        # Verify Redis SET was called (cache populated)
        assert mock_redis.set.called, "Expected redis.set() to be called to populate cache"
        call_args = mock_redis.set.call_args_list
        cache_key_calls = [c for c in call_args if str(tenant.id) in str(c)]
        assert cache_key_calls, f"Expected cache key with tenant_id, got: {call_args}"
    finally:
        app.state.redis = original_redis


# ---------------------------------------------------------------------------
# AV-06: Falls back to DB when redis is None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_driver_availability_works_without_redis():
    tenant = await _create_tenant()
    await _create_driver(tenant.id)

    original_redis = getattr(app.state, "redis", None)
    app.state.redis = None  # simulate no Redis

    try:
        import httpx

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.get("/api/v1/availability/drivers", headers=_auth(tenant.id))

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] >= 1
    finally:
        app.state.redis = original_redis


# ---------------------------------------------------------------------------
# AV-07: Cross-tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_driver_availability_cross_tenant_isolation():
    tenant_a = await _create_tenant()
    tenant_b = await _create_tenant()
    await _create_driver(tenant_a.id)
    driver_b = await _create_driver(tenant_b.id)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/availability/drivers", headers=_auth(tenant_a.id))

    assert resp.status_code == 200, resp.text
    ids = {i["driver_id"] for i in resp.json()["items"]}
    assert str(driver_b.id) not in ids, "Tenant B driver should NOT appear in tenant A results"


# ---------------------------------------------------------------------------
# AV-08: Pagination works after filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_driver_availability_pagination():
    tenant = await _create_tenant()
    # Create 3 drivers
    for _ in range(3):
        await _create_driver(tenant.id)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/availability/drivers?limit=2&offset=0",
            headers=_auth(tenant.id),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] == 2
    assert len(body["items"]) <= 2
    assert body["total"] >= 3  # total reflects full filtered set


# ---------------------------------------------------------------------------
# AV-09: Vehicle status filter works correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_vehicle_status_filter_available():
    tenant = await _create_tenant()
    vehicle_free = await _create_vehicle(tenant.id)
    vehicle_busy = await _create_vehicle(tenant.id)
    driver = await _create_driver(tenant.id)
    # Put vehicle_busy on an active trip
    await _create_active_trip(tenant.id, vehicle_busy.id, driver.id)

    import httpx

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/availability/vehicles?status=available",
            headers=_auth(tenant.id),
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    ids = {i["vehicle_id"] for i in body["items"]}
    assert str(vehicle_free.id) in ids, "Free vehicle should be in available results"
    assert str(vehicle_busy.id) not in ids, "Busy vehicle should NOT be in available results"
