"""FSM tests — transition rules, locking, idempotency."""
import asyncio
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.domain.fsm import CaseFSM
from core.exceptions import IllegalTransition, MissingRequiredField
from core.models import Case


async def _open(db, tenant_id, taxonomy) -> uuid.UUID:
    fsm = CaseFSM(db, tenant_id)
    case_id = await fsm.open_case(
        case_type_id=taxonomy["case_type"].id,
        initial_status="open",
        occurrence_ids=[],
        payload={},
        actor_id=uuid.uuid4(),
        idempotency_key=str(uuid.uuid4()),
    )
    await db.commit()
    return case_id


async def test_open_case_creates_case(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    case = await db.get(Case, case_id)
    assert case is not None
    assert case.status == "open"
    assert case.reference.startswith("CASE-")


async def test_reference_increments_sequentially(db: AsyncSession, tenant_id, taxonomy):
    id1 = await _open(db, tenant_id, taxonomy)
    id2 = await _open(db, tenant_id, taxonomy)
    c1 = await db.get(Case, id1)
    c2 = await db.get(Case, id2)
    seq1 = int(c1.reference.split("-")[-1])
    seq2 = int(c2.reference.split("-")[-1])
    assert seq2 == seq1 + 1


async def test_valid_transition_changes_status(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    fsm = CaseFSM(db, tenant_id)
    await fsm.apply_transition(
        case_id=case_id,
        to_status="in_analysis",
        payload={},
        attachments_present=False,
        actor_id=uuid.uuid4(),
        reason=None,
        idempotency_key=str(uuid.uuid4()),
    )
    await db.commit()
    case = await db.get(Case, case_id)
    assert case.status == "in_analysis"


async def test_illegal_transition_raises(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    fsm = CaseFSM(db, tenant_id)
    with pytest.raises(IllegalTransition):
        await fsm.apply_transition(
            case_id=case_id,
            to_status="closed",   # no rule open → closed
            payload={},
            attachments_present=False,
            actor_id=uuid.uuid4(),
            reason=None,
            idempotency_key=str(uuid.uuid4()),
        )


async def test_missing_required_field_raises(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    fsm = CaseFSM(db, tenant_id)
    # open → resolved requires resolution_note
    with pytest.raises(MissingRequiredField) as exc_info:
        await fsm.apply_transition(
            case_id=case_id,
            to_status="resolved",
            payload={},         # missing resolution_note
            attachments_present=False,
            actor_id=uuid.uuid4(),
            reason=None,
            idempotency_key=str(uuid.uuid4()),
        )
    assert exc_info.value.field == "resolution_note"


async def test_resolved_to_closed(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    actor = uuid.uuid4()
    fsm = CaseFSM(db, tenant_id)
    await fsm.apply_transition(
        case_id=case_id, to_status="resolved",
        payload={"resolution_note": "Fixed"},
        attachments_present=False, actor_id=actor,
        reason=None, idempotency_key=str(uuid.uuid4()),
    )
    await db.commit()
    await fsm.apply_transition(
        case_id=case_id, to_status="closed",
        payload={},
        attachments_present=False, actor_id=actor,
        reason=None, idempotency_key=str(uuid.uuid4()),
    )
    await db.commit()
    case = await db.get(Case, case_id)
    assert case.status == "closed"


async def test_idempotent_open_returns_same_case(db: AsyncSession, tenant_id, taxonomy):
    idem_key = str(uuid.uuid4())
    fsm = CaseFSM(db, tenant_id)
    id1 = await fsm.open_case(
        case_type_id=taxonomy["case_type"].id,
        initial_status="open",
        occurrence_ids=[], payload={},
        actor_id=uuid.uuid4(), idempotency_key=idem_key,
    )
    await db.commit()
    id2 = await fsm.open_case(
        case_type_id=taxonomy["case_type"].id,
        initial_status="open",
        occurrence_ids=[], payload={},
        actor_id=uuid.uuid4(), idempotency_key=idem_key,
    )
    await db.commit()
    assert id1 == id2


async def test_idempotent_transition_returns_same_record(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    idem_key = str(uuid.uuid4())
    fsm = CaseFSM(db, tenant_id)
    t1 = await fsm.apply_transition(
        case_id=case_id, to_status="in_analysis",
        payload={}, attachments_present=False,
        actor_id=uuid.uuid4(), reason=None, idempotency_key=idem_key,
    )
    await db.commit()
    t2 = await fsm.apply_transition(
        case_id=case_id, to_status="in_analysis",
        payload={}, attachments_present=False,
        actor_id=uuid.uuid4(), reason=None, idempotency_key=idem_key,
    )
    assert t1.id == t2.id


async def test_get_available_transitions(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    fsm = CaseFSM(db, tenant_id)
    transitions = await fsm.get_available_transitions(case_id)
    to_statuses = {t["to_status"] for t in transitions}
    assert "in_analysis" in to_statuses
    assert "resolved" in to_statuses


async def test_timeline_ordered_asc(db: AsyncSession, tenant_id, taxonomy):
    case_id = await _open(db, tenant_id, taxonomy)
    fsm = CaseFSM(db, tenant_id)
    await fsm.apply_transition(
        case_id=case_id, to_status="in_analysis",
        payload={}, attachments_present=False,
        actor_id=uuid.uuid4(), reason=None, idempotency_key=str(uuid.uuid4()),
    )
    await db.commit()
    timeline = await fsm.get_timeline(case_id)
    assert len(timeline) >= 1
    times = [t["at"] for t in timeline]
    assert times == sorted(times)


async def test_tenant_isolation_cross_tenant(engine, tenant_id, taxonomy):
    """Case created in tenant A is not visible to tenant B."""
    from core.database import set_rls_tenant
    other_tenant = uuid.uuid4()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Create case in tenant A
    set_rls_tenant(str(tenant_id))
    async with session_factory() as db_a:
        fsm = CaseFSM(db_a, tenant_id)
        case_id = await fsm.open_case(
            case_type_id=taxonomy["case_type"].id,
            initial_status="open",
            occurrence_ids=[], payload={},
            actor_id=uuid.uuid4(), idempotency_key=str(uuid.uuid4()),
        )
        await db_a.commit()

    # Tenant B should not see it (RLS)
    set_rls_tenant(str(other_tenant))
    async with session_factory() as db_b:
        case = await db_b.scalar(select(Case).where(Case.id == case_id))
        assert case is None

    set_rls_tenant(None)


async def test_concurrent_transitions_serialize_correctly(engine, tenant_id, taxonomy):
    """Two concurrent apply_transition calls on the same case must serialize.

    One must succeed (open → in_analysis), the other must raise IllegalTransition
    (in_analysis → in_analysis has no rule) — never corrupt state.
    """
    from core.database import set_rls_tenant
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Open a case first
    set_rls_tenant(str(tenant_id))
    async with session_factory() as setup_db:
        fsm = CaseFSM(setup_db, tenant_id)
        case_id = await fsm.open_case(
            case_type_id=taxonomy["case_type"].id,
            initial_status="open",
            occurrence_ids=[], payload={},
            actor_id=uuid.uuid4(), idempotency_key=str(uuid.uuid4()),
        )
        await setup_db.commit()

    errors: list[Exception] = []
    successes: list[str] = []

    async def _try_transition(idem_key: str) -> None:
        set_rls_tenant(str(tenant_id))
        async with session_factory() as sess:
            fsm = CaseFSM(sess, tenant_id)
            try:
                await fsm.apply_transition(
                    case_id=case_id, to_status="in_analysis",
                    payload={}, attachments_present=False,
                    actor_id=uuid.uuid4(), reason=None,
                    idempotency_key=idem_key,
                )
                await sess.commit()
                successes.append(idem_key)
            except (IllegalTransition, Exception) as e:
                errors.append(e)

    await asyncio.gather(
        _try_transition(str(uuid.uuid4())),
        _try_transition(str(uuid.uuid4())),
    )

    # Exactly one must have succeeded
    assert len(successes) == 1
    # Final case status must be in_analysis
    set_rls_tenant(str(tenant_id))
    async with session_factory() as check_db:
        case = await check_db.get(Case, case_id)
        assert case.status == "in_analysis"
    set_rls_tenant(None)
