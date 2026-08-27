"""
ROTAS adapter end-to-end tests.

Covers:
- bootstrap() is idempotent (safe to call N times)
- sync_entities() upserts correctly
- push_event() creates Occurrence + auto-promotes to Case for high severity
- push_event() idempotency (same key → same occurrence)
- all 13 event types map to a valid taxonomy code
- entity created on-the-fly when not pre-synced
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.rotas.schemas import (
    ROTAS_EVENT_TYPE_CODES,
    RotasEntityRecord,
    RotasEventEntity,
    RotasEventPush,
)
from adapters.rotas.service import RotasAdapterService
from core.models import Case, Occurrence


def _svc(db: AsyncSession, tenant_id: uuid.UUID) -> RotasAdapterService:
    return RotasAdapterService(db, tenant_id, uuid.uuid4())


async def test_bootstrap_creates_taxonomy(db: AsyncSession, tenant_id: uuid.UUID):
    svc = _svc(db, tenant_id)
    result = await svc.bootstrap()
    assert result["taxonomy_types"] == len(ROTAS_EVENT_TYPE_CODES)
    assert result["case_types"] == 4
    assert result["entity_catalogs"] == 5


async def test_bootstrap_is_idempotent(db: AsyncSession, tenant_id: uuid.UUID):
    svc = _svc(db, tenant_id)
    r1 = await svc.bootstrap()
    r2 = await svc.bootstrap()
    assert r1["taxonomy_types"] == r2["taxonomy_types"]
    assert r1["case_types"] == r2["case_types"]


async def test_sync_entities_creates_instances(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    vehicle_id = str(uuid.uuid4())
    ids = await svc.sync_entities(
        [
            RotasEntityRecord(
                entity_type="vehicle",
                external_id=vehicle_id,
                display_name="MZ-01-AB",
                attributes={"plate": "MZ-01-AB", "make": "Mercedes"},
            )
        ]
    )
    assert len(ids) == 1


async def test_sync_entities_upserts_on_second_call(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    ext_id = str(uuid.uuid4())
    record = RotasEntityRecord(
        entity_type="vehicle", external_id=ext_id, display_name="v1", attributes={}
    )
    ids1 = await svc.sync_entities([record])
    record.display_name = "v2-updated"
    ids2 = await svc.sync_entities([record])
    # Same instance, updated display_name
    assert ids1[0] == ids2[0]


async def test_push_event_creates_occurrence(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    result = await svc.push_event(
        RotasEventPush(
            event_type="vehicle.breakdown",
            severity="alta",
            title="Avaria em estrada",
            occurred_at=datetime.now(UTC),
            entities=[],
            idempotency_key=f"test:{uuid.uuid4()}",
        )
    )
    assert result.numero.startswith("EVT-")
    occ = await db.get(Occurrence, result.occurrence_id)
    assert occ is not None
    assert occ.tenant_id == tenant_id


async def test_push_event_high_severity_auto_promotes(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    result = await svc.push_event(
        RotasEventPush(
            event_type="vehicle.breakdown",
            severity="alta",
            title="Avaria grave",
            occurred_at=datetime.now(UTC),
            entities=[],
            idempotency_key=f"test:{uuid.uuid4()}",
        )
    )
    assert result.case_id is not None
    assert result.case_reference.startswith("CASE-")
    case = await db.get(Case, result.case_id)
    assert case is not None
    assert case.status == "open"


async def test_push_event_low_severity_no_case(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    result = await svc.push_event(
        RotasEventPush(
            event_type="vehicle.breakdown",
            severity="baixa",
            title="Avaria leve",
            occurred_at=datetime.now(UTC),
            entities=[],
            idempotency_key=f"test:{uuid.uuid4()}",
        )
    )
    assert result.case_id is None


async def test_push_event_idempotent(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    idem_key = f"test:{uuid.uuid4()}"
    event = RotasEventPush(
        event_type="trip.incident",
        severity="media",
        title="Incidente de percurso",
        occurred_at=datetime.now(UTC),
        entities=[],
        idempotency_key=idem_key,
    )
    r1 = await svc.push_event(event)
    r2 = await svc.push_event(event)
    assert r1.occurrence_id == r2.occurrence_id
    assert r1.numero == r2.numero


async def test_push_event_with_entities_creates_links(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    vehicle_ext_id = str(uuid.uuid4())
    result = await svc.push_event(
        RotasEventPush(
            event_type="fuel.anomaly",
            severity="alta",
            title="Consumo anómalo",
            occurred_at=datetime.now(UTC),
            entities=[
                RotasEventEntity(
                    entity_type="vehicle",
                    external_id=vehicle_ext_id,
                    role="sujeito",
                    display_name="MZ-99-XY",
                    snapshot={"plate": "MZ-99-XY"},
                )
            ],
            idempotency_key=f"test:{uuid.uuid4()}",
        )
    )
    assert result.occurrence_id is not None
    # Verify link was created
    from core.models import OccurrenceLink

    links = await db.execute(
        select(OccurrenceLink).where(OccurrenceLink.occurrence_id == result.occurrence_id)
    )
    link_list = list(links.scalars())
    assert len(link_list) == 1
    assert link_list[0].role == "sujeito"


async def test_entity_created_on_the_fly_if_not_synced(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    # Push event with an entity that was never synced via sync_entities
    ext_id = str(uuid.uuid4())
    result = await svc.push_event(
        RotasEventPush(
            event_type="driver.infraction",
            severity="media",
            title="Infracção de trânsito",
            occurred_at=datetime.now(UTC),
            entities=[
                RotasEventEntity(
                    entity_type="driver",
                    external_id=ext_id,
                    display_name="João Machava",
                )
            ],
            idempotency_key=f"test:{uuid.uuid4()}",
        )
    )
    assert result.occurrence_id is not None


async def test_all_event_types_have_taxonomy_code():
    """All 13 event type keys in ROTAS_EVENT_TYPE_CODES must be non-empty strings."""
    assert len(ROTAS_EVENT_TYPE_CODES) == 13
    for event_type, code in ROTAS_EVENT_TYPE_CODES.items():
        assert code.startswith("rotas."), f"{event_type} maps to non-rotas code: {code}"


async def test_document_expired_promotes_to_compliance(db: AsyncSession, tenant_id: uuid.UUID):
    await _svc(db, tenant_id).bootstrap()
    svc = _svc(db, tenant_id)
    result = await svc.push_event(
        RotasEventPush(
            event_type="document.expired",
            severity="baixa",  # min_severity for compliance is baixa
            title="Documento expirado",
            occurred_at=datetime.now(UTC),
            entities=[],
            idempotency_key=f"test:{uuid.uuid4()}",
        )
    )
    # document.expired + baixa >= baixa → should promote to rotas.compliance
    assert result.case_id is not None
    case = await db.get(Case, result.case_id)
    from core.models import TaxonomyCaseType

    ct = await db.get(TaxonomyCaseType, case.case_type_id)
    assert ct.code == "rotas.compliance"
