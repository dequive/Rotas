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
