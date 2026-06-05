"""MAINT-01: Preventive Maintenance Scheduler — test stubs.

These stubs document required behaviors. Remove skip markers as implementation completes.
"""
import pytest
from uuid import uuid4
from app.database import AsyncSessionLocal, engine, import_all_models

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


@pytest.mark.skip(reason="stub — implement in 04-02-PLAN")
async def test_scheduler_creates_work_order_on_km_trigger():
    """MAINT-01 D-02: When vehicle.current_km >= plan.next_due_km,
    evaluate_maintenance_schedule_all_tenants() creates a WorkOrder with status='draft'."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-02-PLAN")
async def test_scheduler_creates_work_order_on_date_trigger():
    """MAINT-01 D-02: When today >= plan.next_due_at,
    evaluate_maintenance_schedule_all_tenants() creates a WorkOrder with status='draft'."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-02-PLAN")
async def test_scheduler_skips_duplicate_work_order():
    """MAINT-01 D-04: If an open WorkOrder (status not in closed/cancelled) already exists
    for the same plan_id + vehicle_id, scheduler returns skip=True and creates no new WorkOrder."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-02-PLAN")
async def test_next_cycle_schedule_created_after_trigger():
    """MAINT-01 D-03: After triggering, a new MaintenanceSchedule row is created with
    status='pending', due_km = trigger_km + interval_km, due_at = today + interval_days."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-03-PLAN")
async def test_odometer_event_enqueues_arq_task():
    """MAINT-01 D-01: When fuel log creation updates vehicle.current_km,
    an ARQ task 'check_vehicle_maintenance' is enqueued for that vehicle_id."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-02-PLAN")
async def test_imminent_maintenance_alerts():
    """MAINT-01 D-06: API endpoint returns vehicles where due_at <= today + 30 days
    OR due_km <= current_km + 500. Returns list with trigger_type field."""
    pytest.fail("not implemented")
