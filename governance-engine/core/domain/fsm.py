"""
Case Finite State Machine.

All state changes go through this class — never update case.status directly.
Pessimistic locking (SELECT FOR UPDATE) serialises concurrent transitions on the same case.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import (
    IllegalTransition,
    MissingRequiredAttachment,
    MissingRequiredField,
    NotFound,
)
from core.models import (
    Activity,
    Case,
    CaseOccurrence,
    CaseTransition,
    CaseTransitionRule,
)

_SEVERITY_ORDER = ["baixa", "media", "alta", "critica"]


class CaseFSM:
    def __init__(self, db: AsyncSession, tenant_id: UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id

    # ── open_case ─────────────────────────────────────────────────────────────

    async def open_case(
        self,
        *,
        case_type_id: UUID,
        initial_status: str,
        occurrence_ids: list[UUID],
        payload: dict,
        actor_id: UUID,
        idempotency_key: str | None,
    ) -> UUID:
        # Idempotency check
        if idempotency_key:
            existing = await self._db.scalar(
                select(CaseTransition).where(
                    CaseTransition.tenant_id == self._tenant_id,
                    CaseTransition.idempotency_key == idempotency_key,
                    CaseTransition.from_status.is_(None),
                )
            )
            if existing:
                return existing.case_id

        # Validate entry rule (from_status=None)
        rule = await self._db.scalar(
            select(CaseTransitionRule).where(
                CaseTransitionRule.tenant_id == self._tenant_id,
                CaseTransitionRule.case_type_id == case_type_id,
                CaseTransitionRule.from_status.is_(None),
                CaseTransitionRule.to_status == initial_status,
                CaseTransitionRule.is_active.is_(True),
            )
        )
        if rule is None:
            raise IllegalTransition(None, initial_status)

        # Validate required fields
        for field_name in rule.required_fields or []:
            if not payload.get(field_name):
                raise MissingRequiredField(field_name)

        # Generate CASE-YYYY-NNNNNN
        reference = await self._next_reference()

        # Compute SLA
        sla_due_at = None
        if rule.sla_hours:
            sla_due_at = datetime.now(UTC) + timedelta(hours=rule.sla_hours)

        case = Case(
            tenant_id=self._tenant_id,
            reference=reference,
            case_type_id=case_type_id,
            status=initial_status,
            payload=payload,
            sla_due_at=sla_due_at,
        )
        self._db.add(case)
        await self._db.flush()

        # Link occurrences
        for occ_id in occurrence_ids:
            self._db.add(
                CaseOccurrence(
                    case_id=case.id,
                    occurrence_id=occ_id,
                    tenant_id=self._tenant_id,
                )
            )

        # Record entry transition
        transition = CaseTransition(
            tenant_id=self._tenant_id,
            case_id=case.id,
            from_status=None,
            to_status=initial_status,
            actor_id=actor_id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        self._db.add(transition)
        await self._db.flush()

        self._db.add(
            Activity(
                tenant_id=self._tenant_id,
                case_id=case.id,
                transition_id=transition.id,
                actor_id=actor_id,
                activity_type="case_opened",
                description=f"Case opened in status {initial_status}",
                payload={"from_status": None, "to_status": initial_status},
            )
        )
        await self._db.flush()

        # SLA activity
        if sla_due_at:
            self._db.add(
                Activity(
                    tenant_id=self._tenant_id,
                    case_id=case.id,
                    transition_id=transition.id,
                    actor_id=actor_id,
                    activity_type="sla_set",
                    description=f"SLA due at {sla_due_at.isoformat()}",
                    payload={"sla_due_at": sla_due_at.isoformat()},
                )
            )
            await self._db.flush()

        return case.id

    # ── apply_transition ──────────────────────────────────────────────────────

    async def apply_transition(
        self,
        *,
        case_id: UUID,
        to_status: str,
        payload: dict,
        attachments_present: bool,
        actor_id: UUID,
        reason: str | None,
        idempotency_key: str | None,
    ) -> CaseTransition:
        # Idempotency check
        if idempotency_key:
            existing = await self._db.scalar(
                select(CaseTransition).where(
                    CaseTransition.tenant_id == self._tenant_id,
                    CaseTransition.idempotency_key == idempotency_key,
                )
            )
            if existing:
                return existing

        # Pessimistic lock — serialises concurrent transitions on the same case
        case = await self._db.scalar(
            select(Case)
            .where(Case.id == case_id, Case.tenant_id == self._tenant_id)
            .with_for_update()
        )
        if case is None:
            raise NotFound("Case", str(case_id))

        # Find matching rule
        rule = await self._db.scalar(
            select(CaseTransitionRule).where(
                CaseTransitionRule.tenant_id == self._tenant_id,
                CaseTransitionRule.case_type_id == case.case_type_id,
                CaseTransitionRule.from_status == case.status,
                CaseTransitionRule.to_status == to_status,
                CaseTransitionRule.is_active.is_(True),
            )
        )
        if rule is None:
            raise IllegalTransition(case.status, to_status)

        # Validate required fields
        for field_name in rule.required_fields or []:
            if not payload.get(field_name):
                raise MissingRequiredField(field_name)

        # Validate attachments
        if rule.required_attachments and not attachments_present:
            raise MissingRequiredAttachment()

        from_status = case.status

        # Record transition (append-only)
        transition = CaseTransition(
            tenant_id=self._tenant_id,
            case_id=case_id,
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            reason=reason,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        self._db.add(transition)
        await self._db.flush()

        self._db.add(
            Activity(
                tenant_id=self._tenant_id,
                case_id=case_id,
                transition_id=transition.id,
                actor_id=actor_id,
                activity_type="case_transitioned",
                description=f"Case transitioned from {from_status} to {to_status}",
                payload={"from_status": from_status, "to_status": to_status},
            )
        )
        await self._db.flush()

        # Update case.status (only mutation allowed on cases)
        await self._db.execute(
            update(Case)
            .where(Case.id == case_id)
            .values(status=to_status, updated_at=datetime.now(UTC))
            .execution_options(synchronize_session=False)
        )
        await self._db.flush()

        # SLA activity if rule defines new SLA
        if rule.sla_hours:
            sla_due_at = datetime.now(UTC) + timedelta(hours=rule.sla_hours)
            self._db.add(
                Activity(
                    tenant_id=self._tenant_id,
                    case_id=case_id,
                    transition_id=transition.id,
                    actor_id=actor_id,
                    activity_type="sla_updated",
                    description=f"SLA reset to {sla_due_at.isoformat()}",
                    payload={"sla_due_at": sla_due_at.isoformat()},
                )
            )
            await self._db.execute(
                update(Case)
                .where(Case.id == case_id)
                .values(sla_due_at=sla_due_at)
                .execution_options(synchronize_session=False)
            )
            await self._db.flush()

        return transition

    # ── queries ───────────────────────────────────────────────────────────────

    async def get_available_transitions(self, case_id: UUID) -> list[dict]:
        case = await self._db.scalar(
            select(Case).where(Case.id == case_id, Case.tenant_id == self._tenant_id)
        )
        if case is None:
            raise NotFound("Case", str(case_id))

        result = await self._db.execute(
            select(CaseTransitionRule).where(
                CaseTransitionRule.tenant_id == self._tenant_id,
                CaseTransitionRule.case_type_id == case.case_type_id,
                CaseTransitionRule.from_status == case.status,
                CaseTransitionRule.is_active.is_(True),
            )
        )
        return [
            {
                "to_status": r.to_status,
                "required_fields": r.required_fields or [],
                "required_attachments": r.required_attachments,
            }
            for r in result.scalars()
        ]

    async def get_timeline(self, case_id: UUID) -> list[dict]:
        result = await self._db.execute(
            select(Activity)
            .where(Activity.case_id == case_id, Activity.tenant_id == self._tenant_id)
            .order_by(Activity.at.asc())
        )
        return [
            {
                "id": str(a.id),
                "activity_type": a.activity_type,
                "actor_id": str(a.actor_id),
                "description": a.description,
                "payload": a.payload,
                "at": a.at.isoformat(),
            }
            for a in result.scalars()
        ]

    # ── helpers ───────────────────────────────────────────────────────────────

    async def _next_reference(self) -> str:
        year = datetime.now(UTC).year
        result = await self._db.execute(
            text("SELECT next_human_id(:tid, 'CASE', :yr)"),
            {"tid": str(self._tenant_id), "yr": year},
        )
        return result.scalar_one()
