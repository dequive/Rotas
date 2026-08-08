"""Restore database-managed composite indexes on historical databases.

Revision ID: rec11
Revises: rec10
Create Date: 2026-07-26 01:10:00+02:00

The indexes are intentionally excluded from ORM autogenerate because they are
database-managed. A historical database can therefore be stamped at head while
missing them. Reasserting the complete set with ``IF NOT EXISTS`` is safe on
canonical and legacy databases.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec11"
down_revision: str | None = "rec10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDEXES = {
    "ix_trips_tenant_status": "trips (tenant_id, status)",
    "ix_trips_tenant_driver_status": "trips (tenant_id, driver_id, status)",
    "ix_trips_tenant_vehicle_status": "trips (tenant_id, vehicle_id, status)",
    "ix_trips_tenant_actual_departure": "trips (tenant_id, actual_departure)",
    "ix_fuel_logs_tenant_vehicle": "fuel_logs (tenant_id, vehicle_id)",
    "ix_fuel_logs_tenant_created_at": "fuel_logs (tenant_id, created_at)",
    "ix_maintenance_plans_tenant_status_km": (
        "maintenance_plans (tenant_id, status, next_due_km)"
    ),
    "ix_maintenance_schedule_tenant_status": (
        "maintenance_schedule (tenant_id, status)"
    ),
    "ix_sync_events_tenant_driver": "sync_events (tenant_id, driver_id)",
    "ix_trip_stops_tenant_trip": "trip_stops (tenant_id, trip_id)",
}


def upgrade() -> None:
    for index_name, index_target in _INDEXES.items():
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            f"{index_name} ON {index_target}"
        )


def downgrade() -> None:
    # These indexes may predate this reconciliation revision. Removing them on
    # downgrade would degrade canonical databases, so rollback is non-destructive.
    pass
