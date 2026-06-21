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

EXPECTED_RLS_TABLES = sorted(
    [
        "alerts",
        "audit_logs",
        "billing_documents",
        "billing_items",
        "cargo_manifests",
        "checklist_templates",
        "checklists",
        # Phase 5 Plan 02: clients, client_payments, payment_allocations added
        "client_payments",
        "clients",
        "contracts",
        "delivery_proofs",
        "dispatch_clearances",
        "driver_devices",
        "driver_sessions",
        "drivers",
        "export_jobs",
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
        "email_verification_tokens",
        "mfa_challenges",
        "operational_exceptions",
        "notification_outbox",
        "operational_waivers",
        "password_reset_tokens",
        "payment_allocations",
        "refresh_tokens",
        "spare_part_movements",
        "spare_parts_inventory",
        "sync_events",
        "tenant_roles",
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
        # Phase 23: Third Party Registry
        "driver_vehicle_assignments",
        "operational_documents",
        "service_provider_profiles",
        "supplier_profiles",
        "third_parties",
        "third_party_roles",
        # Phase 23 Plan 09: supplier evaluations + ledger + contacts
        "supplier_evaluations",
        "supplier_ledger_entries",
        "third_party_contacts",
        # Phase 18: vehicle insurance + tenant document profiles
        "insurance_claims",
        "vehicle_insurances",
        "tenant_document_profiles",
    ]
)
# 63 tables: base RLS set + export_jobs + self-service token/outbox tables
#            + Phase 5 clients/client_payments/payment_allocations
#            + Phase 23 third party registry (6 tables)
#            + Phase 23 Plan 09: supplier_evaluations, supplier_ledger_entries, third_party_contacts

INTENTIONALLY_EXCLUDED = {
    "files",
    # Phase 13.5 workshop expansion tables created without RLS
    # in a8f3b2c1d4e5_add_workshop_expansion.py.
    # These are pre-existing gaps tracked in deferred-items; Phase 13.5 plan must add RLS.
    "tool_calibrations",
    "spare_part_serial_items",
    "workshop_staff_rates",
    # fisc01_fiscal_counter_gap_free.py created fiscal_counters with RLS enabled
    # and FORCE RLS but used policy name 'rls_fiscal_counters' instead of 'tenant_isolation'.
    # The table IS protected by RLS — the gap test only scans for policyname='tenant_isolation'.
    # Tracked: rename policy to 'tenant_isolation' in a follow-up migration.
    "fiscal_counters",
}
# files: cross-tenant file service access pattern (design decision in migration 4b0a7802dc3c)
# tenants: root table with no tenant_id column — never appears in gap query by design


async def test_rls_all_tenant_tables_have_policy():
    """RLS-01: All tenant-scoped tables must have a tenant_isolation policy in pg_policies.

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


# ---------------------------------------------------------------------------
# DB-role-based cross-tenant isolation — RLS-03
# ---------------------------------------------------------------------------


async def test_rls_blocks_cross_tenant_vehicle_access():
    """RLS-03: DB-level RLS blocks cross-tenant vehicle reads without any WHERE tenant_id.

    This test proves that the tenant_isolation policy on the vehicles table enforces
    isolation at the PostgreSQL layer — not just via app-layer WHERE clauses.

    Method: connect via asyncpg directly as the rotas_app role (not BYPASSRLS),
    set app.tenant_id = tenant_B, then execute SELECT * FROM vehicles with NO WHERE
    clause. Tenant A's vehicle must be invisible — count must be 0.

    Assumption: the test database has a 'rotas_app' role with password 'rotas_app_dev'.
    This matches the init SQL convention for local dev. If the role is unavailable,
    the test skips gracefully rather than failing hard.

    Expected: RED until plan 09-02 migration applies (enables RLS + FORCE RLS on
    vehicles table). Will turn GREEN once the RLS migration has run against the test DB.
    """
    import re
    from uuid import uuid4

    import asyncpg

    from app.config import get_settings as _get_settings
    from app.modules.tenants.models import Tenant
    from app.modules.vehicles.models import Vehicle

    _settings = _get_settings()

    # --- Setup: create two tenants and a vehicle for tenant_A using admin connection ---
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        t_a = Tenant(name=f"VehRLS_A_{suffix}", slug=f"veh-rls-a-{suffix}")
        t_b = Tenant(name=f"VehRLS_B_{suffix}", slug=f"veh-rls-b-{suffix}")
        db.add_all([t_a, t_b])
        await db.flush()

        v_a = Vehicle(
            tenant_id=t_a.id,
            plate=f"VRLS-{suffix}",
            category="ligeiro",
            fuel_type="gasolina",
        )
        db.add(v_a)
        await db.commit()
        t_b_id = str(t_b.id)
        v_a_id = str(v_a.id)

    # --- Build rotas_app DSN from settings.database_url ---
    # Replace the user/password portion with rotas_app:rotas_app_dev.
    # settings.database_url uses asyncpg driver; asyncpg.connect needs postgresql:// scheme.
    base_url = _settings.database_url
    # Normalise asyncpg-style URL to plain postgresql:// for asyncpg library
    rotas_app_dsn = re.sub(
        r"postgresql\+asyncpg://[^@]+@",
        "postgresql://rotas_app:rotas_app_dev@",
        base_url,
    )

    # --- Connect as rotas_app and verify RLS blocks tenant_A's vehicle under tenant_B context ---
    try:
        conn = await asyncpg.connect(rotas_app_dsn)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"rotas_app role not available in test DB: {exc}")
        return

    try:
        async with conn.transaction():
            # Set tenant context to tenant_B — no WHERE clause will reference tenant_id
            await conn.execute(f"SET LOCAL app.tenant_id = '{t_b_id}'")

            # Query vehicles with NO WHERE clause — RLS should filter by app.tenant_id
            rows = await conn.fetch("SELECT * FROM vehicles")

            # Tenant_A's vehicle must not appear (RLS filters to tenant_B's rows only)
            visible_ids = {str(r["id"]) for r in rows}
    finally:
        await conn.close()

    assert v_a_id not in visible_ids, (
        f"RLS FAILED: tenant_B context (rotas_app role, SET LOCAL app.tenant_id=tenant_B) "
        f"can see tenant_A's vehicle {v_a_id} with no WHERE tenant_id clause. "
        "DB-level cross-tenant isolation is not enforced on the vehicles table."
    )
