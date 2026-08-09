"""
Test configuration.

Isolation strategy: each test function gets a unique tenant_id UUID.
RLS policies naturally isolate all data — no table truncation needed,
which would conflict with append-only triggers.

The session-scoped engine creates tables + SQL functions once per test run.
"""
import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.auth import generate_api_key
from core.database import Base, GovernanceSession, set_rls_tenant
from core.models import (
    CaseTransitionRule,
    TaxonomyCaseType,
    TaxonomyDomain,
    TaxonomyType,
    TaxonomyTypePromotion,
)
from core.models_auth import ApiKey
from main import app

TEST_DB_URL = os.getenv("GOVERNANCE_TEST_DATABASE_URL")
if not TEST_DB_URL:
    raise RuntimeError(
        "GOVERNANCE_TEST_DATABASE_URL is required and must target a disposable test database."
    )

_NEXT_HUMAN_ID_SQL = """
CREATE OR REPLACE FUNCTION next_human_id(
    p_tenant_id UUID,
    p_prefix    TEXT,
    p_year      SMALLINT
) RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE
    v_seq INTEGER;
BEGIN
    INSERT INTO tenant_sequences (tenant_id, prefix, year, last_seq)
    VALUES (p_tenant_id, p_prefix, p_year, 1)
    ON CONFLICT (tenant_id, prefix, year)
    DO UPDATE SET last_seq = tenant_sequences.last_seq + 1
    RETURNING last_seq INTO v_seq;

    RETURN p_prefix || '-' || p_year::TEXT || '-' || LPAD(v_seq::TEXT, 6, '0');
END;
$$;
"""

_IMMUTABILITY_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION raise_immutable_record()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'This table is append-only — reverse with a new record.';
END;
$$;
"""

_TRIGGER_OCCURRENCES_SQL = """
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_occurrences_immutable'
    ) THEN
        CREATE TRIGGER trg_occurrences_immutable
            BEFORE UPDATE OR DELETE ON occurrences
            FOR EACH ROW EXECUTE FUNCTION raise_immutable_record();
    END IF;
END $$;
"""

_TRIGGER_TRANSITIONS_SQL = """
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_case_transitions_immutable'
    ) THEN
        CREATE TRIGGER trg_case_transitions_immutable
            BEFORE UPDATE OR DELETE ON case_transitions
            FOR EACH ROW EXECUTE FUNCTION raise_immutable_record();
    END IF;
END $$;
"""


@pytest.fixture(scope="session")
def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    return eng


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(_NEXT_HUMAN_ID_SQL))
        await conn.execute(text(_IMMUTABILITY_FUNCTION_SQL))
        await conn.execute(text(_TRIGGER_OCCURRENCES_SQL))
        await conn.execute(text(_TRIGGER_TRANSITIONS_SQL))
    yield


@pytest_asyncio.fixture(autouse=True)
async def dispose_engine_between_tests(engine):
    yield
    await engine.dispose()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    """Each test gets a fresh tenant UUID — RLS isolates all data."""
    return uuid.uuid4()


@pytest_asyncio.fixture
async def tenant_row(engine, tenant_id: uuid.UUID) -> None:
    """Provision the tenant required by the migrated production schema."""
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        sync_session_class=GovernanceSession,
    )
    set_rls_tenant(None)
    async with session_factory() as session:
        await session.execute(
            text(
                """
                INSERT INTO tenants (id, name, slug)
                VALUES (:tenant_id, :name, :slug)
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "tenant_id": tenant_id,
                "name": "Test Tenant",
                "slug": f"test-{tenant_id.hex[:8]}",
            },
        )
        await session.commit()


@pytest_asyncio.fixture
async def db(engine, tenant_id, tenant_row) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        sync_session_class=GovernanceSession,
    )
    set_rls_tenant(str(tenant_id))
    async with session_factory() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        yield session
    set_rls_tenant(None)


@pytest_asyncio.fixture
async def taxonomy(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Bootstrap minimal taxonomy for a test tenant."""
    domain = TaxonomyDomain(
        tenant_id=tenant_id, code="test", name="Test Domain"
    )
    db.add(domain)
    await db.flush()

    incident_case_type = TaxonomyCaseType(
        tenant_id=tenant_id,
        domain_id=domain.id,
        code="test.incident",
        name="Test Incident",
        initial_status="open",
        sla_hours=48,
    )
    db.add(incident_case_type)
    await db.flush()

    occ_type = TaxonomyType(
        tenant_id=tenant_id,
        domain_id=domain.id,
        code="test.breakdown",
        name="Test Breakdown",
    )
    db.add(occ_type)
    await db.flush()

    # Promotion: test.breakdown + alta → test.incident
    db.add(TaxonomyTypePromotion(
        tenant_id=tenant_id,
        type_id=occ_type.id,
        case_type_id=incident_case_type.id,
        min_severity="alta",
    ))

    # Transition rules
    for from_s, to_s, req_fields, req_attach in [
        (None,           "open",        [],                    False),
        ("open",         "in_analysis", [],                    False),
        ("in_analysis",  "resolved",    ["resolution_note"],   False),
        ("open",         "resolved",    ["resolution_note"],   False),
        ("resolved",     "closed",      [],                    False),
    ]:
        db.add(CaseTransitionRule(
            tenant_id=tenant_id,
            case_type_id=incident_case_type.id,
            from_status=from_s,
            to_status=to_s,
            required_fields=req_fields,
            required_attachments=req_attach,
        ))

    await db.commit()
    return {
        "domain": domain,
        "case_type": incident_case_type,
        "occ_type": occ_type,
    }


@pytest_asyncio.fixture
async def api_key_raw(tenant_id: uuid.UUID, engine, tenant_row) -> str:
    """Create an API key with broad scopes for the test tenant."""
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
        sync_session_class=GovernanceSession,
    )

    full_key, prefix, key_hash = generate_api_key()

    set_rls_tenant(str(tenant_id))
    async with session_factory() as session:
        api_key = ApiKey(
            tenant_id=tenant_id,
            label="test-key",
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[
                "occurrences:read", "occurrences:write",
                "cases:read", "cases:write",
                "admin:read", "admin:write",
                "adapter:rotas",
            ],
        )
        session.add(api_key)
        await session.commit()

    set_rls_tenant(None)
    return full_key


@pytest_asyncio.fixture
async def client(api_key_raw: str) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-API-Key": api_key_raw},
    ) as c:
        yield c
