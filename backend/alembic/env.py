from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import get_settings
from app.database import Base, import_all_models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()

# ALEMBIC_DATABASE_URL: uses rotas_admin role (BYPASSRLS) so Alembic can run migrations
# after RLS is enabled on all tenant tables. Falls back to DATABASE_URL in local dev
# where RLS may not be active. (Pitfall 1 from RESEARCH.md)
_alembic_url = settings.resolved_alembic_database_url.replace("+asyncpg", "+psycopg")

import_all_models()
target_metadata = Base.metadata

# Performance indexes created deliberately by historical migrations and managed
# at database level. They must be preserved even when not repeated in ORM models.
_DATABASE_MANAGED_INDEXES = {
    "ix_fuel_logs_tenant_created_at",
    "ix_fuel_logs_tenant_vehicle",
    "ix_item_categories_tenant_id",
    "ix_items_category_id",
    "ix_items_tenant_id",
    "ix_maintenance_plans_tenant_status_km",
    "ix_maintenance_schedule_tenant_status",
    "ix_platform_audit_logs_actor_id",
    "ix_platform_audit_logs_target_tenant_id",
    "ix_platform_users_email",
    "ix_stock_movements_item_id",
    "ix_stock_movements_tenant_id",
    "ix_stock_movements_warehouse_id",
    "ix_sle_currency",
    "ix_sync_events_tenant_driver",
    "ix_trip_stops_tenant_trip",
    "ix_trips_tenant_actual_departure",
    "ix_trips_tenant_driver_status",
    "ix_trips_tenant_status",
    "ix_trips_tenant_vehicle_status",
    "ix_warehouses_tenant_id",
}


def run_migrations_offline() -> None:
    context.configure(
        url=_alembic_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "index" and reflected and compare_to is None and name in _DATABASE_MANAGED_INDEXES:
        return False
    if type_ == "table" and name:
        if name.startswith("gps_positions") or name in [
            "vehicle_last_position",
            "tracking_tokens",
            "gps_devices",
        ]:
            return False
    return True


def run_migrations_online() -> None:
    connectable = create_engine(_alembic_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # Set autocommit so that CREATE INDEX CONCURRENTLY can run outside a transaction.
        # transaction_per_migration=False tells Alembic not to wrap each migration in
        # BEGIN/COMMIT, but the connection itself must also be in autocommit mode.
        connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            transaction_per_migration=False,  # Required for CREATE INDEX CONCURRENTLY
            include_object=include_object,
        )

        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
