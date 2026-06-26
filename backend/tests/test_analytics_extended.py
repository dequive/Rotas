"""ANA-01: Extended analytics dashboard KPI tests (route profitability, contract margins,
delivery NPS, top drivers, dashboard endpoint, cross-tenant isolation).

These 7 tests are written first (TDD RED phase) against the new
GET /api/v1/analytics/dashboard endpoint before the implementation exists.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.cargo.models import DeliveryProof
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PERIOD_START = "2026-01-01T00:00:00"
PERIOD_END = "2026-12-31T23:59:59"

BASE_PARAMS = {
    "period_start": PERIOD_START,
    "period_end": PERIOD_END,
}


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


async def _create_closed_trip(
    db,
    tenant_id,
    vehicle_id,
    driver_id,
    origin="Maputo",
    destination="Beira",
    cost=50000,
    km_start=0,
    km_end=500,
):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin=origin,
        destination=destination,
        status="closed",
        closed_at=datetime(2026, 3, 15, tzinfo=UTC),
        total_transport_cost=Decimal(str(cost)),
        km_start=km_start,
        km_end=km_end,
    )
    db.add(t)
    await db.flush()
    return t


# ---------------------------------------------------------------------------
# Test 1: route_profitability — empty when no trips exist for tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_profitability_empty(async_client, auth_headers):
    """ANA-01: No trips for tenant → route_profitability is an empty list."""
    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "route_profitability" in data
    assert data["route_profitability"] == []


# ---------------------------------------------------------------------------
# Test 2: route_profitability returns origin/destination with correct avg_cost
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_route_profitability_returns_origin_destination(
    async_client, db, tenant_id, auth_headers
):
    """ANA-01: 2 closed trips on same route → 1 entry with correct avg_cost."""
    vehicle = await _create_vehicle(db, tenant_id)
    driver = await _create_driver(db, tenant_id)
    await _create_closed_trip(db, tenant_id, vehicle.id, driver.id, "Maputo", "Nampula", cost=800)
    await _create_closed_trip(db, tenant_id, vehicle.id, driver.id, "Maputo", "Nampula", cost=1200)
    await db.commit()

    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    routes = data["route_profitability"]
    assert isinstance(routes, list)

    maputo_nampula = [
        r for r in routes if r["origin"] == "Maputo" and r["destination"] == "Nampula"
    ]
    assert len(maputo_nampula) == 1
    entry = maputo_nampula[0]
    assert entry["trip_count"] == 2
    assert entry["avg_cost"] == pytest.approx(1000.0, abs=0.01)  # (800 + 1200) / 2


# ---------------------------------------------------------------------------
# Test 3: delivery_nps — all intact → 100.0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_nps_all_intact(async_client, db, tenant_id, auth_headers):
    """ANA-01: 3 intact delivery proofs in period → delivery_nps == 100.0."""
    vehicle = await _create_vehicle(db, tenant_id)
    driver = await _create_driver(db, tenant_id)
    for _ in range(3):
        trip = await _create_closed_trip(db, tenant_id, vehicle.id, driver.id)
        dp = DeliveryProof(
            tenant_id=tenant_id,
            trip_id=trip.id,
            cargo_condition="intact",
            delivered_at=datetime(2026, 3, 15, tzinfo=UTC),
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
    assert data["delivery_nps"] == pytest.approx(100.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test 4: delivery_nps — mixed (1 intact / 1 damaged) → 50.0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delivery_nps_mixed(async_client, db, tenant_id, auth_headers):
    """ANA-01: 1 intact + 1 damaged → delivery_nps == 50.0."""
    vehicle = await _create_vehicle(db, tenant_id)
    driver = await _create_driver(db, tenant_id)
    trip1 = await _create_closed_trip(db, tenant_id, vehicle.id, driver.id)
    trip2 = await _create_closed_trip(db, tenant_id, vehicle.id, driver.id)
    for trip, condition in [(trip1, "intact"), (trip2, "damaged")]:
        dp = DeliveryProof(
            tenant_id=tenant_id,
            trip_id=trip.id,
            cargo_condition=condition,
            delivered_at=datetime(2026, 3, 15, tzinfo=UTC),
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
    assert data["delivery_nps"] == pytest.approx(50.0, abs=0.01)


# ---------------------------------------------------------------------------
# Test 5: top_drivers — max 5 entries even with 6 drivers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_top_drivers_max_5(async_client, db, tenant_id, auth_headers):
    """ANA-01: 6 drivers each with 1 trip → top_drivers list has at most 5 entries."""
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
# Test 6: Dashboard endpoint returns all 8 expected top-level keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_endpoint_returns_all_blocks(async_client, auth_headers):
    """ANA-01: GET /api/v1/analytics/dashboard returns all 8 expected top-level keys."""
    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    expected_keys = {
        "route_profitability",
        "contract_margins",
        "delivery_nps",
        "top_drivers",
        "cost_per_km",
        "fleet_utilization",
        "l_per_100km",
        "trips_completed",
    }
    missing = expected_keys - set(data.keys())
    assert not missing, f"Dashboard response missing keys: {missing}"


# ---------------------------------------------------------------------------
# Test 7: Cross-tenant isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_cross_tenant_isolation(async_client, db, tenant_id, auth_headers):
    """ANA-01: Tenant B data must not appear in Tenant A dashboard response."""
    # Seed a distinct second tenant
    suffix = uuid4().hex[:8]
    tenant_b = Tenant(name=f"Tenant B {suffix}", slug=f"tenant-b-{suffix}")
    db.add(tenant_b)
    await db.flush()

    vb = Vehicle(
        tenant_id=tenant_b.id,
        plate=f"MZ-B{uuid4().hex[:5].upper()}",
        status="active",
    )
    db.add(vb)
    db_driver = Driver(
        tenant_id=tenant_b.id,
        full_name=f"Driver B {uuid4().hex[:6]}",
        status="active",
    )
    db.add(db_driver)
    await db.flush()

    # Tenant B trip: unique route "Lichinga→Mocuba" with distinctive cost
    trip_b = Trip(
        tenant_id=tenant_b.id,
        vehicle_id=vb.id,
        driver_id=db_driver.id,
        origin="Lichinga",
        destination="Mocuba",
        status="closed",
        total_transport_cost=Decimal("99999.99"),
        km_start=0,
        km_end=400,
        closed_at=datetime(2026, 3, 15, tzinfo=UTC),
    )
    db.add(trip_b)
    await db.commit()

    # Query Tenant A — must not see Tenant B data
    response = await async_client.get(
        "/api/v1/analytics/dashboard",
        params=BASE_PARAMS,
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()

    routes = data.get("route_profitability", [])
    assert all(not (r["origin"] == "Lichinga" and r["destination"] == "Mocuba") for r in routes), (
        "Tenant B route 'Lichinga→Mocuba' must not appear in Tenant A dashboard"
    )

    top_driver_ids = {str(dr["driver_id"]) for dr in data.get("top_drivers", [])}
    assert str(db_driver.id) not in top_driver_ids, (
        "Tenant B driver must not appear in Tenant A top_drivers"
    )
