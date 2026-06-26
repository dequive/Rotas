"""Phase 11 Plan 11-06 — Trip settlement (liquidação) service tests.

6 tests covering the full settlement lifecycle:
  SET-01  compute_settlement on completed trip with advance — correct balance
  SET-02  compute_settlement is idempotent (no duplicate created)
  SET-03  compute_settlement on non-completed trip raises 409
  SET-04  approve_settlement transitions status to 'approved'
  SET-05  reject_settlement transitions status to 'rejected' with reason
  SET-06  Cannot approve an already-approved settlement (409)
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.errors import ApiError
from app.modules.drivers import advance_service, settlement_service
from app.modules.drivers.models import Driver
from app.modules.trips.models import Trip, TripCost
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


async def _make_trip(db, tenant_id, vehicle, driver, status="completed"):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Nacala",
        status=status,
    )
    db.add(t)
    await db.flush()
    return t


async def _add_cost(db, tenant_id, trip, cost_type, amount):
    cost = TripCost(
        tenant_id=tenant_id,
        trip_id=trip.id,
        cost_type=cost_type,
        amount=Decimal(str(amount)),
        currency="MZN",
        description=f"{cost_type} cost",
        request_reference=f"test-{uuid4().hex[:12]}",
        incurred_at=datetime.now(UTC),
    )
    db.add(cost)
    await db.flush()
    return cost


# ── Tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set01_compute_settlement_correct_balance(db, tenant_id):
    """SET-01: Settlement balance = advance - total_costs; positive = driver owes company."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)

    # Create planned trip, issue advance, then complete it
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="planned")
    await advance_service.issue_advance(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        trip_id=trip.id,
        driver_id=driver.id,
        amount_mzn=Decimal("5000.00"),
    )
    trip.status = "completed"
    await db.flush()

    # Add costs: 1500 + 800 = 2300
    await _add_cost(db, tenant_id, trip, "fuel", "1500.00")
    await _add_cost(db, tenant_id, trip, "toll", "800.00")
    await db.commit()

    result = await settlement_service.compute_settlement(db, tenant_id=tenant_id, trip_id=trip.id)

    assert result["status"] == "pending"
    assert Decimal(result["total_costs_mzn"]) == Decimal("2300.00")
    assert Decimal(result["advance_amount_mzn"]) == Decimal("5000.00")
    # balance = 5000 - 2300 = 2700 (positive: driver owes company)
    assert Decimal(result["balance_mzn"]) == Decimal("2700.00")
    assert result["advance_id"] is not None


@pytest.mark.asyncio
async def test_set02_compute_settlement_is_idempotent(db, tenant_id):
    """SET-02: Calling compute_settlement twice returns same ID — no duplicate created."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="completed")

    first = await settlement_service.compute_settlement(db, tenant_id=tenant_id, trip_id=trip.id)
    second = await settlement_service.compute_settlement(db, tenant_id=tenant_id, trip_id=trip.id)

    assert first["id"] == second["id"], "Idempotent — same settlement returned on second call"


@pytest.mark.asyncio
async def test_set03_compute_settlement_non_completed_trip_raises(db, tenant_id):
    """SET-03: compute_settlement on a planned trip raises 409 trip_not_completed."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="planned")

    with pytest.raises(ApiError) as exc_info:
        await settlement_service.compute_settlement(db, tenant_id=tenant_id, trip_id=trip.id)

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "trip_not_completed"


@pytest.mark.asyncio
async def test_set04_approve_settlement(db, tenant_id):
    """SET-04: approve_settlement transitions a pending settlement to 'approved'."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="completed")

    settlement = await settlement_service.compute_settlement(
        db, tenant_id=tenant_id, trip_id=trip.id
    )
    assert settlement["status"] == "pending"

    approved = await settlement_service.approve_settlement(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        settlement_id=settlement["id"],
    )

    assert approved["status"] == "approved"
    assert approved["approved_by"] == str(user.id)
    assert approved["approved_at"] is not None


@pytest.mark.asyncio
async def test_set05_reject_settlement(db, tenant_id):
    """SET-05: reject_settlement transitions a pending settlement to 'rejected' with reason."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="completed")

    settlement = await settlement_service.compute_settlement(
        db, tenant_id=tenant_id, trip_id=trip.id
    )

    rejected = await settlement_service.reject_settlement(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        settlement_id=settlement["id"],
        reason="Despesas não documentadas correctamente.",
    )

    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "Despesas não documentadas correctamente."


@pytest.mark.asyncio
async def test_set06_cannot_approve_already_approved(db, tenant_id):
    """SET-06: Approving an already-approved settlement raises 409."""
    user = await _make_user(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver, status="completed")

    settlement = await settlement_service.compute_settlement(
        db, tenant_id=tenant_id, trip_id=trip.id
    )

    # First approval succeeds
    await settlement_service.approve_settlement(
        db, tenant_id=tenant_id, user_id=user.id, settlement_id=settlement["id"]
    )

    # Second approval must raise 409
    with pytest.raises(ApiError) as exc_info:
        await settlement_service.approve_settlement(
            db, tenant_id=tenant_id, user_id=user.id, settlement_id=settlement["id"]
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "settlement_already_approved"
