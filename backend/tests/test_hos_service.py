"""Tests for HOS (Hours of Service) calculation in hos_service.py.

Behaviors tested (16-02 Task 1):
  1. Driver with one 3h + one 2h trip today → hours_today=5.0, status="ok"
  2. Driver with one 9.5h trip today → hours_today=9.5, status="violation",
     violation_reason="daily_limit"
  3. Driver with 8.5h today → status="warning"  (>= 8h, < 9h)
  4. Driver with 10h/day Mon–Fri = 50h week → status="violation",
     violation_reason="weekly_limit"
  5. Trip with NULL actual_departure is excluded
  6. In-progress trip (actual_arrival=None) uses NOW()-actual_departure
  7. Trips from a different tenant are NOT included (tenant isolation)
"""

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.drivers.hos_service import (
    HOS_VIOLATION_HOURS_DAY,
    HOS_VIOLATION_HOURS_WEEK,
    HOS_WARNING_HOURS_DAY,
    calculate_driving_hours,
)
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _dt(offset_hours: float, *, base: datetime | None = None) -> datetime:
    """Return a timezone-aware UTC datetime offset_hours from base (default: today 00:00 UTC)."""
    if base is None:
        today = _today_utc()
        base = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=UTC)
    return base + timedelta(hours=offset_hours)


async def _make_driver(db, tenant_id) -> Driver:
    """Create a minimal Driver row to satisfy FK constraints."""
    driver = Driver(
        tenant_id=tenant_id,
        full_name=f"HOS Test Driver {uuid4().hex[:8]}",
        status="active",
    )
    db.add(driver)
    await db.flush()
    return driver


async def _make_vehicle(db, tenant_id) -> Vehicle:
    """Create a minimal Vehicle row to satisfy FK constraints."""
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"TH-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(vehicle)
    await db.flush()
    return vehicle


def _make_trip(
    *,
    tenant_id,
    driver_id,
    vehicle_id,
    actual_departure: datetime | None,
    actual_arrival: datetime | None,
    status: str = "completed",
) -> Trip:
    return Trip(
        id=uuid4(),
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin="A",
        destination="B",
        status=status,
        billing_status="pending_delivery_proof",
        actual_departure=actual_departure,
        actual_arrival=actual_arrival,
    )


# ---------------------------------------------------------------------------
# Test 1: Two short trips today → hours_today=5.0, status="ok"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_short_trips_today_ok(db, tenant_id):
    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    # 3h trip
    t1 = _make_trip(
        tenant_id=tenant_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        actual_departure=_dt(1),
        actual_arrival=_dt(4),
    )
    # 2h trip
    t2 = _make_trip(
        tenant_id=tenant_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        actual_departure=_dt(5),
        actual_arrival=_dt(7),
    )
    db.add_all([t1, t2])
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db)

    assert result["hours_today"] == pytest.approx(5.0, abs=0.05)
    assert result["status"] == "ok"
    assert result["violation_reason"] is None


# ---------------------------------------------------------------------------
# Test 2: 9.5h trip today → violation / daily_limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_long_trip_today_violation(db, tenant_id):
    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    t = _make_trip(
        tenant_id=tenant_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        actual_departure=_dt(0),
        actual_arrival=_dt(9.5),
    )
    db.add(t)
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db)

    assert result["hours_today"] == pytest.approx(9.5, abs=0.05)
    assert result["status"] == "violation"
    assert result["violation_reason"] == "daily_limit"


# ---------------------------------------------------------------------------
# Test 3: 8.5h today → warning (>= 8h, < 9h)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_8_5h_today_warning(db, tenant_id):
    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    t = _make_trip(
        tenant_id=tenant_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        actual_departure=_dt(0),
        actual_arrival=_dt(8.5),
    )
    db.add(t)
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db)

    assert result["hours_today"] == pytest.approx(8.5, abs=0.05)
    assert result["status"] == "warning"
    assert result["violation_reason"] is None


# ---------------------------------------------------------------------------
# Test 4: 50h over Mon–Fri → weekly violation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weekly_violation(db, tenant_id):
    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)

    # Get Monday of current week
    today = _today_utc()
    monday = today - timedelta(days=today.weekday())

    trips = []
    for day_offset in range(5):  # Mon–Fri
        day = monday + timedelta(days=day_offset)
        base = datetime(day.year, day.month, day.day, 6, 0, 0, tzinfo=UTC)
        trips.append(
            _make_trip(
                tenant_id=tenant_id,
                driver_id=driver.id,
                vehicle_id=vehicle.id,
                actual_departure=base,
                actual_arrival=base + timedelta(hours=10),
            )
        )
    db.add_all(trips)
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db, target_date=today)

    assert result["hours_this_week"] == pytest.approx(50.0, abs=0.1)
    assert result["status"] == "violation"
    assert result["violation_reason"] == "weekly_limit"


# ---------------------------------------------------------------------------
# Test 5: Trip with NULL actual_departure is excluded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_departure_excluded(db, tenant_id):
    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    t = _make_trip(
        tenant_id=tenant_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        actual_departure=None,
        actual_arrival=None,
        status="completed",
    )
    db.add(t)
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db)

    assert result["hours_today"] == 0.0
    assert result["hours_this_week"] == 0.0
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 6: In-progress trip (actual_arrival=None) uses NOW() as end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_progress_trip_uses_now(db, tenant_id):
    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    # Start trip 2 hours ago
    departure = datetime.now(UTC) - timedelta(hours=2)
    t = _make_trip(
        tenant_id=tenant_id,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
        actual_departure=departure,
        actual_arrival=None,  # in progress
        status="in_progress",
    )
    db.add(t)
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db)

    # Should be approximately 2h (allow ±2 minutes for test execution time)
    assert result["hours_today"] == pytest.approx(2.0, abs=0.05)
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 7: Trips from a different tenant are NOT included
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_isolation(db, tenant_id):
    # Create a second tenant
    other_tenant = Tenant(name="Other Tenant HOS", slug=f"other-hos-{uuid4().hex[:8]}")
    db.add(other_tenant)
    await db.flush()

    driver_id = uuid4()

    # Need a real driver and vehicle under the other tenant
    other_driver = Driver(
        id=driver_id,
        tenant_id=other_tenant.id,
        full_name="Cross Tenant Driver HOS",
        status="active",
    )
    other_vehicle = Vehicle(
        tenant_id=other_tenant.id,
        plate=f"OT-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add_all([other_driver, other_vehicle])
    await db.flush()

    # Trip under the OTHER tenant — should not count
    t_other = _make_trip(
        tenant_id=other_tenant.id,
        driver_id=other_driver.id,
        vehicle_id=other_vehicle.id,
        actual_departure=_dt(0),
        actual_arrival=_dt(9.5),
    )
    db.add(t_other)
    await db.commit()

    # Query for the original tenant → should see 0 hours
    result = await calculate_driving_hours(driver_id, tenant_id, db)

    assert result["hours_today"] == 0.0
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Constants sanity check
# ---------------------------------------------------------------------------


def test_hos_constants():
    assert HOS_WARNING_HOURS_DAY == 8.0
    assert HOS_VIOLATION_HOURS_DAY == 9.0
    assert HOS_VIOLATION_HOURS_WEEK == 48.0
