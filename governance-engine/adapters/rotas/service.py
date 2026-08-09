"""
ROTAS Adapter Service.

bootstrap()     — idempotent setup: creates entity catalogs, taxonomy types,
                  case types, promotion rules, and transition rules for a tenant.
sync_entities() — upserts entity instances from ROTAS by external_id.
push_event()    — translates a ROTAS event push into an Occurrence (+ auto Case).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.rotas.schemas import (
    ROTAS_EVENT_TYPE_CODES,
    ROTAS_TO_GOVERNANCE_SEVERITY,
    RotasEntityRecord,
    RotasEventPush,
    RotasEventPushResponse,
)
from core.exceptions import NotFound
from core.models import (
    Case,
    CaseOccurrence,
    CaseTransitionRule,
    EntityCatalog,
    EntityInstance,
    Occurrence,
    TaxonomyCaseType,
    TaxonomyDomain,
    TaxonomyType,
    TaxonomyTypePromotion,
)
from core.services.occurrences import LinkInput, OccurrenceService

# ── Bootstrap constants ───────────────────────────────────────────────────────

_DOMAIN_CODE = "rotas"

_ENTITY_TYPES = ["vehicle", "driver", "trip", "third_party", "fuel_tank"]

_TAXONOMY_TYPES = list(ROTAS_EVENT_TYPE_CODES.values())

_CASE_TYPES = [
    {
        "code": "rotas.incident",
        "name": "Incidente Operacional",
        "initial_status": "open",
        "sla_hours": 48,
    },
    {
        "code": "rotas.compliance",
        "name": "Incumprimento Documental",
        "initial_status": "open",
        "sla_hours": 72,
    },
    {
        "code": "rotas.fuel_anomaly",
        "name": "Anomalia de Combustível",
        "initial_status": "open",
        "sla_hours": 24,
    },
    {
        "code": "rotas.cargo_integrity",
        "name": "Integridade de Carga",
        "initial_status": "open",
        "sla_hours": 24,
    },
]

# (type_code, case_type_code, min_severity)
_PROMOTIONS = [
    ("rotas.vehicle.breakdown", "rotas.incident", "alta"),
    ("rotas.vehicle.accident", "rotas.incident", "media"),
    ("rotas.trip.incident", "rotas.incident", "media"),
    ("rotas.fuel.anomaly", "rotas.fuel_anomaly", "alta"),
    ("rotas.fuel.theft_suspicion", "rotas.fuel_anomaly", "media"),
    ("rotas.cargo.damage", "rotas.cargo_integrity", "media"),
    ("rotas.cargo.loss", "rotas.cargo_integrity", "media"),
    ("rotas.document.expired", "rotas.compliance", "baixa"),
    ("rotas.vehicle.overdue_checklist", "rotas.compliance", "baixa"),
]

# Transition rule tuple:
# (from_status, to_status, required_fields, required_attachments, sla_hours)
_TRANSITION_RULES: dict[str, list[tuple]] = {
    "rotas.incident": [
        (None, "open", [], False, None),
        ("open", "in_analysis", [], False, None),
        ("in_analysis", "resolved", ["resolution_note"], False, None),
        ("open", "resolved", ["resolution_note"], False, None),
        ("resolved", "closed", [], False, None),
    ],
    "rotas.compliance": [
        (None, "open", [], False, None),
        ("open", "in_analysis", [], False, None),
        ("in_analysis", "resolved", ["resolution_note"], True, None),
        ("open", "resolved", ["resolution_note"], True, None),
        ("resolved", "closed", [], False, None),
    ],
    "rotas.fuel_anomaly": [
        (None, "open", [], False, None),
        ("open", "in_analysis", [], False, None),
        ("in_analysis", "resolved", ["resolution_note"], False, None),
        ("resolved", "closed", [], False, None),
    ],
    "rotas.cargo_integrity": [
        (None, "open", [], False, None),
        ("open", "in_analysis", [], False, None),
        ("in_analysis", "resolved", ["resolution_note"], True, None),
        ("resolved", "closed", [], False, None),
    ],
}


class RotasAdapterService:
    def __init__(self, db: AsyncSession, tenant_id: UUID, actor_id: UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._actor_id = actor_id

    # ── bootstrap ─────────────────────────────────────────────────────────────

    async def bootstrap(self) -> dict:
        domain = await self._ensure_domain()
        entity_catalogs = await self._ensure_entity_catalogs()
        taxonomy_types = await self._ensure_taxonomy_types(domain)
        case_types = await self._ensure_case_types(domain)
        await self._ensure_promotions(taxonomy_types, case_types)
        await self._ensure_transition_rules(case_types)
        await self._db.commit()
        return {
            "domain_id": str(domain.id),
            "entity_catalogs": len(entity_catalogs),
            "taxonomy_types": len(taxonomy_types),
            "case_types": len(case_types),
        }

    async def _ensure_domain(self) -> TaxonomyDomain:
        domain = await self._db.scalar(
            select(TaxonomyDomain).where(
                TaxonomyDomain.tenant_id == self._tenant_id,
                TaxonomyDomain.code == _DOMAIN_CODE,
            )
        )
        if domain is None:
            domain = TaxonomyDomain(
                tenant_id=self._tenant_id,
                code=_DOMAIN_CODE,
                name="ROTAS TMS",
                description="Eventos do sistema de gestão de frotas ROTAS",
            )
            self._db.add(domain)
            await self._db.flush()
        return domain

    async def _ensure_entity_catalogs(self) -> list[EntityCatalog]:
        catalogs = []
        for et in _ENTITY_TYPES:
            cat = await self._db.scalar(
                select(EntityCatalog).where(
                    EntityCatalog.tenant_id == self._tenant_id,
                    EntityCatalog.entity_type == et,
                )
            )
            if cat is None:
                cat = EntityCatalog(
                    tenant_id=self._tenant_id,
                    entity_type=et,
                    name=et.replace("_", " ").capitalize(),
                )
                self._db.add(cat)
                await self._db.flush()
            catalogs.append(cat)
        return catalogs

    async def _ensure_taxonomy_types(self, domain: TaxonomyDomain) -> dict[str, TaxonomyType]:
        types: dict[str, TaxonomyType] = {}
        for code in _TAXONOMY_TYPES:
            t = await self._db.scalar(
                select(TaxonomyType).where(
                    TaxonomyType.tenant_id == self._tenant_id,
                    TaxonomyType.code == code,
                )
            )
            if t is None:
                t = TaxonomyType(
                    tenant_id=self._tenant_id,
                    domain_id=domain.id,
                    code=code,
                    name=code.replace("rotas.", "").replace(".", " — ").replace("_", " ").title(),
                )
                self._db.add(t)
                await self._db.flush()
            types[code] = t
        return types

    async def _ensure_case_types(self, domain: TaxonomyDomain) -> dict[str, TaxonomyCaseType]:
        case_types: dict[str, TaxonomyCaseType] = {}
        for spec in _CASE_TYPES:
            ct = await self._db.scalar(
                select(TaxonomyCaseType).where(
                    TaxonomyCaseType.tenant_id == self._tenant_id,
                    TaxonomyCaseType.code == spec["code"],
                )
            )
            if ct is None:
                ct = TaxonomyCaseType(
                    tenant_id=self._tenant_id,
                    domain_id=domain.id,
                    code=spec["code"],
                    name=spec["name"],
                    initial_status=spec["initial_status"],
                    sla_hours=spec["sla_hours"],
                )
                self._db.add(ct)
                await self._db.flush()
            case_types[spec["code"]] = ct
        return case_types

    async def _ensure_promotions(
        self,
        types: dict[str, TaxonomyType],
        case_types: dict[str, TaxonomyCaseType],
    ) -> None:
        for type_code, case_type_code, min_sev in _PROMOTIONS:
            t = types.get(type_code)
            ct = case_types.get(case_type_code)
            if t is None or ct is None:
                continue
            existing = await self._db.scalar(
                select(TaxonomyTypePromotion).where(
                    TaxonomyTypePromotion.tenant_id == self._tenant_id,
                    TaxonomyTypePromotion.type_id == t.id,
                    TaxonomyTypePromotion.case_type_id == ct.id,
                )
            )
            if existing is None:
                self._db.add(
                    TaxonomyTypePromotion(
                        tenant_id=self._tenant_id,
                        type_id=t.id,
                        case_type_id=ct.id,
                        min_severity=min_sev,
                    )
                )
                await self._db.flush()

    async def _ensure_transition_rules(self, case_types: dict[str, TaxonomyCaseType]) -> None:
        for case_type_code, rules in _TRANSITION_RULES.items():
            ct = case_types.get(case_type_code)
            if ct is None:
                continue
            for from_s, to_s, req_fields, req_attach, sla_h in rules:
                existing = await self._db.scalar(
                    select(CaseTransitionRule).where(
                        CaseTransitionRule.tenant_id == self._tenant_id,
                        CaseTransitionRule.case_type_id == ct.id,
                        CaseTransitionRule.from_status == from_s,
                        CaseTransitionRule.to_status == to_s,
                    )
                )
                if existing is None:
                    self._db.add(
                        CaseTransitionRule(
                            tenant_id=self._tenant_id,
                            case_type_id=ct.id,
                            from_status=from_s,
                            to_status=to_s,
                            required_fields=req_fields,
                            required_attachments=req_attach,
                            sla_hours=sla_h,
                        )
                    )
                    await self._db.flush()

    # ── sync_entities ─────────────────────────────────────────────────────────

    async def sync_entities(self, records: list[RotasEntityRecord]) -> list[UUID]:
        ids: list[UUID] = []
        for rec in records:
            catalog = await self._db.scalar(
                select(EntityCatalog).where(
                    EntityCatalog.tenant_id == self._tenant_id,
                    EntityCatalog.entity_type == rec.entity_type,
                )
            )
            if catalog is None:
                catalog = EntityCatalog(
                    tenant_id=self._tenant_id,
                    entity_type=rec.entity_type,
                    name=rec.entity_type.capitalize(),
                )
                self._db.add(catalog)
                await self._db.flush()

            instance = await self._db.scalar(
                select(EntityInstance).where(
                    EntityInstance.tenant_id == self._tenant_id,
                    EntityInstance.catalog_id == catalog.id,
                    EntityInstance.external_id == rec.external_id,
                )
            )
            if instance is None:
                instance = EntityInstance(
                    tenant_id=self._tenant_id,
                    catalog_id=catalog.id,
                    external_id=rec.external_id,
                    display_name=rec.display_name,
                    attributes=rec.attributes,
                )
                self._db.add(instance)
            else:
                instance.display_name = rec.display_name
                instance.attributes = rec.attributes
            await self._db.flush()
            ids.append(instance.id)

        await self._db.commit()
        return ids

    # ── push_event ────────────────────────────────────────────────────────────

    async def push_event(self, event: RotasEventPush) -> RotasEventPushResponse:
        type_code = ROTAS_EVENT_TYPE_CODES.get(event.event_type, "rotas.trip.operational_exception")
        severity = ROTAS_TO_GOVERNANCE_SEVERITY.get(event.severity, "baixa")

        svc = OccurrenceService(self._db, self._tenant_id, self._actor_id)
        result = await svc.create(
            type_code=type_code,
            severity=severity,
            title=event.title,
            description=event.description,
            occurred_at=event.occurred_at,
            links=[
                LinkInput(
                    entity_type=e.entity_type,
                    external_id=e.external_id,
                    role=e.role,
                    display_name=e.display_name,
                    snapshot=e.snapshot,
                )
                for e in event.entities
            ],
            location_text=event.location_text,
            idempotency_key=event.idempotency_key,
            payload=event.payload,
        )
        await self._db.commit()

        return RotasEventPushResponse(
            occurrence_id=result.occurrence_id,
            numero=result.numero,
            case_id=result.case_id,
            case_reference=result.case_reference,
        )

    async def get_event_receipt(self, idempotency_key: str) -> RotasEventPushResponse:
        """Return the canonical receipt for an idempotently delivered event."""
        result = await self._db.execute(
            select(Occurrence, Case)
            .outerjoin(
                CaseOccurrence,
                and_(
                    CaseOccurrence.tenant_id == self._tenant_id,
                    CaseOccurrence.occurrence_id == Occurrence.id,
                ),
            )
            .outerjoin(
                Case,
                and_(
                    Case.tenant_id == self._tenant_id,
                    Case.id == CaseOccurrence.case_id,
                ),
            )
            .where(
                Occurrence.tenant_id == self._tenant_id,
                Occurrence.idempotency_key == idempotency_key,
            )
            .order_by(Case.created_at.asc().nulls_last())
            .limit(1)
        )
        row = result.one_or_none()
        if row is None:
            raise NotFound("ROTAS event receipt", idempotency_key)
        occurrence, case = row
        return RotasEventPushResponse(
            occurrence_id=occurrence.id,
            numero=occurrence.numero,
            case_id=case.id if case else None,
            case_reference=case.reference if case else None,
        )
