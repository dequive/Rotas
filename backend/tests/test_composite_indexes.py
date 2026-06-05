"""Composite Index Audit — test stubs (D-14).

Verifies that all required composite indexes exist after migration.
"""
import pytest
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine, import_all_models

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


@pytest.mark.skip(reason="stub — implement in 04-06-PLAN after migration")
async def test_trips_composite_indexes_exist():
    """D-14: After Alembic migration, the following indexes must exist on 'trips':
    ix_trips_tenant_status (tenant_id, status)
    ix_trips_tenant_driver_status (tenant_id, driver_id, status)
    ix_trips_tenant_vehicle_status (tenant_id, vehicle_id, status)
    ix_trips_tenant_actual_departure (tenant_id, actual_departure)
    """
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-06-PLAN after migration")
async def test_fuel_logs_composite_indexes_exist():
    """D-14: ix_fuel_logs_tenant_vehicle (tenant_id, vehicle_id)
    ix_fuel_logs_tenant_created_at (tenant_id, created_at) must exist."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-06-PLAN after migration")
async def test_maintenance_composite_indexes_exist():
    """D-14: ix_maintenance_plans_tenant_status_km (tenant_id, status, next_due_km)
    ix_maintenance_schedule_tenant_status (tenant_id, status) must exist."""
    pytest.fail("not implemented")
