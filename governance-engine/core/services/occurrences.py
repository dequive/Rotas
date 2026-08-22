"""
OccurrenceService — creates immutable occurrence records and triggers
auto-promotion to Cases when taxonomy rules match.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.fsm import CaseFSM
from core.exceptions import NotFound
from core.models import (
    Case,
    EntityCatalog,
    EntityInstance,
    Occurrence,
    OccurrenceLink,
    TaxonomyCaseType,
    TaxonomyType,
    TaxonomyTypePromotion,
)

_SEVERITY_ORDER = ["baixa", "media", "alta", "critica"]


@dataclass
class LinkInput:
    entity_type: str
    external_id: str
    role: str
    display_name: str
    snapshot: dict


@dataclass
class CreateOccurrenceResult:
    occurrence_id: UUID
    numero: str
    case_id: UUID | None
    case_reference: str | None


class OccurrenceService:
    def __init__(self, db: AsyncSession, tenant_id: UUID, actor_id: UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._actor_id = actor_id

    async def create(
        self,
        *,
        type_code: str,
        severity: str,
        title: str,
        description: str | None,
        occurred_at: datetime,
        links: list[LinkInput],
        location_text: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        supersedes_id: UUID | None = None,
        idempotency_key: str | None = None,
        payload: dict | None = None,
    ) -> CreateOccurrenceResult:
        # Idempotency — fast path if key already used
        # (Sprint 2: move to occurrence_idempotency_keys table for non-unique key semantics)
        if idempotency_key:
            existing = await self._db.scalar(
                select(Occurrence).where(
                    Occurrence.tenant_id == self._tenant_id,
                    Occurrence.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return CreateOccurrenceResult(
                    occurrence_id=existing.id,
                    numero=existing.numero,
                    case_id=None,
                    case_reference=None,
                )

        # Resolve taxonomy type
        tax_type = await self._db.scalar(
            select(TaxonomyType).where(
                TaxonomyType.tenant_id == self._tenant_id,
                TaxonomyType.code == type_code,
                TaxonomyType.is_active.is_(True),
            )
        )
        if tax_type is None:
            raise NotFound("TaxonomyType", type_code)

        # Generate EVT-YYYY-NNNNNN
        numero = await self._next_numero()

        occ = Occurrence(
            tenant_id=self._tenant_id,
            numero=numero,
            type_id=tax_type.id,
            severity=severity,
            title=title,
            description=description,
            occurred_at=occurred_at,
            reported_by=self._actor_id,
            location_text=location_text,
            latitude=latitude,
            longitude=longitude,
            supersedes_id=supersedes_id,
            idempotency_key=idempotency_key,
            payload=payload or {},
        )
        self._db.add(occ)
        await self._db.flush()

        # Resolve and link entities
        instance_ids: list[UUID] = []
        for link in links:
            instance = await self._find_or_create_instance(
                entity_type=link.entity_type,
                external_id=link.external_id,
                display_name=link.display_name,
            )
            self._db.add(
                OccurrenceLink(
                    tenant_id=self._tenant_id,
                    occurrence_id=occ.id,
                    instance_id=instance.id,
                    role=link.role,
                    snapshot=link.snapshot,
                )
            )
            instance_ids.append(instance.id)
        if links:
            await self._db.flush()

        # Auto-promotion: check if type+severity matches a promotion rule
        case_id: UUID | None = None
        case_reference: str | None = None

        promotion = await self._db.scalar(
            select(TaxonomyTypePromotion).where(
                TaxonomyTypePromotion.tenant_id == self._tenant_id,
                TaxonomyTypePromotion.type_id == tax_type.id,
                TaxonomyTypePromotion.is_active.is_(True),
            )
        )
        if promotion and self._severity_gte(severity, promotion.min_severity):
            case_type = await self._db.get(TaxonomyCaseType, promotion.case_type_id)
            if case_type and case_type.is_active:
                fsm = CaseFSM(self._db, self._tenant_id)
                promo_idem_key = f"auto_promo:{idempotency_key}" if idempotency_key else None
                case_id = await fsm.open_case(
                    case_type_id=case_type.id,
                    initial_status=case_type.initial_status,
                    occurrence_ids=[occ.id],
                    payload={},
                    actor_id=self._actor_id,
                    idempotency_key=promo_idem_key,
                )
                case_obj = await self._db.scalar(select(Case).where(Case.id == case_id))
                if case_obj:
                    case_reference = case_obj.reference

        return CreateOccurrenceResult(
            occurrence_id=occ.id,
            numero=numero,
            case_id=case_id,
            case_reference=case_reference,
        )

    async def reverse(
        self,
        *,
        original_id: UUID,
        reason: str,
        idempotency_key: str | None,
    ) -> CreateOccurrenceResult:
        original = await self._db.scalar(
            select(Occurrence).where(
                Occurrence.id == original_id,
                Occurrence.tenant_id == self._tenant_id,
            )
        )
        if original is None:
            raise NotFound("Occurrence", str(original_id))

        tax_type = await self._db.get(TaxonomyType, original.type_id)

        # Carry original entity links into the estorno so audit chain is intact
        links_result = await self._db.execute(
            select(OccurrenceLink).where(OccurrenceLink.occurrence_id == original_id)
        )
        link_inputs: list[LinkInput] = []
        for lnk in links_result.scalars():
            inst = await self._db.get(EntityInstance, lnk.instance_id)
            if inst is None:
                continue
            catalog = await self._db.get(EntityCatalog, inst.catalog_id)
            link_inputs.append(
                LinkInput(
                    entity_type=catalog.entity_type if catalog else "",
                    external_id=inst.external_id,
                    role=lnk.role,
                    display_name=inst.display_name,
                    snapshot=lnk.snapshot,
                )
            )

        return await self.create(
            type_code=tax_type.code if tax_type else "",
            severity=original.severity,
            title=f"[ESTORNO] {original.title}",
            description=reason,
            occurred_at=datetime.now(UTC),
            links=link_inputs,
            supersedes_id=original_id,
            idempotency_key=idempotency_key,
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _next_numero(self) -> str:
        year = datetime.now(UTC).year
        result = await self._db.execute(
            text("SELECT next_human_id(:tid, 'EVT', :yr)"),
            {"tid": str(self._tenant_id), "yr": year},
        )
        return result.scalar_one()

    async def _find_or_create_instance(
        self,
        *,
        entity_type: str,
        external_id: str,
        display_name: str,
    ) -> EntityInstance:
        # Find catalog
        catalog = await self._db.scalar(
            select(EntityCatalog).where(
                EntityCatalog.tenant_id == self._tenant_id,
                EntityCatalog.entity_type == entity_type,
            )
        )
        if catalog is None:
            catalog = EntityCatalog(
                tenant_id=self._tenant_id,
                entity_type=entity_type,
                name=entity_type.capitalize(),
            )
            self._db.add(catalog)
            await self._db.flush()

        instance = await self._db.scalar(
            select(EntityInstance).where(
                EntityInstance.tenant_id == self._tenant_id,
                EntityInstance.catalog_id == catalog.id,
                EntityInstance.external_id == external_id,
            )
        )
        if instance is None:
            instance = EntityInstance(
                tenant_id=self._tenant_id,
                catalog_id=catalog.id,
                external_id=external_id,
                display_name=display_name or external_id,
            )
            self._db.add(instance)
            await self._db.flush()

        return instance

    @staticmethod
    def _severity_gte(severity: str, min_severity: str) -> bool:
        try:
            return _SEVERITY_ORDER.index(severity) >= _SEVERITY_ORDER.index(min_severity)
        except ValueError:
            return False
