"""PostgreSQL RLS — tests (D-16 through D-19).

The existing test_cross_tenant_isolation.py covers code-level isolation.
These tests verify DB-level RLS enforcement after the Alembic RLS migration.
"""

import pytest
from sqlalchemy import select, text

from app.database import AsyncSessionLocal, engine, import_all_models, set_rls_tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


async def test_rls_tenant_isolation_policy_exists():
    """D-19: pg_policies shows tenant_isolation policy on trips table."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "SELECT 1 FROM pg_policies "
                "WHERE tablename = 'trips' AND policyname = 'tenant_isolation'"
            )
        )
        row = result.scalar()
    assert row is not None, "RLS policy 'tenant_isolation' not found on trips table"


async def test_rls_set_local_scoped_to_transaction():
    """D-17: SET LOCAL app.tenant_id is transaction-scoped, not session-scoped."""
    from uuid import uuid4

    tid = str(uuid4())
    async with AsyncSessionLocal() as db:
        async with db.begin():
            await db.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
            result = await db.execute(text("SELECT current_setting('app.tenant_id', true)"))
            in_tx = result.scalar()
        # After transaction ends, SET LOCAL setting should be cleared
        result2 = await db.execute(text("SELECT current_setting('app.tenant_id', true)"))
        after_tx = result2.scalar()
    assert in_tx == tid, f"Expected {tid} inside transaction, got {in_tx}"
    # After transaction, SET LOCAL should be gone (returns empty string or None)
    assert after_tx != tid, "SET LOCAL leaked past transaction boundary — pool safety risk"


async def test_rls_blocks_cross_tenant_trip_access():
    """D-19: With app.tenant_id=A, queries on trips table cannot see tenant B's rows."""
    from uuid import uuid4

    from app.modules.drivers.models import Driver
    from app.modules.tenants.models import Tenant
    from app.modules.trips.models import Trip
    from app.modules.vehicles.models import Vehicle

    # Create two tenants and a trip for tenant_b
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        # Create tenants — no RLS on tenants table (it is the root table)
        t_a = Tenant(name=f"RLS_A_{suffix}", slug=f"rls-a-{suffix}")
        t_b = Tenant(name=f"RLS_B_{suffix}", slug=f"rls-b-{suffix}")
        db.add_all([t_a, t_b])
        await db.flush()

        # Create minimal vehicle + driver for tenant_b to seed a trip
        v_b = Vehicle(
            tenant_id=t_b.id,
            plate=f"RLS-B-{suffix}",
            category="ligeiro",
            fuel_type="gasolina",
        )
        d_b = Driver(
            tenant_id=t_b.id,
            full_name=f"Driver B {suffix}",
            phone=f"25881{suffix}",
        )
        db.add_all([v_b, d_b])
        await db.flush()

        trip_b = Trip(
            tenant_id=t_b.id,
            vehicle_id=v_b.id,
            driver_id=d_b.id,
            origin="Maputo",
            destination="Beira",
            status="planned",
        )
        db.add(trip_b)
        await db.commit()
        t_a_id = t_a.id
        trip_b_id = trip_b.id

    # Now query as tenant_A via the rotas_app role (not BYPASSRLS) — should NOT see tenant_B's trip.
    # The default 'rotas' superuser has BYPASSRLS=true, so we must SET ROLE rotas_app to activate
    # the tenant_isolation policy within this transaction.
    set_rls_tenant(str(t_a_id))
    try:
        async with AsyncSessionLocal() as db:
            # Switch to rotas_app role for this transaction so RLS is enforced
            await db.execute(text("SET LOCAL ROLE rotas_app"))
            result = await db.execute(select(Trip).where(Trip.id == trip_b_id))
            row = result.scalar()
    finally:
        set_rls_tenant(None)

    assert row is None, (
        f"RLS FAILED: tenant A (via rotas_app role) can see tenant B's trip {trip_b_id}. "
        "Cross-tenant data leak detected."
    )


# ---------------------------------------------------------------------------
# RLS completeness gate — RLS-01
# ---------------------------------------------------------------------------

EXPECTED_RLS_TABLES = sorted([
    "alerts", "audit_logs", "billing_documents", "billing_items",
    "cargo_manifests", "checklist_templates", "checklists", "contracts",
    "delivery_proofs", "dispatch_clearances", "driver_devices", "driver_sessions",
    "drivers", "export_jobs", "fuel_logs", "fuel_movements", "fuel_purchases",
    "fuel_receipts", "fuel_stock_counts", "fuel_tanks", "idempotency_keys",
    "known_routes", "load_permits", "maintenance_parts_used", "maintenance_plans",
    "maintenance_requests", "maintenance_schedule", "operational_exceptions",
    "operational_waivers", "refresh_tokens", "spare_part_movements",
    "spare_parts_inventory", "sync_events", "tool_checkouts",
    "transport_documents", "trip_costs", "trip_execution_events",
    "trip_incidents", "trip_orders", "trip_stops", "trips", "users",
    "vehicle_refuels", "vehicles", "work_order_tasks", "work_orders",
    "workshop_tools",
])
# 47 tables: 46 from migration 4b0a7802dc3c_add_rls_policies + export_jobs from gap-closure migration (plan 09-02)

INTENTIONALLY_EXCLUDED = {"tenants", "files"}
# tenants: root table — no tenant_id column; RLS would break registration and cross-tenant admin queries
# files: cross-tenant file service access pattern (design decision in migration 4b0a7802dc3c)


async def test_rls_all_tenant_tables_have_policy():
    """RLS-01: All 47 tenant-scoped tables must have a tenant_isolation policy in pg_policies.

    This test is intentionally RED until plan 09-02 applies the gap-closure migration that
    adds the RLS policy to export_jobs. The failure message will clearly show the gap.
    """
    async with AsyncSessionLocal() as db:
        # 1. Collect all tables that currently have the tenant_isolation policy
        result = await db.execute(
            text(
                "SELECT tablename FROM pg_policies "
                "WHERE policyname = 'tenant_isolation' "
                "ORDER BY tablename"
            )
        )
        actual_policy_set = {row[0] for row in result.fetchall()}

        # 2. Assert the exact match against the expected 47-table list
        expected_set = set(EXPECTED_RLS_TABLES)
        missing = expected_set - actual_policy_set
        extra = actual_policy_set - expected_set
        assert actual_policy_set == expected_set, (
            f"RLS policy coverage mismatch.\n"
            f"  Missing policies (tables that need RLS but don't have it): {sorted(missing)}\n"
            f"  Unexpected policies (not in expected list): {sorted(extra)}"
        )

        # 3. Cross-check: tables with tenant_id column that lack a policy (gap detection)
        gap_result = await db.execute(
            text(
                "SELECT c.table_name "
                "FROM information_schema.columns c "
                "WHERE c.column_name = 'tenant_id' AND c.table_schema = 'public' "
                "EXCEPT "
                "SELECT p.tablename "
                "FROM pg_policies p "
                "WHERE p.policyname = 'tenant_isolation'"
            )
        )
        gap_set = {row[0] for row in gap_result.fetchall()}

        assert gap_set == INTENTIONALLY_EXCLUDED, (
            f"Tables with tenant_id but no RLS policy "
            f"(expected only {{tenants, files}}): {gap_set - INTENTIONALLY_EXCLUDED}"
        )
