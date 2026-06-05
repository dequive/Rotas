"""Composite Index Audit — D-14 verification.

Queries pg_indexes to confirm all required composite indexes exist after migration.
"""
import pytest
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine, import_all_models

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


async def _index_exists(index_name: str) -> bool:
    """Check if a named index exists in the current database."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT 1 FROM pg_indexes "
                "WHERE indexname = :name"
            ),
            {"name": index_name},
        )
        return result.scalar() is not None


async def test_trips_composite_indexes_exist():
    """D-14: After migration, all 4 composite indexes on trips must exist."""
    assert await _index_exists("ix_trips_tenant_status"), \
        "Missing index: ix_trips_tenant_status"
    assert await _index_exists("ix_trips_tenant_driver_status"), \
        "Missing index: ix_trips_tenant_driver_status"
    assert await _index_exists("ix_trips_tenant_vehicle_status"), \
        "Missing index: ix_trips_tenant_vehicle_status"
    assert await _index_exists("ix_trips_tenant_actual_departure"), \
        "Missing index: ix_trips_tenant_actual_departure"


async def test_fuel_logs_composite_indexes_exist():
    """D-14: After migration, 2 composite indexes on fuel_logs must exist."""
    assert await _index_exists("ix_fuel_logs_tenant_vehicle"), \
        "Missing index: ix_fuel_logs_tenant_vehicle"
    assert await _index_exists("ix_fuel_logs_tenant_created_at"), \
        "Missing index: ix_fuel_logs_tenant_created_at"


async def test_maintenance_composite_indexes_exist():
    """D-14: After migration, maintenance + sync + stops indexes must exist."""
    assert await _index_exists("ix_maintenance_plans_tenant_status_km"), \
        "Missing index: ix_maintenance_plans_tenant_status_km"
    assert await _index_exists("ix_maintenance_schedule_tenant_status"), \
        "Missing index: ix_maintenance_schedule_tenant_status"
    assert await _index_exists("ix_sync_events_tenant_driver"), \
        "Missing index: ix_sync_events_tenant_driver"
    assert await _index_exists("ix_trip_stops_tenant_trip"), \
        "Missing index: ix_trip_stops_tenant_trip"
