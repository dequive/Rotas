"""Tests for worker alert tasks: driver document expiry and HOS violations.

Tests call service-layer functions directly (same approach as the tasks themselves)
to avoid needing a live ARQ / Redis setup. The ctx["db_factory"] pattern is
exercised via a thin async-context-manager adapter over the test db fixture.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from datetime import date as _date
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.alerts.models import Alert
from app.modules.drivers.models import Driver
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_ctx(db):
    """Build a minimal ctx dict whose db_factory wraps the provided test session."""

    @asynccontextmanager
    async def _factory():
        yield db

    return {"db_factory": _factory}


# ── Task 1: task_check_driver_document_expiry ─────────────────────────────────


@pytest.mark.asyncio
async def test_task_check_driver_document_expiry_generates_alert(db, tenant_id):
    """Driver with document expiring in 5 days → alert created."""
    expiry = (_date.today() + timedelta(days=5)).isoformat()
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Test Driver PVF-01",
        status="active",
        documents={"carta_conducao": {"expiry_date": expiry, "number": "DR-001"}},
    )
    db.add(driver)
    await db.commit()

    from app.worker import task_check_driver_document_expiry

    result = await task_check_driver_document_expiry(_make_ctx(db))

    assert "1" in result or int(result.split()[1]) >= 1

    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.alert_type == "driver_document_expiring_soon",
            Alert.entity_id == driver.id,
        )
    )
    assert alert is not None
    assert alert.priority == "critical"  # <= 7 days → critical
    assert "carta_conducao" in alert.title


@pytest.mark.asyncio
async def test_task_check_driver_document_expiry_skips_non_expiring(db, tenant_id):
    """Driver with document expiring in 60 days → no alert created."""
    expiry = (_date.today() + timedelta(days=60)).isoformat()
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Test Driver PVF-02",
        status="active",
        documents={"passaporte": {"expiry_date": expiry}},
    )
    db.add(driver)
    await db.commit()

    from app.worker import task_check_driver_document_expiry

    await task_check_driver_document_expiry(_make_ctx(db))

    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.alert_type == "driver_document_expiring_soon",
            Alert.entity_id == driver.id,
        )
    )
    # No alert for THIS driver — the 60-day doc is outside the 30-day window
    assert alert is None


@pytest.mark.asyncio
async def test_task_check_driver_document_expiry_idempotent(db, tenant_id):
    """Running the task twice for same document produces exactly 1 alert."""
    expiry = (_date.today() + timedelta(days=3)).isoformat()
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Test Driver PVF-03",
        status="active",
        documents={"bi": {"expiry_date": expiry}},
    )
    db.add(driver)
    await db.commit()

    from app.worker import task_check_driver_document_expiry

    ctx = _make_ctx(db)
    await task_check_driver_document_expiry(ctx)
    await task_check_driver_document_expiry(ctx)

    count_result = await db.execute(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.alert_type == "driver_document_expiring_soon",
            Alert.entity_id == driver.id,
        )
    )
    alerts = count_result.scalars().all()
    assert len(alerts) == 1


# ── Task 2: task_check_hos_violations ────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_check_hos_violations_generates_warning(db, tenant_id):
    """Driver with trip departing 8.5 hours ago in in_progress → hos warning alert."""
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(vehicle)

    driver = Driver(
        tenant_id=tenant_id,
        full_name="Test Driver PVF-04",
        status="active",
    )
    db.add(driver)
    await db.flush()

    departure = datetime.now(UTC) - timedelta(hours=8, minutes=30)
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Beira",
        status="in_progress",
        actual_departure=departure,
    )
    db.add(trip)
    await db.commit()

    from app.worker import task_check_hos_violations

    result = await task_check_hos_violations(_make_ctx(db))

    # Result should report at least 1 warning
    assert "warning" in result
    parts = result.split(",")
    warnings_part = parts[0]  # "HOS: X warnings"
    assert int(warnings_part.split()[1]) >= 1

    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.alert_type == "driver_hos_warning",
            Alert.entity_id == driver.id,
        )
    )
    assert alert is not None
    assert alert.priority == "high"


@pytest.mark.asyncio
async def test_task_check_hos_violations_ok_driver_no_alert(db, tenant_id):
    """Driver with trip that started only 2 hours ago → no HOS alert."""
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(vehicle)

    driver = Driver(
        tenant_id=tenant_id,
        full_name="Test Driver PVF-05",
        status="active",
    )
    db.add(driver)
    await db.flush()

    departure = datetime.now(UTC) - timedelta(hours=2)
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Inhambane",
        status="in_progress",
        actual_departure=departure,
    )
    db.add(trip)
    await db.commit()

    from app.worker import task_check_hos_violations

    await task_check_hos_violations(_make_ctx(db))

    # Warnings and violations for this driver should be 0
    # (other test data may have produced alerts, check this driver specifically)
    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.alert_type.in_(["driver_hos_warning", "driver_hos_violation"]),
            Alert.entity_id == driver.id,
        )
    )
    assert alert is None
