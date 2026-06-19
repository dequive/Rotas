"""add_composite_indexes

Revision ID: b19ec4f5d607
Revises: a1b2c3d4e5f6
Create Date: 2026-06-05 20:30:00.000000

D-14: Composite indexes for high-traffic tables.
tenant_id is the leading column in all indexes.
Uses CREATE INDEX CONCURRENTLY to avoid table locks.
Requires transaction_per_migration=False in alembic/env.py.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b19ec4f5d607"
down_revision: str | None = "7b6acddf4ab0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # trips table — 4 indexes
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trips_tenant_status ON trips (tenant_id, status)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trips_tenant_driver_status ON trips (tenant_id, driver_id, status)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trips_tenant_vehicle_status ON trips (tenant_id, vehicle_id, status)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trips_tenant_actual_departure ON trips (tenant_id, actual_departure)"
    )

    # fuel_logs table — 2 indexes
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_fuel_logs_tenant_vehicle ON fuel_logs (tenant_id, vehicle_id)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_fuel_logs_tenant_created_at ON fuel_logs (tenant_id, created_at)"
    )

    # maintenance_plans + maintenance_schedule — 2 indexes
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_maintenance_plans_tenant_status_km "
        "ON maintenance_plans (tenant_id, status, next_due_km)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_maintenance_schedule_tenant_status "
        "ON maintenance_schedule (tenant_id, status)"
    )

    # sync_events — 1 index
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_sync_events_tenant_driver ON sync_events (tenant_id, driver_id)"
    )

    # trip_stops — 1 index
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trip_stops_tenant_trip ON trip_stops (tenant_id, trip_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_trips_tenant_status")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_trips_tenant_driver_status")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_trips_tenant_vehicle_status")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_trips_tenant_actual_departure")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_fuel_logs_tenant_vehicle")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_fuel_logs_tenant_created_at")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_maintenance_plans_tenant_status_km")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_maintenance_schedule_tenant_status")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_sync_events_tenant_driver")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_trip_stops_tenant_trip")
