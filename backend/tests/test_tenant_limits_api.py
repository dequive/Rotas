"""Tests for INFRA-03: GET /api/v1/tenants/me/limits endpoint and plan_limit_reached guards."""
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def _create_tenant(
    max_vehicles: int | None = 5,
    max_drivers: int | None = 5,
    max_users: int | None = 3,
) -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Limits Test Tenant {suffix}",
            slug=f"limits-{suffix}",
            max_vehicles=max_vehicles,
            max_drivers=max_drivers,
            max_users=max_users,
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


def _auth(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_get_limits_returns_correct_counts() -> None:
    """GET /api/v1/tenants/me/limits returns vehicles/drivers/users with used/max/pct."""
    tenant = await _create_tenant(max_vehicles=10, max_drivers=8, max_users=5)

    # Seed 2 active vehicles directly in DB
    async with AsyncSessionLocal() as db:
        for i in range(2):
            db.add(Vehicle(
                tenant_id=tenant.id,
                plate=f"LIM-{uuid4().hex[:6].upper()}",
                status="active",
            ))
        await db.commit()

    async with await _client() as client:
        resp = await client.get("/api/v1/tenants/me/limits", headers=_auth(tenant.id))

    assert resp.status_code == 200
    body = resp.json()
    assert "vehicles" in body
    assert "drivers" in body
    assert "users" in body
    assert "upgrade_url" in body

    v = body["vehicles"]
    assert v["used"] == 2
    assert v["max"] == 10
    assert v["pct"] == 20.0

    d = body["drivers"]
    assert d["used"] == 0
    assert d["max"] == 8
    assert d["pct"] == 0.0

    u = body["users"]
    assert u["max"] == 5
    assert isinstance(u["pct"], float)


@pytest.mark.asyncio
async def test_get_limits_null_max_for_unlimited_tenant() -> None:
    """When Tenant.max_vehicles is None, vehicle max is null and pct is null in response."""
    # The Tenant model has int default=5, so we need to set None after creation
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        tenant = Tenant(
            name=f"Unlimited Tenant {suffix}",
            slug=f"unlimited-{suffix}",
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        # Force max_vehicles to NULL at DB level to test the unlimited path
        await db.execute(
            text("UPDATE tenants SET max_vehicles = NULL WHERE id = :tid"),
            {"tid": str(tenant.id)},
        )
        await db.commit()
        await db.refresh(tenant)
        tenant_id = tenant.id

    async with await _client() as client:
        resp = await client.get("/api/v1/tenants/me/limits", headers=_auth(tenant_id))

    assert resp.status_code == 200
    body = resp.json()
    assert body["vehicles"]["max"] is None
    assert body["vehicles"]["pct"] is None


@pytest.mark.asyncio
async def test_redis_cache_hit_skips_db_count() -> None:
    """Second call to /tenants/me/limits within 30s reads from Redis, not DB."""
    tenant = await _create_tenant(max_vehicles=5, max_drivers=5, max_users=3)

    # Mock redis to return cached values on second call
    mock_redis = AsyncMock()
    # First call: cache miss (hget returns None)
    # Second call: cache hit (hget returns cached value)
    hget_results = [None, b"0"]  # first None (miss), then cached value

    async def mock_hget(key, field):
        return hget_results.pop(0) if hget_results else b"0"

    mock_redis.hget = mock_hget
    mock_redis.hset = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock(return_value=1)

    app.state.redis = mock_redis

    try:
        async with await _client() as client:
            resp1 = await client.get("/api/v1/tenants/me/limits", headers=_auth(tenant.id))
            assert resp1.status_code == 200

            resp2 = await client.get("/api/v1/tenants/me/limits", headers=_auth(tenant.id))
            assert resp2.status_code == 200
            # Second response should also succeed (served from mock redis)
            assert resp2.json()["vehicles"]["used"] == 0
    finally:
        app.state.redis = None


@pytest.mark.asyncio
async def test_limits_requires_auth() -> None:
    """GET /api/v1/tenants/me/limits returns 401 without auth token."""
    async with await _client() as client:
        resp = await client.get("/api/v1/tenants/me/limits")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_vehicle_limit_guard_returns_plan_limit_reached() -> None:
    """Creating a vehicle past max_vehicles returns 403 with slug plan_limit_reached."""
    tenant = await _create_tenant(max_vehicles=1, max_drivers=5, max_users=3)

    async with await _client() as client:
        # Create first vehicle — should succeed
        r1 = await client.post(
            "/api/v1/vehicles",
            headers={**_auth(tenant.id), "Idempotency-Key": f"lim-v1-{tenant.id}"},
            json={
                "plate": f"LIM-{uuid4().hex[:6].upper()}",
                "brand": "Toyota",
                "model": "Dyna",
                "year": 2020,
                "category": "pesado",
                "fuel_type": "gasoleo",
                "current_km": 0,
            },
        )
        assert r1.status_code == 200

        # Create second vehicle — should hit limit
        r2 = await client.post(
            "/api/v1/vehicles",
            headers=_auth(tenant.id),
            json={
                "plate": f"LIM-{uuid4().hex[:6].upper()}",
                "brand": "Toyota",
                "model": "Dyna",
                "year": 2020,
                "category": "pesado",
                "fuel_type": "gasoleo",
                "current_km": 0,
            },
        )
        assert r2.status_code == 403
        err = r2.json()["error"]
        assert err["code"] == "plan_limit_reached"
        assert "upgrade_url" in err["details"]
        assert err["details"]["dimension"] == "vehicles"


@pytest.mark.asyncio
async def test_null_max_vehicles_allows_unlimited_creation() -> None:
    """When max_vehicles is None (unlimited), vehicles can always be created."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        from sqlalchemy import text
        tenant = Tenant(name=f"Unlimited {suffix}", slug=f"unlim-{suffix}", max_vehicles=999)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        await db.execute(
            text("UPDATE tenants SET max_vehicles = NULL WHERE id = :tid"),
            {"tid": str(tenant.id)},
        )
        await db.commit()
        tenant_id = tenant.id

    async with await _client() as client:
        for i in range(3):
            r = await client.post(
                "/api/v1/vehicles",
                headers=_auth(tenant_id),
                json={
                    "plate": f"UNL-{uuid4().hex[:6].upper()}",
                    "category": "pesado",
                    "fuel_type": "gasoleo",
                    "current_km": 0,
                },
            )
            assert r.status_code == 200, f"Vehicle {i+1} creation failed: {r.json()}"
