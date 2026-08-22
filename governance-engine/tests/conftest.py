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
from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.auth import generate_api_key
from core.database import engine as app_engine
from core.database import install_rls_context, set_rls_tenant
from core.models import (
    CaseTransitionRule,
    TaxonomyCaseType,
    TaxonomyDomain,
    TaxonomyType,
    TaxonomyTypePromotion,
)
from core.models_auth import ApiKey, Tenant
from main import app

TEST_DB_URL = os.getenv(
    "GOVERNANCE_TEST_DATABASE_URL",
    "postgresql+asyncpg://governance_app:governance@localhost:55433/governance",
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
    # pytest-asyncio may use distinct loops for session and function fixtures.
    # NullPool prevents an asyncpg connection created on one loop being reused
    # by another while keeping the database itself session-scoped.
    eng = create_async_engine(TEST_DB_URL, echo=False, poolclass=NullPool)
    install_rls_context(eng)
    return eng


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables(engine):
    """Require the canonical Alembic schema; application tests never run DDL."""
    async with engine.connect() as conn:
        occurrences = await conn.scalar(text("SELECT to_regclass('public.occurrences')"))
        next_human_id = await conn.scalar(
            text("SELECT to_regprocedure('public.next_human_id(uuid,text,smallint)')")
        )
    if occurrences is None or next_human_id is None:
        raise RuntimeError(
            "Governance test database is not migrated; run `alembic upgrade head` first."
        )
    yield


@pytest_asyncio.fixture(autouse=True)
async def dispose_engine_between_tests(engine):
    yield
    await engine.dispose()
    await app_engine.dispose()


@pytest.fixture
def tenant_id() -> uuid.UUID:
    """Each test gets a fresh tenant UUID — RLS isolates all data."""
    return uuid.uuid4()


@pytest_asyncio.fixture
async def db(engine, tenant_id) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    # Canonical migrations enforce tenant foreign keys. Seed the auth-layer
    # tenant before inserting any tenant-scoped fixture rows.
    async with session_factory() as auth_session:
        if await auth_session.get(Tenant, tenant_id) is None:
            auth_session.add(
                Tenant(
                    id=tenant_id,
                    name="Test Tenant",
                    slug=f"test-{tenant_id.hex[:12]}",
                )
            )
            await auth_session.commit()

    set_rls_tenant(str(tenant_id))
    async with session_factory() as session:
        yield session
    set_rls_tenant(None)


@pytest_asyncio.fixture
async def taxonomy(db: AsyncSession, tenant_id: uuid.UUID) -> dict:
    """Bootstrap minimal taxonomy for a test tenant."""
    domain = TaxonomyDomain(tenant_id=tenant_id, code="test", name="Test Domain")
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
    db.add(
        TaxonomyTypePromotion(
            tenant_id=tenant_id,
            type_id=occ_type.id,
            case_type_id=incident_case_type.id,
            min_severity="alta",
        )
    )

    # Transition rules
    for from_s, to_s, req_fields, req_attach in [
        (None, "open", [], False),
        ("open", "in_analysis", [], False),
        ("in_analysis", "resolved", ["resolution_note"], False),
        ("open", "resolved", ["resolution_note"], False),
        ("resolved", "closed", [], False),
    ]:
        db.add(
            CaseTransitionRule(
                tenant_id=tenant_id,
                case_type_id=incident_case_type.id,
                from_status=from_s,
                to_status=to_s,
                required_fields=req_fields,
                required_attachments=req_attach,
            )
        )

    await db.commit()
    return {
        "domain": domain,
        "case_type": incident_case_type,
        "occ_type": occ_type,
    }


@pytest_asyncio.fixture
async def api_key_raw(tenant_id: uuid.UUID, engine) -> str:
    """Create an API key with broad scopes for the test tenant."""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create tenant row (no RLS on tenants table)
    set_rls_tenant(None)
    async with session_factory() as session:
        if await session.get(Tenant, tenant_id) is None:
            session.add(
                Tenant(
                    id=tenant_id,
                    name="Test Tenant",
                    slug=f"test-{tenant_id.hex[:12]}",
                )
            )
            await session.commit()

    full_key, prefix, key_hash = generate_api_key()

    set_rls_tenant(str(tenant_id))
    async with session_factory() as session:
        api_key = ApiKey(
            tenant_id=tenant_id,
            label="test-key",
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=[
                "occurrences:read",
                "occurrences:write",
                "cases:read",
                "cases:write",
                "admin:read",
                "admin:write",
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
