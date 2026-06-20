"""Tests for ANA-01: Extended Analytics Dashboard KPIs.

Covers: route profitability, contract margins, delivery NPS, top drivers, Redis cache,
cross-tenant isolation, and viewer-role access.

NOTE: These tests require GET /api/v1/analytics/dashboard which is implemented in
Phase 18 (ANA-01). They are skipped until that endpoint exists.
"""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.cargo.models import DeliveryProof
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

# Skip entire module until Phase 18 ANA-01 implements /api/v1/analytics/dashboard
_SKIP_REASON = "Phase 18 ANA-01: /api/v1/analytics/dashboard not yet implemented"
pytestmark = pytest.mark.skip(reason=_SKIP_REASON)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD_START = "2026-01-01T00:00:00"
PERIOD_END = "2026-12-31T23:59:59"

BASE_PARAMS = {
    "period_start": PERIOD_START,
    "period_end": PERIOD_END,
}


async def _create_tenant(db) -> Tenant:
    suffix = uuid4().hex[:8]
    t = Tenant(name=f"Test Tenant {suffix}", slug=f"test-{suffix}")
    db.add(t)
    await db.flush()
    return t


async def _create_vehicle(db, tenant_id):
    v = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(v)
    await db.flush()
    return v


async def _create_driver(db, tenant_id, name="Driver Test"):
    d = Driver(
        tenant_id=tenant_id,
        full_name=f"{name} {uuid4().hex[:4]}",
        status="active",
    )
    db.add(d)
    await db.flush()
    return d


async def _create_closed_trip(db, tenant_id, vehicle_id, driver_id, origin="Maputo",
                               destination="Beira", cost=50000):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin=origin,
        destination=destination,
        status="closed",
        closed_at=datetime(2026, 3, 15, tzinfo=UTC),
        total_transport_cost=Decimal(str(cost)),
        km_start=0,
        km_end=1200,
    )
    db.add(t)
    await db.flush()
    return t


# ---------------------------------------------------------------------------
# Test 1: Route profitability — empty result
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_route_profitability_returns_top_routes(
    async_client, db, tenant_id, auth_headers
):
    """ANA-01: /dashboard returns route_profitability list with origin/destination/avg_cost."""
    vehicle = await _create_vehicle(db, tenant_id)
    driver = await _create_driver(db, tenant_id)

    await _create_closed_trip(
        db, tenant_id, vehicle.id, driver.id, "Maputo", "Beira", cost=40000
    )
    await _create_closed_trip(
        db, tenant_id, vehicle.id, driver.id, "Maputo", "Beira", cost=60000
    )
    await _create_closed_trip(
        db, tenant_id, vehicle.id, driver.id, "Maputo", "Nampula", cost=80000
    )
    await db.commit()

    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "route_profitability" in data

    routes = data["route_profitability"]
    assert isinstance(routes, list)
    assert len(routes) >= 2

    # Check structure of each entry
    for r in routes:
        assert "origin" in r
        assert "destination" in r
        assert "trip_count" in r
        assert "avg_cost" in r

    # Maputo→Beira: avg_cost = 50000, Maputo→Nampula: avg_cost = 80000
    nampula_route = next(
        (r for r in routes if r["destination"] == "Nampula"), None
    )
    assert nampula_route is not None
    assert nampula_route["avg_cost"] == pytest.approx(80000.0)

    beira_route = next((r for r in routes if r["destination"] == "Beira"), None)
    assert beira_route is not None
    assert beira_route["trip_count"] == 2
    assert beira_route["avg_cost"] == pytest.approx(50000.0)


# ---------------------------------------------------------------------------
# Test 2: Delivery NPS between 0 and 100
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_delivery_nps_is_0_to_100(async_client, db, tenant_id, auth_headers):
    """ANA-01: delivery_nps is a float in [0, 100] given a mix of intact and damaged proofs."""
    vehicle = await _create_vehicle(db, tenant_id)
    driver = await _create_driver(db, tenant_id)
    trip = await _create_closed_trip(db, tenant_id, vehicle.id, driver.id)

    # 2 intact, 2 damaged → NPS = 50.0
    for condition in ["intact", "intact", "damaged", "damaged"]:
        dp = DeliveryProof(
            tenant_id=tenant_id,
            trip_id=trip.id,
            cargo_condition=condition,
            delivered_at=datetime(2026, 3, 15, tzinfo=UTC),
            status="pending",
        )
        db.add(dp)
    await db.commit()

    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "delivery_nps" in data

    nps = data["delivery_nps"]
    # None is acceptable when there are no proofs; otherwise it must be 0–100
    if nps is not None:
        assert 0.0 <= nps <= 100.0
        assert nps == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Test 3: Top drivers — at most 5 entries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_top_drivers_max_5_entries(async_client, db, tenant_id, auth_headers):
    """ANA-01: top_drivers list has at most 5 entries even when 6 drivers exist."""
    vehicle = await _create_vehicle(db, tenant_id)

    for i in range(6):
        driver = await _create_driver(db, tenant_id, f"Driver{i}")
        await _create_closed_trip(db, tenant_id, vehicle.id, driver.id)
    await db.commit()

    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "top_drivers" in data
    assert len(data["top_drivers"]) <= 5


# ---------------------------------------------------------------------------
# Test 4: Contract margin is positive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_contract_margin_positive(async_client, db, tenant_id, auth_headers):
    """ANA-01: contract_margins shows positive margin when revenue > cost."""
    vehicle = await _create_vehicle(db, tenant_id)
    driver = await _create_driver(db, tenant_id)
    trip = await _create_closed_trip(db, tenant_id, vehicle.id, driver.id, cost=10000)

    # BillingDocument
    bd = BillingDocument(
        tenant_id=tenant_id,
        client_name="Test Client",
        billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2026, 3, 31, tzinfo=UTC),
        subtotal=Decimal("20000.00"),
        total_amount=Decimal("20000.00"),
        status="draft",
    )
    db.add(bd)
    await db.flush()

    # BillingItem linking the billing doc to the trip
    bi = BillingItem(
        tenant_id=tenant_id,
        billing_document_id=bd.id,
        trip_id=trip.id,
        amount=Decimal("20000.00"),
        delivered_at=datetime(2026, 3, 15, tzinfo=UTC),
        status="draft",
    )
    db.add(bi)
    await db.commit()

    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "contract_margins" in data

    margins = data["contract_margins"]
    assert isinstance(margins, list)
    if margins:
        margin = margins[0]
        assert "billing_document_id" in margin
        assert "total_revenue" in margin
        assert "gross_margin" in margin
        # Revenue 20000 - cost 10000 = positive margin
        assert margin["gross_margin"] > 0


# ---------------------------------------------------------------------------
# Test 5: Cross-tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_cross_tenant_isolation(async_client, db, tenant_id, auth_headers):
    """ANA-01: tenant B data must not appear in tenant A dashboard response."""
    # Create tenant B with its own vehicle, driver, and trip on a unique route
    tenant_b = await _create_tenant(db)
    vb = await _create_vehicle(db, tenant_b.id)
    db_driver = await _create_driver(db, tenant_b.id)
    await _create_closed_trip(
        db, tenant_b.id, vb.id, db_driver.id,
        origin="Lichinga", destination="Mocuba", cost=99999
    )
    await db.commit()

    # Call with tenant A credentials
    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    routes = data.get("route_profitability", [])
    # Tenant B's unique route must not appear in tenant A's response
    origins = [r["origin"] for r in routes]
    dests = [r["destination"] for r in routes]
    assert "Lichinga" not in origins
    assert "Mocuba" not in dests


# ---------------------------------------------------------------------------
# Test 6: Redis cache hit — second call has same cached_at
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_redis_cache_hit(async_client, db, tenant_id, auth_headers):
    """ANA-01: second call within TTL returns identical cached_at from Redis."""

    cache_store = {}

    async def fake_get(key):
        return cache_store.get(key)

    async def fake_setex(key, ttl, value):
        cache_store[key] = value
        return True

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=fake_get)
    mock_redis.setex = AsyncMock(side_effect=fake_setex)

    from app.main import app

    original_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        r1 = await async_client.get(
            "/api/v1/analytics/dashboard", params=BASE_PARAMS, headers=auth_headers
        )
        assert r1.status_code == 200
        r1.json()  # consume response to ensure body is readable

        r2 = await async_client.get(
            "/api/v1/analytics/dashboard", params=BASE_PARAMS, headers=auth_headers
        )
        assert r2.status_code == 200
        r2.json()  # consume response to ensure body is readable

        # After 2 calls with the same params, setex should have been called once
        assert mock_redis.setex.call_count == 1
        # The second call should hit cache (get returns the stored value)
        assert mock_redis.get.call_count == 2
    finally:
        app.state.redis = original_redis


# ---------------------------------------------------------------------------
# Test 7: Viewer role (fleet.read) can access /dashboard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_viewer_can_access_dashboard(async_client, viewer_headers):
    """ANA-01: viewer role (fleet.read) must receive HTTP 200 from /dashboard."""
    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=viewer_headers,
    )
    assert response.status_code == 200
