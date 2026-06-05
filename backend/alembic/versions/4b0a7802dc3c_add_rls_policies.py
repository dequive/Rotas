"""add_rls_policies

D-16 through D-19: PostgreSQL Row Level Security for multitenant isolation.
Creates rotas_app (RLS enforced) and rotas_admin (BYPASSRLS) roles.
Enables RLS on all tenant-scoped tables.
Creates tenant_isolation policy using SET LOCAL app.tenant_id.

Revision ID: 4b0a7802dc3c
Revises: cb7d41a8a0f7
Create Date: 2026-06-05 23:22:28.061925+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "4b0a7802dc3c"
down_revision: str | None = "cb7d41a8a0f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# All tables that have a tenant_id column — verified against the actual DB schema.
# NOTE: "tenants" is EXCLUDED — root table, no tenant_id column.
# NOTE: "files" is EXCLUDED — has tenant_id but is accessed cross-tenant by the file
#        service for uploads; adding RLS here would break file retrieval by tenant workers.
#        Revisit when a dedicated files-per-tenant access pattern is established.
TENANT_SCOPED_TABLES = [
    "alerts",
    "audit_logs",
    "billing_documents",
    "billing_items",
    "cargo_manifests",
    "checklist_templates",
    "checklists",
    "contracts",
    "delivery_proofs",
    "dispatch_clearances",
    "driver_devices",
    "driver_sessions",
    "drivers",
    "fuel_logs",
    "fuel_movements",
    "fuel_purchases",
    "fuel_receipts",
    "fuel_stock_counts",
    "fuel_tanks",
    "idempotency_keys",
    "known_routes",
    "load_permits",
    "maintenance_parts_used",
    "maintenance_plans",
    "maintenance_requests",
    "maintenance_schedule",
    "operational_exceptions",
    "operational_waivers",
    "refresh_tokens",
    "spare_part_movements",
    "spare_parts_inventory",
    "sync_events",
    "tool_checkouts",
    "transport_documents",
    "trip_costs",
    "trip_execution_events",
    "trip_incidents",
    "trip_orders",
    "trip_stops",
    "trips",
    "users",
    "vehicle_refuels",
    "vehicles",
    "work_order_tasks",
    "work_orders",
    "workshop_tools",
]


def upgrade() -> None:
    # D-18: Create application roles (IF NOT EXISTS via DO block — idempotent).
    # rotas_app: subject to RLS enforcement (used by FastAPI application connection).
    # rotas_admin: BYPASSRLS (used by Alembic and ARQ worker for cross-tenant queries).
    op.execute(
        "DO $$ BEGIN CREATE ROLE rotas_app; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.execute(
        "DO $$ BEGIN CREATE ROLE rotas_admin BYPASSRLS; "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )

    # Grant rotas_app read/write on all existing tables and sequences.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rotas_app")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rotas_app")

    # D-16/D-19: Enable RLS and create tenant_isolation policy on every tenant-scoped table.
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # D-17: current_setting 'true' arg returns NULL if setting is absent (no error).
        # Cast tenant_id::text to match current_setting text return type (Pitfall 6).
        # When app.tenant_id is not set, current_setting returns NULL/'' so no rows match.
        # Use DO block for idempotency — CREATE POLICY has no IF NOT EXISTS in PG < 17.
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE tablename = '{table}' AND policyname = 'tenant_isolation'
                ) THEN
                    EXECUTE 'CREATE POLICY tenant_isolation ON {table}
                        USING (tenant_id::text = current_setting(''app.tenant_id'', true))';
                END IF;
            END $$
        """)


def downgrade() -> None:
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    # Note: roles are NOT dropped in downgrade to avoid breaking existing connections.
