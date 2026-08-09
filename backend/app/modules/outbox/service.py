"""Transactional delivery from ROTAS to Governance.

Delivery is at-least-once. Workers claim rows in a short PostgreSQL transaction
with ``FOR UPDATE SKIP LOCKED``, release the lock before network I/O and finish
only claims they still own. Governance idempotency makes crash redelivery safe.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.modules.outbox.models import OutboxEvent
from app.modules.platform.audit_service import record_platform_audit

log = logging.getLogger("rotas.outbox")

DEFAULT_BACKOFFS_SECONDS = (60, 300, 1800, 7200, 43200, 86400)
DEFAULT_CLAIM_LEASE_SECONDS = 120
MAX_ERROR_LENGTH = 500


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _retry_at(attempt_count: int) -> datetime:
    """Return the delay after ``attempt_count`` completed attempts."""
    schedule_index = max(0, attempt_count - 1)
    schedule_index = min(schedule_index, len(DEFAULT_BACKOFFS_SECONDS) - 1)
    return _utcnow() + timedelta(seconds=DEFAULT_BACKOFFS_SECONDS[schedule_index])


def _is_dead_letter(attempt_count: int) -> bool:
    return attempt_count >= len(DEFAULT_BACKOFFS_SECONDS)


def _is_terminal_error(error: str | None) -> bool:
    return bool(error and error.startswith("client_error_"))


def _safe_error(error: str | None) -> str:
    return (error or "unknown")[:MAX_ERROR_LENGTH]


def _idempotency_key(row: OutboxEvent) -> str:
    value = row.payload.get("idempotency_key") if isinstance(row.payload, dict) else None
    return str(value or f"rotas:outbox:{row.id}")


def _parse_uuid(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


async def enqueue(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    aggregate_type: str | None = None,
    aggregate_id: uuid.UUID | None = None,
    correlation_id: uuid.UUID | None = None,
    selected_id: uuid.UUID | None = None,
) -> OutboxEvent:
    """Insert an event in the caller's business transaction."""
    row = OutboxEvent(
        id=selected_id or uuid.uuid4(),
        tenant_id=tenant_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=jsonable_encoder(payload),
        status="pending",
        attempt_count=0,
        next_attempt_at=_utcnow(),
        correlation_id=correlation_id,
    )
    session.add(row)
    return row


def _governance_headers() -> tuple[str | None, dict[str, str] | None, str | None]:
    settings = get_settings()
    if not settings.governance_engine_url:
        return None, None, "governance_engine_url not configured"
    if not settings.governance_api_key:
        return None, None, "governance_api_key not configured"
    return (
        settings.governance_engine_url.rstrip("/"),
        {"Content-Type": "application/json", "X-API-Key": settings.governance_api_key},
        None,
    )


async def _post_to_governance(
    row: OutboxEvent,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    base_url, headers, configuration_error = _governance_headers()
    if configuration_error:
        return False, None, configuration_error

    body = dict(row.payload)
    body.setdefault("event_type", row.event_type)
    body.setdefault("idempotency_key", _idempotency_key(row))
    body.setdefault("occurred_at", row.created_at.isoformat() if row.created_at else None)
    body.setdefault(
        "payload",
        {
            "outbox_event_id": str(row.id),
            "aggregate_type": row.aggregate_type,
            "aggregate_id": str(row.aggregate_id) if row.aggregate_id else None,
            "correlation_id": str(row.correlation_id) if row.correlation_id else None,
        },
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{base_url}/api/v1/adapters/rotas/events",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        return False, None, f"http_error:{exc.__class__.__name__}"

    if response.status_code == 409:
        return True, {}, None
    if response.status_code in {408, 425, 429} or response.status_code >= 500:
        return False, None, f"upstream_{response.status_code}"
    if response.status_code >= 400:
        return False, None, f"client_error_{response.status_code}"
    try:
        response_body = response.json()
    except ValueError:
        response_body = {}
    return True, response_body, None


async def _get_governance_receipt(
    row: OutboxEvent,
) -> tuple[bool, dict[str, Any] | None, str | None]:
    base_url, headers, configuration_error = _governance_headers()
    if configuration_error:
        return False, None, configuration_error
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{base_url}/api/v1/adapters/rotas/events/receipt",
                headers=headers,
                params={"idempotency_key": _idempotency_key(row)},
            )
    except httpx.HTTPError as exc:
        return False, None, f"http_error:{exc.__class__.__name__}"

    if response.status_code == 404:
        return False, None, "receipt_not_found"
    if response.status_code in {408, 425, 429} or response.status_code >= 500:
        return False, None, f"upstream_{response.status_code}"
    if response.status_code >= 400:
        return False, None, f"client_error_{response.status_code}"
    try:
        return True, response.json(), None
    except ValueError:
        return False, None, "invalid_receipt_response"


async def _claim_batch(
    session: AsyncSession,
    *,
    worker_id: str,
    max_rows: int,
    lease_seconds: int,
) -> tuple[list[OutboxEvent], int]:
    if max_rows <= 0:
        return [], 0
    now = _utcnow()
    stmt = (
        select(OutboxEvent)
        .where(
            or_(
                and_(
                    OutboxEvent.status == "pending",
                    or_(
                        OutboxEvent.next_attempt_at.is_(None),
                        OutboxEvent.next_attempt_at <= now,
                    ),
                ),
                and_(
                    OutboxEvent.status == "processing",
                    or_(
                        OutboxEvent.claim_expires_at.is_(None),
                        OutboxEvent.claim_expires_at <= now,
                    ),
                ),
            )
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(max_rows)
        .with_for_update(skip_locked=True)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    reclaimed = sum(row.status == "processing" for row in rows)
    for row in rows:
        row.status = "processing"
        row.claimed_at = now
        row.claim_expires_at = now + timedelta(seconds=lease_seconds)
        row.claimed_by = worker_id
    if rows:
        await session.commit()
    return rows, reclaimed


async def _finish_claim(
    session: AsyncSession,
    *,
    row: OutboxEvent,
    worker_id: str,
    ok: bool,
    body: dict[str, Any] | None,
    error: str | None,
) -> str:
    now = _utcnow()
    attempt_count = row.attempt_count + 1
    values: dict[str, Any] = {
        "attempt_count": attempt_count,
        "total_attempt_count": row.total_attempt_count + 1,
        "claimed_at": None,
        "claim_expires_at": None,
        "claimed_by": None,
    }
    outcome: str
    if ok:
        occurrence_id = _parse_uuid((body or {}).get("occurrence_id"))
        values.update(
            status="sent",
            sent_at=now,
            next_attempt_at=None,
            last_error=None,
            governance_occurrence_id=occurrence_id,
            governance_case_id=_parse_uuid((body or {}).get("case_id")),
            reconciled_at=now if occurrence_id else None,
            next_reconciliation_at=None if occurrence_id else now,
            reconciliation_error=None,
        )
        outcome = "sent"
    elif _is_terminal_error(error) or _is_dead_letter(attempt_count):
        values.update(
            status="dead_letter",
            last_error=_safe_error(error),
            next_attempt_at=None,
            dead_lettered_at=now,
        )
        outcome = "dead_letter"
    else:
        values.update(
            status="pending",
            last_error=_safe_error(error),
            next_attempt_at=_retry_at(attempt_count),
        )
        outcome = "retried"

    result = await session.execute(
        update(OutboxEvent)
        .where(
            OutboxEvent.id == row.id,
            OutboxEvent.status == "processing",
            OutboxEvent.claimed_by == worker_id,
        )
        .values(**values)
        .returning(OutboxEvent.id)
    )
    finished = result.scalar_one_or_none() is not None
    await session.commit()
    return outcome if finished else "lost_claim"


async def drain_outbox(
    session: AsyncSession,
    max_rows: int = 100,
    *,
    worker_id: str | None = None,
    lease_seconds: int = DEFAULT_CLAIM_LEASE_SECONDS,
) -> dict[str, int]:
    """Claim and deliver a bounded batch without holding locks during HTTP."""
    if get_settings().ff_governance_outbox is False:
        return {
            "scanned": 0,
            "sent": 0,
            "retried": 0,
            "dead_letter": 0,
            "reclaimed": 0,
            "lost_claim": 0,
        }
    claim_owner = worker_id or f"worker:{uuid.uuid4()}"
    rows, reclaimed = await _claim_batch(
        session,
        worker_id=claim_owner,
        max_rows=max_rows,
        lease_seconds=max(1, lease_seconds),
    )
    counts = {
        "scanned": len(rows),
        "sent": 0,
        "retried": 0,
        "dead_letter": 0,
        "reclaimed": reclaimed,
        "lost_claim": 0,
    }
    for row in rows:
        try:
            ok, body, error = await _post_to_governance(row)
        except Exception as exc:  # pragma: no cover - final safety boundary
            ok, body, error = False, None, f"unexpected:{exc.__class__.__name__}"
        outcome = await _finish_claim(
            session,
            row=row,
            worker_id=claim_owner,
            ok=ok,
            body=body,
            error=error,
        )
        counts[outcome] += 1
    return counts


async def reconcile_outbox(session: AsyncSession, max_rows: int = 100) -> dict[str, int]:
    """Confirm Governance receipts for sent rows lacking occurrence evidence."""
    if get_settings().ff_governance_outbox is False or max_rows <= 0:
        return {"scanned": 0, "confirmed": 0, "missing": 0, "failed": 0, "lost_claim": 0}
    now = _utcnow()
    claim_owner = f"reconciler:{uuid.uuid4()}"
    rows = list(
        (
            await session.execute(
                select(OutboxEvent)
                .where(
                    OutboxEvent.status == "sent",
                    OutboxEvent.reconciled_at.is_(None),
                    or_(
                        OutboxEvent.next_reconciliation_at.is_(None),
                        OutboxEvent.next_reconciliation_at <= now,
                    ),
                    or_(
                        OutboxEvent.claim_expires_at.is_(None),
                        OutboxEvent.claim_expires_at <= now,
                    ),
                )
                .order_by(OutboxEvent.sent_at.asc())
                .limit(max_rows)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    if rows:
        for row in rows:
            row.claimed_at = now
            row.claim_expires_at = now + timedelta(seconds=DEFAULT_CLAIM_LEASE_SECONDS)
            row.claimed_by = claim_owner
        await session.commit()
    counts = {
        "scanned": len(rows),
        "confirmed": 0,
        "missing": 0,
        "failed": 0,
        "lost_claim": 0,
    }
    for row in rows:
        ok, body, error = await _get_governance_receipt(row)
        if not ok:
            outcome = "missing" if error == "receipt_not_found" else "failed"
            attempt_count = row.reconciliation_attempt_count + 1
            result = await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == row.id,
                    OutboxEvent.status == "sent",
                    OutboxEvent.reconciled_at.is_(None),
                    OutboxEvent.claimed_by == claim_owner,
                )
                .values(
                    reconciliation_attempt_count=attempt_count,
                    reconciliation_error=_safe_error(error),
                    next_reconciliation_at=_retry_at(attempt_count),
                    claimed_at=None,
                    claim_expires_at=None,
                    claimed_by=None,
                )
                .returning(OutboxEvent.id)
            )
            await session.commit()
            counts[outcome if result.scalar_one_or_none() is not None else "lost_claim"] += 1
            continue
        occurrence_id = _parse_uuid((body or {}).get("occurrence_id"))
        if occurrence_id is None:
            attempt_count = row.reconciliation_attempt_count + 1
            result = await session.execute(
                update(OutboxEvent)
                .where(
                    OutboxEvent.id == row.id,
                    OutboxEvent.status == "sent",
                    OutboxEvent.reconciled_at.is_(None),
                    OutboxEvent.claimed_by == claim_owner,
                )
                .values(
                    reconciliation_attempt_count=attempt_count,
                    reconciliation_error="invalid_receipt_response",
                    next_reconciliation_at=_retry_at(attempt_count),
                    claimed_at=None,
                    claim_expires_at=None,
                    claimed_by=None,
                )
                .returning(OutboxEvent.id)
            )
            await session.commit()
            counts["failed" if result.scalar_one_or_none() is not None else "lost_claim"] += 1
            continue
        result = await session.execute(
            update(OutboxEvent)
            .where(
                OutboxEvent.id == row.id,
                OutboxEvent.status == "sent",
                OutboxEvent.reconciled_at.is_(None),
                OutboxEvent.claimed_by == claim_owner,
            )
            .values(
                governance_occurrence_id=occurrence_id,
                governance_case_id=_parse_uuid((body or {}).get("case_id")),
                reconciled_at=_utcnow(),
                reconciliation_error=None,
                next_reconciliation_at=None,
                claimed_at=None,
                claim_expires_at=None,
                claimed_by=None,
            )
            .returning(OutboxEvent.id)
        )
        await session.commit()
        counts["confirmed" if result.scalar_one_or_none() is not None else "lost_claim"] += 1
    return counts


async def outbox_health(session: AsyncSession) -> dict[str, Any]:
    now = _utcnow()
    status_rows = await session.execute(
        select(OutboxEvent.status, func.count(OutboxEvent.id)).group_by(OutboxEvent.status)
    )
    status_counts = {str(key): int(value) for key, value in status_rows.all()}
    due_pending = await session.scalar(
        select(func.count(OutboxEvent.id)).where(
            OutboxEvent.status == "pending",
            or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now),
        )
    )
    stale_claims = await session.scalar(
        select(func.count(OutboxEvent.id)).where(
            OutboxEvent.status == "processing",
            or_(
                OutboxEvent.claim_expires_at.is_(None),
                OutboxEvent.claim_expires_at <= now,
            ),
        )
    )
    unreconciled_sent = await session.scalar(
        select(func.count(OutboxEvent.id)).where(
            OutboxEvent.status == "sent",
            OutboxEvent.reconciled_at.is_(None),
        )
    )
    oldest_pending = await session.scalar(
        select(func.min(OutboxEvent.created_at)).where(OutboxEvent.status == "pending")
    )
    return {
        "statuses": {key: status_counts.get(key, 0) for key in ("pending", "processing", "sent", "dead_letter")},
        "due_pending": int(due_pending or 0),
        "stale_claims": int(stale_claims or 0),
        "unreconciled_sent": int(unreconciled_sent or 0),
        "oldest_pending_at": oldest_pending,
        "checked_at": now,
    }


async def list_dead_letters(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID | None = None,
    limit: int = 100,
) -> list[OutboxEvent]:
    stmt = select(OutboxEvent).where(OutboxEvent.status == "dead_letter")
    if tenant_id is not None:
        stmt = stmt.where(OutboxEvent.tenant_id == tenant_id)
    result = await session.execute(stmt.order_by(OutboxEvent.dead_lettered_at.desc()).limit(max(1, min(limit, 200))))
    return list(result.scalars().all())


async def replay_dead_letter(
    session: AsyncSession,
    *,
    event_id: uuid.UUID,
    operator_id: uuid.UUID,
    operator_role: str,
    reason: str,
    ip_address: str | None = None,
) -> OutboxEvent:
    normalized_reason = reason.strip()
    if len(normalized_reason) < 10:
        raise ApiError(
            "replay_reason_required",
            "A replay reason with at least 10 characters is required.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    row = await session.scalar(select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update())
    if row is None:
        raise ApiError("outbox_event_not_found", "Outbox event not found.", status_code=404)
    if row.status != "dead_letter":
        raise ApiError(
            "outbox_event_not_replayable",
            "Only dead-letter events can be replayed.",
            status_code=status.HTTP_409_CONFLICT,
        )
    now = _utcnow()
    previous_attempt_count = row.attempt_count
    row.status = "pending"
    row.attempt_count = 0
    row.next_attempt_at = now
    row.dead_lettered_at = None
    row.claimed_at = None
    row.claim_expires_at = None
    row.claimed_by = None
    row.replay_count += 1
    row.last_replayed_at = now
    row.replayed_by = str(operator_id)
    row.replay_reason = normalized_reason
    await record_platform_audit(
        session,
        actor_id=operator_id,
        actor_role=operator_role,
        action="governance_outbox.replay",
        target_tenant_id=row.tenant_id,
        resource_type="outbox_event",
        resource_id=row.id,
        payload={
            "reason": normalized_reason,
            "previous_attempt_count": previous_attempt_count,
            "total_attempt_count": row.total_attempt_count,
            "replay_count": row.replay_count,
        },
        ip_address=ip_address,
    )
    await session.commit()
    await session.refresh(row)
    return row


class BackoffSchedule:
    @staticmethod
    def next_attempt_at(attempt_count: int) -> datetime:
        return _retry_at(attempt_count)

    @staticmethod
    def is_dead_letter(attempt_count: int) -> bool:
        return _is_dead_letter(attempt_count)
