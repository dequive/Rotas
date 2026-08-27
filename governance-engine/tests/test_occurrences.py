"""Occurrence service tests — numbering, idempotency, auto-promotion, estorno."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Case, Occurrence
from core.models_auth import Tenant
from core.services.occurrences import OccurrenceService


def _svc(db, tenant_id) -> OccurrenceService:
    return OccurrenceService(db, tenant_id, uuid.uuid4())


async def _create(db, tenant_id, taxonomy, **kwargs) -> tuple:
    svc = _svc(db, tenant_id)
    result = await svc.create(
        type_code=taxonomy["occ_type"].code,
        severity=kwargs.get("severity", "alta"),
        title=kwargs.get("title", "Test occurrence"),
        description=None,
        occurred_at=datetime.now(UTC),
        links=[],
        idempotency_key=kwargs.get("idempotency_key", str(uuid.uuid4())),
    )
    await db.commit()
    return result


async def test_occurrence_creates_with_numero(db: AsyncSession, tenant_id, taxonomy):
    result = await _create(db, tenant_id, taxonomy)
    assert result.numero.startswith("EVT-")
    occ = await db.get(Occurrence, result.occurrence_id)
    assert occ is not None
    assert occ.tenant_id == tenant_id


async def test_numero_sequential(db: AsyncSession, tenant_id, taxonomy):
    r1 = await _create(db, tenant_id, taxonomy)
    r2 = await _create(db, tenant_id, taxonomy)
    seq1 = int(r1.numero.split("-")[-1])
    seq2 = int(r2.numero.split("-")[-1])
    assert seq2 == seq1 + 1


async def test_sequences_isolated_by_tenant(db: AsyncSession, tenant_id, taxonomy, engine):
    """Two tenants sharing the same type code get independent sequences."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from core.database import set_rls_tenant

    other_tenant = uuid.uuid4()

    r1 = await _create(db, tenant_id, taxonomy)

    # Bootstrap taxonomy for other_tenant inline
    from core.models import CaseTransitionRule, TaxonomyCaseType, TaxonomyDomain, TaxonomyType

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    set_rls_tenant(None)
    async with session_factory() as auth_db:
        auth_db.add(
            Tenant(
                id=other_tenant,
                name="Other Tenant",
                slug=f"other-{other_tenant.hex[:12]}",
            )
        )
        await auth_db.commit()

    set_rls_tenant(str(other_tenant))
    async with session_factory() as other_db:
        dom = TaxonomyDomain(tenant_id=other_tenant, code="test", name="Other Domain")
        other_db.add(dom)
        await other_db.flush()
        ct = TaxonomyCaseType(
            tenant_id=other_tenant,
            domain_id=dom.id,
            code="test.incident",
            name="X",
            initial_status="open",
        )
        other_db.add(ct)
        await other_db.flush()
        ot = TaxonomyType(tenant_id=other_tenant, domain_id=dom.id, code="test.breakdown", name="X")
        other_db.add(ot)
        await other_db.flush()
        other_db.add(
            CaseTransitionRule(
                tenant_id=other_tenant,
                case_type_id=ct.id,
                from_status=None,
                to_status="open",
                required_fields=[],
                required_attachments=False,
            )
        )
        await other_db.commit()

        other_svc = OccurrenceService(other_db, other_tenant, uuid.uuid4())
        r2 = await other_svc.create(
            type_code="test.breakdown",
            severity="alta",
            title="Other",
            description=None,
            occurred_at=datetime.now(UTC),
            links=[],
            idempotency_key=str(uuid.uuid4()),
        )
        await other_db.commit()

    set_rls_tenant(None)
    # Both get EVT-YYYY-000001 — sequences are per-tenant
    assert r1.numero.startswith("EVT-")
    assert r2.numero.endswith("-000001")
    assert r1.occurrence_id != r2.occurrence_id


async def test_idempotent_create_returns_same_occurrence(db: AsyncSession, tenant_id, taxonomy):
    idem_key = str(uuid.uuid4())
    r1 = await _create(db, tenant_id, taxonomy, idempotency_key=idem_key)
    r2 = await _create(db, tenant_id, taxonomy, idempotency_key=idem_key)
    assert r1.occurrence_id == r2.occurrence_id
    assert r1.numero == r2.numero


async def test_auto_promotion_creates_case(db: AsyncSession, tenant_id, taxonomy):
    result = await _create(db, tenant_id, taxonomy, severity="alta")
    assert result.case_id is not None
    assert result.case_reference is not None
    assert result.case_reference.startswith("CASE-")


async def test_no_promotion_below_threshold(db: AsyncSession, tenant_id, taxonomy):
    result = await _create(db, tenant_id, taxonomy, severity="baixa")
    # Promotion requires min_severity=alta; baixa < alta → no case
    assert result.case_id is None


async def test_auto_promotion_idempotent(db: AsyncSession, tenant_id, taxonomy):
    """Same occurrence created twice must not create two cases."""
    idem_key = str(uuid.uuid4())
    r1 = await _create(db, tenant_id, taxonomy, severity="alta", idempotency_key=idem_key)
    r2 = await _create(db, tenant_id, taxonomy, severity="alta", idempotency_key=idem_key)
    assert r1.occurrence_id == r2.occurrence_id
    # Only one case should exist
    cases = await db.execute(select(Case))
    case_list = list(cases.scalars())
    assert len(case_list) == 1


async def test_reverse_creates_estorno(db: AsyncSession, tenant_id, taxonomy):
    r1 = await _create(db, tenant_id, taxonomy, severity="baixa")
    svc = _svc(db, tenant_id)
    r2 = await svc.reverse(
        original_id=r1.occurrence_id,
        reason="Entered in error",
        idempotency_key=str(uuid.uuid4()),
    )
    await db.commit()
    original = await db.get(Occurrence, r1.occurrence_id)
    reversal = await db.get(Occurrence, r2.occurrence_id)
    assert "[ESTORNO]" in reversal.title
    assert reversal.supersedes_id == original.id
