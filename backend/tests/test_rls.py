"""PostgreSQL RLS — test stubs (D-16 through D-19).

The existing test_cross_tenant_isolation.py covers code-level isolation.
These stubs verify DB-level RLS enforcement after the Alembic RLS migration.
"""
import pytest
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine, import_all_models

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


@pytest.mark.skip(reason="stub — implement in 04-08-PLAN after RLS migration")
async def test_rls_blocks_cross_tenant_trip_access():
    """D-17/D-19: Connecting as rotas_app with app.tenant_id=tenant_A cannot read
    trips belonging to tenant_B. Query returns empty result set, not an error."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-08-PLAN after RLS migration")
async def test_rls_set_local_scoped_to_transaction():
    """D-17 Pitfall: SET LOCAL app.tenant_id is scoped to transaction.
    A second transaction in the same connection with no tenant_id set returns empty results."""
    pytest.fail("not implemented")


@pytest.mark.skip(reason="stub — implement in 04-08-PLAN after RLS migration")
async def test_rls_tenant_isolation_policy_exists():
    """D-19: pg_policies view shows 'tenant_isolation' policy on 'trips' table."""
    pytest.fail("not implemented")
