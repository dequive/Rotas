"""restore indexes and tenant_roles RLS

Revision ID: b4f2c9d8a1e6
Revises: 934b7fae14fc
Create Date: 2026-06-20 12:10:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4f2c9d8a1e6"
down_revision: str | None = "934b7fae14fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_trips_tenant_status ON trips (tenant_id, status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trips_tenant_driver_status "
        "ON trips (tenant_id, driver_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trips_tenant_vehicle_status "
        "ON trips (tenant_id, vehicle_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trips_tenant_actual_departure "
        "ON trips (tenant_id, actual_departure)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fuel_logs_tenant_vehicle "
        "ON fuel_logs (tenant_id, vehicle_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_fuel_logs_tenant_created_at "
        "ON fuel_logs (tenant_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_maintenance_plans_tenant_status_km "
        "ON maintenance_plans (tenant_id, status, next_due_km)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_maintenance_schedule_tenant_status "
        "ON maintenance_schedule (tenant_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sync_events_tenant_driver "
        "ON sync_events (tenant_id, driver_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trip_stops_tenant_trip ON trip_stops (tenant_id, trip_id)"
    )

    op.execute("ALTER TABLE tenant_roles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_roles FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS rls_tenant_roles ON tenant_roles")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'tenant_roles'
                  AND policyname = 'tenant_isolation'
            ) THEN
                CREATE POLICY tenant_isolation ON tenant_roles
                USING (tenant_id::text = current_setting('app.tenant_id', true));
            END IF;
        END $$;
        """
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_roles TO rotas_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_roles")
    op.execute(
        "CREATE POLICY rls_tenant_roles ON tenant_roles "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )

    op.execute("DROP INDEX IF EXISTS ix_trip_stops_tenant_trip")
    op.execute("DROP INDEX IF EXISTS ix_sync_events_tenant_driver")
    op.execute("DROP INDEX IF EXISTS ix_maintenance_schedule_tenant_status")
    op.execute("DROP INDEX IF EXISTS ix_maintenance_plans_tenant_status_km")
    op.execute("DROP INDEX IF EXISTS ix_fuel_logs_tenant_created_at")
    op.execute("DROP INDEX IF EXISTS ix_fuel_logs_tenant_vehicle")
    op.execute("DROP INDEX IF EXISTS ix_trips_tenant_actual_departure")
    op.execute("DROP INDEX IF EXISTS ix_trips_tenant_vehicle_status")
    op.execute("DROP INDEX IF EXISTS ix_trips_tenant_driver_status")
    op.execute("DROP INDEX IF EXISTS ix_trips_tenant_status")
