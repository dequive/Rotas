from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.alerts.models import Alert
from app.modules.audit.service import record_audit_log
from app.modules.outbox.models import OutboxEvent

OUTBOX_STATUSES = frozenset({"pending", "sent", "dead_letter"})


def serialize_outbox_event(row: OutboxEvent, *, include_payload: bool = False) -> dict:
    event = {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "aggregate_type": row.aggregate_type,
        "aggregate_id": row.aggregate_id,
        "event_type": row.event_type,
        "status": row.status,
        "governance_case_id": row.governance_case_id,
        "attempt_count": row.attempt_count,
        "last_error": row.last_error,
        "next_attempt_at": row.next_attempt_at,
        "created_at": row.created_at,
        "sent_at": row.sent_at,
        "correlation_id": row.correlation_id,
    }
    if include_payload:
        event["payload"] = row.payload
    return event


def _audit_state(row: OutboxEvent) -> dict:
    return {
        "status": row.status,
        "attempt_count": row.attempt_count,
        "last_error": row.last_error,
        "next_attempt_at": row.next_attempt_at,
        "sent_at": row.sent_at,
        "governance_case_id": row.governance_case_id,
    }


def _validate_status(status_filter: str | None) -> None:
    if status_filter is not None and status_filter not in OUTBOX_STATUSES:
        raise ApiError(
            "invalid_outbox_status",
            "Outbox status is not supported.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"allowed_statuses": sorted(OUTBOX_STATUSES)},
        )


async def list_outbox_events(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    event_type: str | None = None,
    aggregate_type: str | None = None,
    correlation_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    _validate_status(status_filter)
    stmt = select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id)
    if status_filter:
        stmt = stmt.where(OutboxEvent.status == status_filter)
    if event_type:
        stmt = stmt.where(OutboxEvent.event_type == event_type)
    if aggregate_type:
        stmt = stmt.where(OutboxEvent.aggregate_type == aggregate_type)
    if correlation_id:
        stmt = stmt.where(OutboxEvent.correlation_id == correlation_id)
    rows = (
        (
            await db.execute(
                stmt.order_by(OutboxEvent.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return [serialize_outbox_event(row) for row in rows]


async def get_outbox_event(db: AsyncSession, tenant_id: UUID, event_id: UUID) -> dict:
    row = await db.scalar(
        select(OutboxEvent).where(
            OutboxEvent.id == event_id,
            OutboxEvent.tenant_id == tenant_id,
        )
    )
    if row is None:
        raise ApiError(
            "outbox_event_not_found",
            "Outbox event not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return serialize_outbox_event(row, include_payload=True)


async def get_outbox_reconciliation(db: AsyncSession, tenant_id: UUID) -> dict:
    now = datetime.now(UTC)
    counts_row = (
        await db.execute(
            select(
                func.count(OutboxEvent.id).label("total"),
                func.count(case((OutboxEvent.status == "pending", 1))).label("pending"),
                func.count(case((OutboxEvent.status == "sent", 1))).label("sent"),
                func.count(case((OutboxEvent.status == "dead_letter", 1))).label(
                    "dead_letter"
                ),
                func.count(
                    case(
                        (
                            (OutboxEvent.status == "pending")
                            & (
                                OutboxEvent.next_attempt_at.is_(None)
                                | (OutboxEvent.next_attempt_at <= now)
                            ),
                            1,
                        )
                    )
                ).label("pending_due"),
                func.count(
                    case(
                        (
                            (OutboxEvent.status == "sent")
                            & OutboxEvent.sent_at.is_(None),
                            1,
                        )
                    )
                ).label("sent_without_timestamp"),
                func.count(
                    case(
                        (
                            (OutboxEvent.status == "sent")
                            & OutboxEvent.event_type.not_like("%.internal.%")
                            & OutboxEvent.governance_case_id.is_(None),
                            1,
                        )
                    )
                ).label("governance_case_unrecorded"),
                func.min(
                    case(
                        (OutboxEvent.status == "pending", OutboxEvent.created_at),
                        else_=None,
                    )
                ).label("oldest_pending_at"),
                func.min(
                    case(
                        (OutboxEvent.status == "dead_letter", OutboxEvent.created_at),
                        else_=None,
                    )
                ).label("oldest_dead_letter_at"),
            ).where(OutboxEvent.tenant_id == tenant_id)
        )
    ).one()
    metrics = {
        "total": int(counts_row.total or 0),
        "pending": int(counts_row.pending or 0),
        "sent": int(counts_row.sent or 0),
        "dead_letter": int(counts_row.dead_letter or 0),
        "pending_due": int(counts_row.pending_due or 0),
        "sent_without_timestamp": int(counts_row.sent_without_timestamp or 0),
        "governance_case_unrecorded": int(counts_row.governance_case_unrecorded or 0),
        "oldest_pending_at": counts_row.oldest_pending_at,
        "oldest_dead_letter_at": counts_row.oldest_dead_letter_at,
    }
    if metrics["dead_letter"] or metrics["sent_without_timestamp"]:
        health = "red"
    elif metrics["pending_due"] or metrics["governance_case_unrecorded"]:
        health = "yellow"
    else:
        health = "green"
    return {
        "tenant_id": tenant_id,
        "health": health,
        "measured_at": now,
        "metrics": metrics,
    }


async def replay_dead_letter(
    db: AsyncSession,
    tenant_id: UUID,
    event_id: UUID,
    *,
    reason: str,
    actor_id: UUID | None,
) -> dict:
    row = await db.scalar(
        select(OutboxEvent)
        .where(
            OutboxEvent.id == event_id,
            OutboxEvent.tenant_id == tenant_id,
        )
        .with_for_update()
    )
    if row is None:
        raise ApiError(
            "outbox_event_not_found",
            "Outbox event not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if row.status == "pending":
        return {"replayed": False, "event": serialize_outbox_event(row)}
    if row.status != "dead_letter":
        raise ApiError(
            "outbox_event_not_replayable",
            "Only dead-letter events can be replayed.",
            status_code=status.HTTP_409_CONFLICT,
            details={"current_status": row.status},
        )

    old_values = _audit_state(row)
    row.status = "pending"
    row.attempt_count = 0
    row.last_error = None
    row.next_attempt_at = datetime.now(UTC)
    row.sent_at = None
    row.governance_case_id = None
    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.request_reference == f"outbox-dlq:{row.id}",
        )
    )
    if alert is not None:
        alert.status = "dismissed"
        alert.dismissed_at = datetime.now(UTC)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="outbox.dead_letter_replayed",
        entity_type="outbox_event",
        entity_id=row.id,
        old_values=old_values,
        new_values={**_audit_state(row), "reason": reason},
        correlation_id=str(row.correlation_id) if row.correlation_id else None,
    )
    await db.commit()
    await db.refresh(row)
    return {"replayed": True, "event": serialize_outbox_event(row)}
