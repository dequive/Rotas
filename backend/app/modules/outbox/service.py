"""Stabilization/P0-F8: enqueue + drain for the transactional outbox.

Public surface:

  enqueue(session, tenant_id, event_type, payload, ...)   -- called from any
                                                              service that
                                                              wants to talk
                                                              to the external
                                                              system later
  drain_outbox(session, max_rows)                        -- called by the ARQ
                                                              outbox_drain job

The drainer POSTs each external row to the Governance ROTAS adapter and
records the returned ``case_id`` so reconciliation can later cross-check
that ROTAS events correspond to Governance cases.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi.encoders import jsonable_encoder
from prometheus_client import Counter
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

OUTBOX_DELIVERY_OUTCOMES = Counter(
    "rotas_outbox_delivery_outcomes_total",
    "Transactional outbox delivery outcomes.",
    ("outcome", "event_kind"),
)


class _InternalEventFailure(Exception):
    """Force a savepoint rollback for a failed internal outbox handler."""


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


async def _ensure_dead_letter_alert(session: AsyncSession, row: OutboxEvent) -> bool:
    from app.modules.alerts.models import Alert

    request_reference = f"outbox-dlq:{row.id}"
    alert = await session.scalar(
        select(Alert).where(
            Alert.tenant_id == row.tenant_id,
            Alert.request_reference == request_reference,
        )
    )
    message = (
        f"Event {row.event_type or 'unknown'} exhausted delivery and requires "
        f"operator review. Last error: {(row.last_error or 'unknown')[:500]}"
    )
    if alert is None:
        session.add(
            Alert(
                tenant_id=row.tenant_id,
                request_reference=request_reference,
                alert_type="outbox_dead_letter",
                priority="high",
                entity_type="outbox_event",
                entity_id=row.id,
                title="Outbox event moved to dead-letter",
                message=message,
                channel="dashboard",
                status="pending",
            )
        )
        return True
    if alert.status != "pending":
        alert.status = "pending"
        alert.sent_at = None
        alert.read_at = None
        alert.dismissed_at = None
    alert.message = message
    return False


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
        payload=jsonable_encoder(payload),
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
    if not settings.governance_api_key:
        return False, None, "governance_api_key not configured"
    url = f"{settings.governance_engine_url.rstrip('/')}/api/v1/adapters/rotas/events"
    headers = {"Content-Type": "application/json"}
    headers["X-API-Key"] = settings.governance_api_key
    body = dict(row.payload)
    body.setdefault("event_type", row.event_type)
    body.setdefault("idempotency_key", f"rotas:outbox:{row.id}")
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
            response = await client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        return False, None, f"http_error: {exc.__class__.__name__}"

    if response.status_code == 409:
        # Governance uses the idempotency key as the delivery identity.
        return True, {}, None
    if response.status_code in {408, 425, 429} or response.status_code >= 500:
        return False, None, f"upstream_{response.status_code}"
    if response.status_code >= 400:
        # Other 4xx responses are terminal contract/authentication failures.
        return False, None, f"client_error_{response.status_code}"

    try:
        body_json = response.json()
    except ValueError:
        body_json = {}
    return True, body_json, None


async def _process_internal_event(
    session: AsyncSession, row: OutboxEvent, arq_redis: Any | None = None
) -> tuple[bool, dict[str, Any] | None, str | None]:
    """Dispatch durable ROTAS-internal events without sending them to Governance."""
    event_type = row.event_type
    tenant_id = row.tenant_id
    payload = dict(row.payload)
    if event_type == "workshop.internal.invoice.create":
        from app.modules.workshop.models import WorkOrder
        from app.modules.workshop.workshop_billing_service import create_workshop_invoice

        work_order_id = uuid.UUID(str(payload["work_order_id"]))
        actor_raw = payload.get("actor_id")
        actor_id = uuid.UUID(str(actor_raw)) if actor_raw else None
        document = await create_workshop_invoice(
            session,
            tenant_id,
            work_order_id,
            actor_id=actor_id,
            commit=False,
        )
        work_order = await session.get(WorkOrder, work_order_id)
        if work_order and work_order.tenant_id == tenant_id:
            work_order.billing_status = "draft_created"
            work_order.billing_document_id = uuid.UUID(str(document["id"]))
            work_order.billing_error = None
        return True, document, None

    if event_type == "workshop.internal.preventive.advance":
        from app.modules.workshop.preventive_service import (
            handle_work_order_completion_preventive_matching,
        )

        work_order_id = uuid.UUID(str(payload["work_order_id"]))
        actor_raw = payload.get("actor_id")
        actor_id = uuid.UUID(str(actor_raw)) if actor_raw else None
        result = await handle_work_order_completion_preventive_matching(
            session,
            tenant_id,
            work_order_id,
            actor_id=actor_id,
            commit=False,
        )
        return True, result, None

    if event_type == "billing.internal.export.dispatch":
        if arq_redis is None:
            return False, None, "arq_redis_unavailable"
        await arq_redis.enqueue_job(
            "generate_billing_export",
            job_id=str(payload["job_id"]),
            document_id=str(payload["document_id"]),
            export_format=str(payload["export_format"]),
            tenant_id=str(payload["tenant_id"]),
            _job_id=f"outbox:{row.id}",
        )
        return True, {"job_id": str(payload["job_id"])}, None

    if event_type == "billing.internal.compliance_report.dispatch":
        if arq_redis is None:
            return False, None, "arq_redis_unavailable"
        await arq_redis.enqueue_job(
            "task_export_compliance_report",
            str(payload["job_id"]),
            str(payload["month"]),
            str(payload["tenant_id"]),
            _job_id=f"outbox:{row.id}",
        )
        return True, {"job_id": str(payload["job_id"])}, None

    return False, None, f"unsupported_internal_event: {event_type}"


async def drain_outbox(
    session: AsyncSession, max_rows: int = 100, arq_redis: Any | None = None
) -> dict[str, int]:
    """Process pending events. Returns a small audit summary.

    Behavior per row:
      - success: status='sent', sent_at=now
      - retryable failure: status='pending', next_attempt_at=backoff,
        attempt_count += 1
      - terminal failure (>= max attempts) or client error: status='dead_letter'
    """
    settings = get_settings()
    stmt = (
        select(OutboxEvent)
        .where(
            OutboxEvent.status == "pending",
            (OutboxEvent.next_attempt_at.is_(None)) | (OutboxEvent.next_attempt_at <= datetime.now(UTC)),
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(max_rows)
        .with_for_update(skip_locked=True)
    )
    if settings.ff_governance_outbox is False:
        # Internal events remain operational even when the Governance bridge is off.
        stmt = stmt.where(OutboxEvent.event_type.like("%.internal.%"))
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    counts = {
        "scanned": len(rows),
        "sent": 0,
        "retried": 0,
        "dead_letter": 0,
        "alerts_created": 0,
    }
    for row in rows:
        row_id = row.id
        is_internal = bool(row.event_type and ".internal." in row.event_type)
        if is_internal:
            try:
                async with session.begin_nested():
                    ok, body, error = await _process_internal_event(session, row, arq_redis)
                    if not ok:
                        raise _InternalEventFailure(error or "internal event failed")
            except Exception as exc:
                ok, body = False, None
                error = f"internal_error: {exc.__class__.__name__}: {exc}"
                row = await session.get(OutboxEvent, row_id, populate_existing=True)
                if row is None:
                    continue
                if row.event_type == "workshop.internal.invoice.create":
                    from app.modules.workshop.models import WorkOrder

                    work_order = await session.get(WorkOrder, row.aggregate_id)
                    if work_order and work_order.tenant_id == row.tenant_id:
                        work_order.billing_status = "billing_failed"
                        work_order.billing_error = str(exc)[:1000]
        else:
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
            OUTBOX_DELIVERY_OUTCOMES.labels("sent", "internal" if is_internal else "external").inc()
            continue

        row.last_error = error or "unknown"
        if (error or "").startswith("client_error_") or _is_dead_letter(row.attempt_count):
            row.status = "dead_letter"
            counts["dead_letter"] += 1
            if await _ensure_dead_letter_alert(session, row):
                counts["alerts_created"] += 1
            OUTBOX_DELIVERY_OUTCOMES.labels(
                "dead_letter", "internal" if is_internal else "external"
            ).inc()
        else:
            row.status = "pending"
            row.next_attempt_at = _retry_at(row.attempt_count)
            counts["retried"] += 1
            OUTBOX_DELIVERY_OUTCOMES.labels(
                "retry", "internal" if is_internal else "external"
            ).inc()

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
