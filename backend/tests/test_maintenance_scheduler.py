"""MAINT-01: Preventive Maintenance Scheduler — test stubs.

These stubs document required behaviors. Remove skip markers as implementation completes.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenancePlan,
    MaintenanceSchedule,
    WorkOrder,
)
from app.modules.workshop.service import (
    evaluate_maintenance_schedule,
    get_imminent_maintenance_alerts,
)

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


async def _seed_tenant_and_vehicle(current_km: int = 0) -> tuple:
    """Create a fresh tenant + vehicle for scheduler tests."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Sched Tenant {suffix}", slug=f"sched-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"SCH-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            current_km=current_km,
        )
        db.add(vehicle)
        await db.commit()
        return tenant.id, vehicle.id


async def _create_plan(
    tenant_id,
    vehicle_id,
    *,
    next_due_km: int | None = None,
    next_due_at: datetime | None = None,
    interval_km: int | None = None,
    interval_days: int | None = None,
) -> object:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        plan = MaintenancePlan(
            tenant_id=tenant_id,
            vehicle_id=vehicle_id,
            request_reference=f"REF-SCHED-{suffix}",
            name=f"Plano Teste {suffix}",
            interval_km=interval_km,
            interval_days=interval_days,
            next_due_km=next_due_km,
            next_due_at=next_due_at,
            status="active",
        )
        db.add(plan)
        await db.commit()
        return plan.id


async def test_scheduler_creates_work_order_on_km_trigger():
    """MAINT-01 D-02: When vehicle.current_km >= plan.next_due_km,
    evaluate_maintenance_schedule() creates a WorkOrder with status='draft'."""
    tenant_id, vehicle_id = await _seed_tenant_and_vehicle(current_km=10001)
    plan_id = await _create_plan(
        tenant_id,
        vehicle_id,
        next_due_km=10000,
        interval_km=5000,
    )

    async with AsyncSessionLocal() as db:
        result = await evaluate_maintenance_schedule(db, tenant_id, actor_id=None)

    assert result["created"] >= 1

    async with AsyncSessionLocal() as db:
        wo = await db.scalar(
            select(WorkOrder).where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.vehicle_id == vehicle_id,
                WorkOrder.plan_id == plan_id,
            )
        )
    assert wo is not None
    assert wo.status == "draft"
    assert wo.plan_id == plan_id


async def test_scheduler_creates_work_order_on_date_trigger():
    """MAINT-01 D-02: When today >= plan.next_due_at,
    evaluate_maintenance_schedule() creates a WorkOrder with status='draft'."""
    tenant_id, vehicle_id = await _seed_tenant_and_vehicle(current_km=0)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    plan_id = await _create_plan(
        tenant_id,
        vehicle_id,
        next_due_at=yesterday,
        interval_days=90,
    )

    async with AsyncSessionLocal() as db:
        result = await evaluate_maintenance_schedule(db, tenant_id, actor_id=None)

    assert result["created"] >= 1

    async with AsyncSessionLocal() as db:
        wo = await db.scalar(
            select(WorkOrder).where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.plan_id == plan_id,
            )
        )
    assert wo is not None
    assert wo.status == "draft"


async def test_scheduler_skips_duplicate_work_order():
    """MAINT-01 D-04: If an open WorkOrder (status not in closed/cancelled) already exists
    for the same plan_id + vehicle_id, scheduler returns skip=True and creates no new WorkOrder."""
    tenant_id, vehicle_id = await _seed_tenant_and_vehicle(current_km=10001)
    plan_id = await _create_plan(
        tenant_id,
        vehicle_id,
        next_due_km=10000,
        interval_km=5000,
    )

    # First call — creates WorkOrder
    async with AsyncSessionLocal() as db:
        await evaluate_maintenance_schedule(db, tenant_id, actor_id=None)

    # Second call — should be a no-op (schedule already 'overdue', WorkOrder open)
    async with AsyncSessionLocal() as db:
        await evaluate_maintenance_schedule(db, tenant_id, actor_id=None)

    # Assert exactly 1 WorkOrder exists
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(WorkOrder).where(
                WorkOrder.tenant_id == tenant_id,
                WorkOrder.plan_id == plan_id,
            )
        )
        work_orders = rows.scalars().all()
    assert len(work_orders) == 1


async def test_next_cycle_schedule_created_after_trigger():
    """MAINT-01 D-03: After triggering, a new MaintenanceSchedule row is created with
    status='pending', due_km = trigger_km + interval_km, due_at = today + interval_days."""
    tenant_id, vehicle_id = await _seed_tenant_and_vehicle(current_km=10001)
    plan_id = await _create_plan(
        tenant_id,
        vehicle_id,
        next_due_km=10000,
        interval_km=5000,
    )

    async with AsyncSessionLocal() as db:
        await evaluate_maintenance_schedule(db, tenant_id, actor_id=None)

    async with AsyncSessionLocal() as db:
        pending_schedule = await db.scalar(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.tenant_id == tenant_id,
                MaintenanceSchedule.plan_id == plan_id,
                MaintenanceSchedule.status == "pending",
            )
        )

    assert pending_schedule is not None
    # due_km = vehicle.current_km (10001) + interval_km (5000) = 15001
    assert pending_schedule.due_km == 15001


async def test_odometer_event_enqueues_arq_task():
    """MAINT-01 D-01: When fuel log creation updates vehicle.current_km,
    an ARQ task 'check_vehicle_maintenance' is enqueued for that vehicle_id."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"ARQ Tenant {suffix}", slug=f"arq-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"ARQ-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            current_km=0,
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"ARQ Driver {suffix}",
            phone=f"25886{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)

    mock_pool = AsyncMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.aclose = AsyncMock()

    with patch("app.modules.fuel.service.create_pool", return_value=mock_pool):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                "/api/v1/fuel",
                headers={
                    "Authorization": "Bearer test-token",
                    "X-Tenant-Id": str(tenant.id),
                },
                json={
                    "vehicle_id": str(vehicle.id),
                    "driver_id": str(driver.id),
                    "fuel_date": datetime.now(UTC).isoformat(),
                    "station_name": "Test Station",
                    "fuel_type": "gasoleo",
                    "liters": 40.0,
                    "price_per_liter": 80.0,
                    "total_cost": 3200.0,
                    "km_at_refuel": 50000,
                },
            )
    assert resp.status_code in (200, 201), resp.text
    # Verify enqueue_job was called with check_vehicle_maintenance
    mock_pool.enqueue_job.assert_called_once()
    call_args = mock_pool.enqueue_job.call_args
    assert call_args[0][0] == "check_vehicle_maintenance"
    assert call_args[1]["vehicle_id"] == str(vehicle.id)
    assert call_args[1]["tenant_id"] == str(tenant.id)
    assert call_args[1]["current_km"] == 50000


async def test_imminent_maintenance_alerts():
    """MAINT-01 D-06: API endpoint returns vehicles where due_at <= today + 30 days
    OR due_km <= current_km + 500. Returns list with trigger_type field."""
    tenant_id, vehicle_id = await _seed_tenant_and_vehicle(current_km=1000)
    # Plan due in 15 days — within the 30-day window
    due_soon = datetime.now(UTC) + timedelta(days=15)
    await _create_plan(
        tenant_id,
        vehicle_id,
        next_due_at=due_soon,
        interval_days=90,
    )

    async with AsyncSessionLocal() as db:
        alerts = await get_imminent_maintenance_alerts(db, tenant_id, days_ahead=30, km_ahead=500)

    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["vehicle_id"] == str(vehicle_id)
    assert alert["trigger_type"] == "calendar"
    assert alert["next_due_at"] is not None
