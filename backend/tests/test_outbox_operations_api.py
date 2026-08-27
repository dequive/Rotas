import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.alerts.models import Alert
from app.modules.audit.models import AuditLog
from app.modules.outbox import service as outbox_service
from app.modules.outbox.models import OutboxEvent
from app.modules.tenants.models import Tenant


def _row(tenant_id, *, status: str, attempt_count: int = 0) -> OutboxEvent:
    now = datetime.now(UTC)
    return OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type="trip",
        aggregate_id=uuid4(),
        event_type="trip.incident",
        payload={
            "event_type": "trip.incident",
            "title": "Operational test",
            "idempotency_key": f"test:{uuid4()}",
        },
        status=status,
        attempt_count=attempt_count,
        last_error="upstream_503" if status == "dead_letter" else None,
        next_attempt_at=now - timedelta(minutes=1) if status == "pending" else None,
        sent_at=now if status == "sent" else None,
        created_at=now,
    )


@pytest.mark.asyncio
async def test_outbox_list_and_detail_are_strictly_tenant_scoped(
    async_client, db, tenant_id, auth_headers
):
    other = Tenant(name=f"Other {uuid4().hex[:8]}", slug=f"other-{uuid4().hex[:8]}")
    db.add(other)
    await db.flush()
    own = _row(tenant_id, status="dead_letter", attempt_count=6)
    foreign = _row(other.id, status="dead_letter", attempt_count=6)
    db.add_all([own, foreign])
    await db.commit()

    listing = await async_client.get(
        "/api/v1/outbox-events?status=dead_letter",
        headers=auth_headers,
    )
    foreign_detail = await async_client.get(
        f"/api/v1/outbox-events/{foreign.id}",
        headers=auth_headers,
    )
    own_detail = await async_client.get(
        f"/api/v1/outbox-events/{own.id}",
        headers=auth_headers,
    )

    assert listing.status_code == 200, listing.text
    assert {item["id"] for item in listing.json()} >= {str(own.id)}
    assert str(foreign.id) not in {item["id"] for item in listing.json()}
    assert foreign_detail.status_code == 404
    assert own_detail.status_code == 200
    assert own_detail.json()["payload"]["title"] == "Operational test"


@pytest.mark.asyncio
async def test_outbox_operations_require_dedicated_permissions(
    async_client, viewer_headers
):
    response = await async_client.get(
        "/api/v1/outbox-events/reconciliation",
        headers=viewer_headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["details"]["required_permissions"] == ["outbox.read"]


@pytest.mark.asyncio
async def test_dead_letter_replay_is_atomic_audited_and_idempotent(
    async_client, db, tenant_id, auth_headers
):
    row = _row(tenant_id, status="dead_letter", attempt_count=6)
    db.add(row)
    await db.flush()
    alert = Alert(
        tenant_id=tenant_id,
        request_reference=f"outbox-dlq:{row.id}",
        alert_type="outbox_dead_letter",
        priority="high",
        entity_type="outbox_event",
        entity_id=row.id,
        title="Outbox event moved to dead-letter",
        channel="dashboard",
        status="pending",
    )
    db.add(alert)
    await db.commit()
    row_id = row.id
    alert_id = alert.id

    url = f"/api/v1/outbox-events/{row_id}/replay"
    payload = {"reason": "Contrato upstream corrigido e validado."}
    first, second = await asyncio.gather(
        async_client.post(url, headers=auth_headers, json=payload),
        async_client.post(url, headers=auth_headers, json=payload),
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    replies = [first.json(), second.json()]
    assert sorted(reply["replayed"] for reply in replies) == [False, True]
    replayed = next(reply for reply in replies if reply["replayed"])
    assert replayed["event"]["status"] == "pending"
    assert replayed["event"]["attempt_count"] == 0
    assert replayed["event"]["last_error"] is None

    db.expire_all()
    persisted = await db.get(OutboxEvent, row_id)
    persisted_alert = await db.get(Alert, alert_id)
    audits = (
        (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.entity_type == "outbox_event",
                    AuditLog.entity_id == row_id,
                    AuditLog.action == "outbox.dead_letter_replayed",
                )
            )
        )
        .scalars()
        .all()
    )
    assert persisted is not None
    assert persisted.status == "pending"
    assert persisted_alert is not None
    assert persisted_alert.status == "dismissed"
    assert len(audits) == 1
    assert audits[0].new_values["reason"] == payload["reason"]


@pytest.mark.asyncio
async def test_sent_event_cannot_be_replayed(async_client, db, tenant_id, auth_headers):
    row = _row(tenant_id, status="sent", attempt_count=1)
    db.add(row)
    await db.commit()

    response = await async_client.post(
        f"/api/v1/outbox-events/{row.id}/replay",
        headers=auth_headers,
        json={"reason": "Tentativa operacional não permitida."},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "outbox_event_not_replayable"


@pytest.mark.asyncio
async def test_reconciliation_reports_due_and_dead_letter_counts(
    async_client, db, tenant_id, auth_headers
):
    db.add_all(
        [
            _row(tenant_id, status="pending"),
            _row(tenant_id, status="dead_letter", attempt_count=6),
            _row(tenant_id, status="sent", attempt_count=1),
        ]
    )
    await db.commit()

    response = await async_client.get(
        "/api/v1/outbox-events/reconciliation",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["health"] == "red"
    assert body["metrics"]["pending_due"] >= 1
    assert body["metrics"]["dead_letter"] >= 1


@pytest.mark.asyncio
async def test_drain_creates_single_high_priority_dead_letter_alert(
    monkeypatch, db, tenant_id
):
    row = _row(tenant_id, status="pending")
    row.created_at = datetime(2000, 1, 1, tzinfo=UTC)
    db.add(row)
    await db.commit()
    row_id = row.id

    monkeypatch.setattr(
        outbox_service,
        "get_settings",
        lambda: SimpleNamespace(ff_governance_outbox=True),
    )

    async def terminal_failure(_row):
        return False, None, "client_error_422"

    monkeypatch.setattr(outbox_service, "_post_to_governance", terminal_failure)

    counts = await outbox_service.drain_outbox(db)
    alert = await db.scalar(
        select(Alert).where(
            Alert.tenant_id == tenant_id,
            Alert.request_reference == f"outbox-dlq:{row_id}",
        )
    )

    assert counts["dead_letter"] >= 1
    assert counts["alerts_created"] >= 1
    assert alert is not None
    assert alert.priority == "high"
    assert alert.status == "pending"
