"""Phase 11 Plan 11-06 — Driver advance (despacho) service tests.

6 tests covering the full advance lifecycle:
  ADV-01  Issue advance on a planned trip succeeds
  ADV-02  Duplicate advance on same trip raises 409
  ADV-03  Issue advance on completed trip raises 409
  ADV-04  Void an issued advance succeeds
  ADV-05  Cannot void a settled advance
  ADV-06  list_advances filters by trip_id and status
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.errors import ApiError
from app.modules.drivers import advance_service
from app.modules.drivers.models import Driver, DriverAdvance
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_user(db, tenant_id):
    u = User(
        tenant_id=tenant_id,
        email=f"user-{uuid4().hex[:8]}@test.local",
        password_hash="$argon2id$test",
        full_name="Test Manager",
        role="manager",
        is_active=True,
    )
    db.add(u)
    await db.flush()
    return u


async def _make_vehicle(db, tenant_id):
    v = Vehicle(tenant_id=tenant_id, plate=f"MZ-{uuid4().hex[:6].upper()}", status="active")
    db.add(v)
    await db.flush()
    return v


async def _make_driver(db, tenant_id):
    d = Driver(tenant_id=tenant_id, full_name=f"Driver {uuid4().hex[:6]}", status="active")
    db.add(d)
    await db.flush()
    return d


async def _make_trip(db, tenant_id, vehicle, driver, status="planned"):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Beira",
        status=status,
    )
    db.add(t)
    await db.flush()
    return t


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adv01_issue_advance_planned_trip(db, tenant_id):
    """ADV-01: Issue advance on a planned trip — creates advance with status 'issued'."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="planned")

    result = await advance_service.issue_advance(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        trip_id=trip.id,
        driver_id=driver.id,
        amount_mzn=Decimal("5000.00"),
        notes="Despacho de viagem",
    )

    assert result["status"] == "issued"
    assert result["trip_id"] == str(trip.id)
    assert result["driver_id"] == str(driver.id)
    assert result["amount_mzn"] == "5000.00"
    assert result["notes"] == "Despacho de viagem"
    assert result["id"] is not None


@pytest.mark.asyncio
async def test_adv02_duplicate_advance_raises_conflict(db, tenant_id):
    """ADV-02: Issuing a second non-voided advance on the same trip raises 409."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="planned")

    # First advance succeeds
    await advance_service.issue_advance(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        trip_id=trip.id,
        driver_id=driver.id,
        amount_mzn=Decimal("3000.00"),
    )

    # Second advance must raise 409
    with pytest.raises(ApiError) as exc_info:
        await advance_service.issue_advance(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            trip_id=trip.id,
            driver_id=driver.id,
            amount_mzn=Decimal("1000.00"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "advance_already_exists"


@pytest.mark.asyncio
async def test_adv03_issue_advance_completed_trip_raises_conflict(db, tenant_id):
    """ADV-03: Cannot issue advance for a completed trip — raises 409 before any DB write."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="completed")

    with pytest.raises(ApiError) as exc_info:
        await advance_service.issue_advance(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            trip_id=trip.id,
            driver_id=driver.id,
            amount_mzn=Decimal("1000.00"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "trip_not_dispatchable"


@pytest.mark.asyncio
async def test_adv04_void_advance_succeeds(db, tenant_id):
    """ADV-04: Voiding an issued advance sets status to 'voided'."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="in_progress")

    issued = await advance_service.issue_advance(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        trip_id=trip.id,
        driver_id=driver.id,
        amount_mzn=Decimal("2000.00"),
    )

    voided = await advance_service.void_advance(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        advance_id=issued["id"],
    )

    assert voided["status"] == "voided"
    assert voided["id"] == issued["id"]


@pytest.mark.asyncio
async def test_adv05_cannot_void_settled_advance(db, tenant_id):
    """ADV-05: Voiding a settled advance raises 409 advance_already_settled."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="planned")

    issued = await advance_service.issue_advance(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        trip_id=trip.id,
        driver_id=driver.id,
        amount_mzn=Decimal("4000.00"),
    )

    # Manually set status to 'settled' to simulate settlement workflow
    advance = await db.scalar(
        select(DriverAdvance).where(DriverAdvance.id == issued["id"])
    )
    advance.status = "settled"
    await db.commit()

    with pytest.raises(ApiError) as exc_info:
        await advance_service.void_advance(
            db,
            tenant_id=tenant_id,
            user_id=user.id,
            advance_id=issued["id"],
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "advance_already_settled"


@pytest.mark.asyncio
async def test_adv06_list_advances_filters_by_trip_and_status(db, tenant_id):
    """ADV-06: list_advances respects trip_id and status_filter correctly."""
    user = await _make_user(db, tenant_id)
    vehicle_a = await _make_vehicle(db, tenant_id)
    vehicle_b = await _make_vehicle(db, tenant_id)
    driver_a = await _make_driver(db, tenant_id)
    driver_b = await _make_driver(db, tenant_id)

    trip_a = await _make_trip(db, tenant_id, vehicle_a, driver_a, status="planned")
    trip_b = await _make_trip(db, tenant_id, vehicle_b, driver_b, status="in_progress")

    await advance_service.issue_advance(
        db, tenant_id=tenant_id, user_id=user.id,
        trip_id=trip_a.id, driver_id=driver_a.id, amount_mzn=Decimal("1000.00"),
    )
    advance_b = await advance_service.issue_advance(
        db, tenant_id=tenant_id, user_id=user.id,
        trip_id=trip_b.id, driver_id=driver_b.id, amount_mzn=Decimal("2000.00"),
    )

    # Filter by trip_a — should only return trip_a's advance
    results_a = await advance_service.list_advances(db, tenant_id=tenant_id, trip_id=trip_a.id)
    assert len(results_a) == 1
    assert results_a[0]["trip_id"] == str(trip_a.id)

    # Filter by trip_b — should only return trip_b's advance
    results_b = await advance_service.list_advances(db, tenant_id=tenant_id, trip_id=trip_b.id)
    assert len(results_b) == 1
    assert results_b[0]["id"] == advance_b["id"]

    # Filter by status "voided" — should return empty (both still issued)
    results_voided = await advance_service.list_advances(
        db, tenant_id=tenant_id, status_filter="voided"
    )
    assert len(results_voided) == 0

    # Void trip_b's advance, then filter — should return 1 voided
    await advance_service.void_advance(
        db, tenant_id=tenant_id, user_id=user.id, advance_id=advance_b["id"]
    )
    results_voided2 = await advance_service.list_advances(
        db, tenant_id=tenant_id, status_filter="voided"
    )
    assert len(results_voided2) == 1
