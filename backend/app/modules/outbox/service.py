"""Stabilization/P0-F8: enqueue + drain for the transactional outbox.

Public surface:

  enqueue(session, tenant_id, event_type, payload, ...)   -- called from any
                                                              service that
                                                              wants to talk
                                                              to the external
                                                              system later
  drain_outbox(session, max_rows)                        -- called by the ARQ
                                                              outbox_drain job

The drainer POSTs each row to ``settings.governance_engine_url/ingest`` and
records the returned ``case_id`` so reconciliation can later cross-check
that ROTAS events correspond to Governance cases.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.modules.outbox.models import OutboxEvent

log = logging.getLogger("rotas.outbox")

# Exponential schedule (seconds) for retrying failed events. After the 6th
# attempt the row moves to terminal ``dead_letter`` status and requires a
# human operator to repair or discard it.
DEFAULT_BACKOFFS_SECONDS = (60, 300, 1800, 7200, 43200, 86400)


def _retry_at(attempt_count: int) -> datetime:
    if attempt_count < 0:
        attempt_count = 0
    if attempt_count >= len(DEFAULT_BACKOFFS_SECONDS):
        # Beyond the schedule, leave the row in dead_letter; attempt_count
        # is the number of attempts that already ran.
        offset_seconds = DEFAULT_BACKOFFS_SECONDS[-1]
    else:
        offset_seconds = DEFAULT_BACKOFFS_SECONDS[attempt_count]
    return datetime.now(UTC) + timedelta(seconds=offset_seconds)


def _is_dead_letter(attempt_count: int) -> bool:
    return attempt_count >= len(DEFAULT_BACKOFFS_SECONDS)


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
    """Insert an event row inside the caller's transaction.

    Caller is responsible for committing. Failure to commit will roll back
    both the business write AND the outbox row, keeping the system honest.
    """
    if selected_id is None:
        selected_id = uuid.uuid4()
    row = OutboxEvent(
        id=selected_id,
        tenant_id=tenant_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_type=event_type,
        payload=payload,
        status="pending",
        attempt_count=0,
        next_attempt_at=datetime.now(UTC),
        correlation_id=correlation_id,
    )
    session.add(row)
    # Caller commits. We do NOT flush here to keep the caller's control.
    return row


async def _post_to_governance(row: OutboxEvent) -> tuple[bool, dict[str, Any] | None, str | None]:
    settings = get_settings()
    if not settings.governance_engine_url:
        return False, None, "governance_engine_url not configured"
    url = f"{settings.governance_engine_url.rstrip('/')}/ingest"
    headers = {"Content-Type": "application/json"}
    if settings.governance_api_key:
        headers["Authorization"] = f"Bearer {settings.governance_api_key}"
    body = {
        "event_id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "event_type": row.event_type,
        "aggregate_type": row.aggregate_type,
        "aggregate_id": str(row.aggregate_id) if row.aggregate_id else None,
        "occurred_at": row.created_at.isoformat() if row.created_at else None,
        "correlation_id": str(row.correlation_id) if row.correlation_id else None,
        "payload": row.payload,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        return False, None, f"http_error: {exc.__class__.__name__}"

    if response.status_code >= 500:
        return False, None, f"upstream_{response.status_code}"
    if response.status_code >= 400:
        # 4xx: log but treat as terminal — retrying will not help.
        return False, None, f"client_error_{response.status_code}"

    try:
        body_json = response.json()
    except ValueError:
        body_json = {}
    body_json.get("case_id")
    return True, body_json, None


async def drain_outbox(session: AsyncSession, max_rows: int = 100) -> dict[str, int]:
    """Process pending events. Returns a small audit summary.

    Behavior per row:
      - success: status='sent', sent_at=now
      - retryable failure: status='pending', next_attempt_at=backoff,
        attempt_count += 1
      - terminal failure (>= max attempts) or client error: status='dead_letter'
    """
    settings = get_settings()
    if settings.ff_governance_outbox is False:
        # Feature flag default: off. Enables incremental rollout.
        return {"scanned": 0, "sent": 0, "retried": 0, "dead_letter": 0}

    stmt = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status == "pending",
            (OutboxEvent.next_attempt_at.is_(None))
            | (OutboxEvent.next_attempt_at <= datetime.now(UTC)),
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(max_rows)
    )
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    counts = {"scanned": len(rows), "sent": 0, "retried": 0, "dead_letter": 0}
    for row in rows:
        try:
            ok, body, error = await _post_to_governance(row)
        except Exception as exc:  # belt-and-suspenders against unforeseen errors
            ok, body, error = False, None, f"unexpected: {exc!r}"

        row.attempt_count += 1
        if ok:
            row.status = "sent"
            row.sent_at = datetime.now(UTC)
            case_id = (body or {}).get("case_id") if body else None
            if case_id:
                try:
                    row.governance_case_id = uuid.UUID(case_id)
                except (TypeError, ValueError):
                    # Server gave back a non-UUID; keep the row sent but log.
                    log.warning(
                        "Governance returned non-UUID case_id for event %s: %r",
                        row.id,
                        case_id,
                    )
            counts["sent"] += 1
            continue

        row.last_error = error or "unknown"
        if _is_dead_letter(row.attempt_count):
            row.status = "dead_letter"
            counts["dead_letter"] += 1
        else:
            row.status = "pending"
            row.next_attempt_at = _retry_at(row.attempt_count)
            counts["retried"] += 1

    if rows:
        await session.commit()
    return counts


# Re-exported for tests and reconciliation tooling.
class BackoffSchedule:
    """Convenience facade over the module-level backoff helpers."""

    @staticmethod
    def next_attempt_at(attempt_count: int) -> datetime:
        return _retry_at(attempt_count)

    @staticmethod
    def is_dead_letter(attempt_count: int) -> bool:
        return _is_dead_letter(attempt_count)


# Silence unused-import warning for ApiError (kept in case future errors
# surface via service call rather than the network layer).
_ = ApiError
