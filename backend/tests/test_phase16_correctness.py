"""Phase 16 correctness tests — HOS guard and availability status values.

Tests assert VALUES not just HTTP status codes (presence vs correctness rule).
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal
from app.main import app
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder


async def _make_tenant(db) -> Tenant:
    t = Tenant(name=f"P16 Tenant {uuid4().hex[:8]}", slug=f"p16-{uuid4().hex[:8]}")
    db.add(t)
    await db.flush()
    return t


async def _make_driver(db, tenant_id) -> Driver:
    d = Driver(tenant_id=tenant_id, full_name=f"P16 Driver {uuid4().hex[:8]}", status="active")
    db.add(d)
    await db.flush()
    return d


async def _make_vehicle(db, tenant_id) -> Vehicle:
    v = Vehicle(
        tenant_id=tenant_id,
        plate=f"P16-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(v)
    await db.flush()
    return v


def _completed_trip(*, tenant_id, driver_id, vehicle_id, hours: float, offset: float = 0.0) -> Trip:
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    dep = today + timedelta(hours=offset)
    arr = dep + timedelta(hours=hours)
    return Trip(
        id=uuid4(),
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        origin="Maputo",
        destination="Beira",
        status="completed",
        billing_status="pending_delivery_proof",
        actual_departure=dep,
        actual_arrival=arr,
    )


@pytest.mark.asyncio
async def test_hos_hours_value_correct(db, tenant_id):
    """Driver with one 3h trip today → hours_today == 3.0 exactly."""
    from app.modules.drivers.hos_service import calculate_driving_hours

    driver = await _make_driver(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    db.add(
        _completed_trip(
            tenant_id=tenant_id, driver_id=driver.id, vehicle_id=vehicle.id, hours=3.0, offset=1.0
        )
    )
    await db.commit()

    result = await calculate_driving_hours(driver.id, tenant_id, db)

    assert result["hours_today"] == pytest.approx(3.0, abs=0.05), (
        f"Expected hours_today=3.0, got {result['hours_today']}"
    )
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_hos_violation_blocks_trip_create():
    """Driver with 9.5h today cannot start a new trip — must return 409 + hos_violation_active."""
    async with AsyncSessionLocal() as db:
        tenant = await _make_tenant(db)
        driver = await _make_driver(db, tenant.id)
        vehicle = await _make_vehicle(db, tenant.id)
        db.add(
            _completed_trip(
                tenant_id=tenant.id, driver_id=driver.id, vehicle_id=vehicle.id, hours=9.5
            )
        )
        await db.commit()

    async with AsyncSessionLocal() as db:
        v2 = await _make_vehicle(db, tenant.id)
        await db.commit()
        v2_id = v2.id

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant.id)}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/trips",
            json={
                "vehicle_id": str(v2_id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Inhambane",
            },
            headers=headers,
        )

    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
    err = resp.json().get("error", {})
    assert err.get("code") == "hos_violation_active", f"Wrong error code: {err.get('code')}"
    assert err.get("details", {}).get("override_required") is True


@pytest.mark.asyncio
async def test_vehicle_in_maintenance_blocks_trip():
    """Vehicle with active WorkOrder returns 409 + vehicle_workshop_blocked."""
    async with AsyncSessionLocal() as db:
        tenant = await _make_tenant(db)
        driver = await _make_driver(db, tenant.id)
        vehicle = await _make_vehicle(db, tenant.id)
        wo = WorkOrder(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            work_order_number=f"WO-{uuid4().hex[:6].upper()}",
            planned_work="Engine overhaul",
            status="in_progress",
        )
        db.add(wo)
        await db.commit()
        wo_id = wo.id

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant.id)}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post(
            "/api/v1/trips",
            json={
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Nampula",
            },
            headers=headers,
        )

    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
    err = resp.json().get("error", {})
    assert err.get("code") == "vehicle_workshop_blocked", f"Wrong error code: {err.get('code')}"
    assert err.get("details", {}).get("work_order_id") == str(wo_id), (
        f"work_order_id mismatch: expected {wo_id}, "
        f"got {err.get('details', {}).get('work_order_id')}"
    )


@pytest.mark.asyncio
async def test_availability_drivers_status_not_available_for_active_trip():
    """Driver with in_progress trip → availability_status must not be 'available'."""
    async with AsyncSessionLocal() as db:
        tenant = await _make_tenant(db)
        driver = await _make_driver(db, tenant.id)
        vehicle = await _make_vehicle(db, tenant.id)
        active_trip = Trip(
            id=uuid4(),
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            driver_id=driver.id,
            origin="Maputo",
            destination="Tete",
            status="in_progress",
            billing_status="pending_delivery_proof",
        )
        db.add(active_trip)
        await db.commit()
        driver_id = driver.id

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant.id)}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/availability/drivers", headers=headers)

    assert resp.status_code == 200
    items = resp.json().get("items", [])
    driver_item = next((i for i in items if i.get("driver_id") == str(driver_id)), None)
    assert driver_item is not None, f"Driver {driver_id} not in availability response"

    avail_status = driver_item.get("availability_status")
    assert avail_status != "available", (
        f"Driver with active trip must not be 'available', got '{avail_status}'"
    )


@pytest.mark.asyncio
async def test_availability_vehicles_in_maintenance_has_work_order_id():
    """Vehicle in active WorkOrder: computed_status='in_maintenance', active_work_order_id set."""
    async with AsyncSessionLocal() as db:
        tenant = await _make_tenant(db)
        vehicle = await _make_vehicle(db, tenant.id)
        wo = WorkOrder(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            work_order_number=f"WO-AV-{uuid4().hex[:6].upper()}",
            planned_work="Brake replacement",
            status="in_progress",
        )
        db.add(wo)
        await db.commit()
        vehicle_id = vehicle.id
        wo_id = wo.id

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant.id)}
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/v1/availability/vehicles", headers=headers)

    assert resp.status_code == 200
    items = resp.json().get("items", [])
    v_item = next((i for i in items if i.get("vehicle_id") == str(vehicle_id)), None)
    assert v_item is not None, f"Vehicle {vehicle_id} not in availability response"

    computed = v_item.get("computed_status")
    assert computed == "in_maintenance", (
        f"Expected computed_status='in_maintenance', got '{computed}'"
    )
    assert v_item.get("active_work_order_id") == str(wo_id), (
        f"active_work_order_id mismatch: expected {wo_id}, got {v_item.get('active_work_order_id')}"
    )
