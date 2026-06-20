"""restore_composite_indexes_after_drift_fix

Revision ID: restore_composite_indexes
Revises: tp_merge_wave2
Create Date: 2026-06-20 08:18:27.542773+02:00

D-14: The acfa8ae500c0 drift-fix migration dropped 10 composite indexes that
were created by b19ec4f5d607. This migration restores them with IF NOT EXISTS
so it is idempotent and safe to re-run.
Requires AUTOCOMMIT / transaction_per_migration=False (configured in env.py).
"""

from alembic import op

revision: str = 'restore_composite_indexes'
down_revision: str | None = 'tp_merge_wave2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # trips — 4 composite indexes
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

    # fuel_logs — 2 composite indexes
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_fuel_logs_tenant_vehicle ON fuel_logs (tenant_id, vehicle_id)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_fuel_logs_tenant_created_at ON fuel_logs (tenant_id, created_at)"
    )

    # maintenance_plans + maintenance_schedule — 2 composite indexes
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

    # sync_events — 1 composite index
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_sync_events_tenant_driver ON sync_events (tenant_id, driver_id)"
    )

    # trip_stops — 1 composite index
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
