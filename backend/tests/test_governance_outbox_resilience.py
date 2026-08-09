import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.core.passwords import hash_password
from app.database import AdminSessionLocal, AsyncSessionLocal
from app.modules.outbox import service
from app.modules.outbox.models import OutboxEvent
from app.modules.platform.models import PlatformAuditLog, PlatformUser


@pytest.fixture(autouse=True)
async def isolate_outbox_rows():
    async with AdminSessionLocal() as session:
        await session.execute(delete(OutboxEvent))
        await session.commit()
    yield
    async with AdminSessionLocal() as session:
        await session.execute(delete(OutboxEvent))
        await session.commit()


def _enabled_settings() -> SimpleNamespace:
    return SimpleNamespace(
        ff_governance_outbox=True,
        governance_engine_url="https://governance.internal",
        governance_api_key="secret",
    )


async def _insert_event(
    tenant_id,
    *,
    status: str = "pending",
    attempt_count: int = 0,
    next_attempt_at: datetime | None = None,
    claim_expires_at: datetime | None = None,
) -> OutboxEvent:
    async with AdminSessionLocal() as session:
        row = OutboxEvent(
            id=uuid4(),
            tenant_id=tenant_id,
            aggregate_type="operational_exception",
            aggregate_id=uuid4(),
            event_type="vehicle.breakdown",
            payload={
                "event_type": "vehicle.breakdown",
                "severity": "alta",
                "title": "Avaria",
                "occurred_at": datetime.now(UTC).isoformat(),
                "entities": [],
                "idempotency_key": f"rotas:test:{uuid4()}",
            },
            status=status,
            attempt_count=attempt_count,
            total_attempt_count=attempt_count,
            next_attempt_at=next_attempt_at or datetime.now(UTC) - timedelta(seconds=1),
            claimed_at=(datetime.now(UTC) - timedelta(minutes=5)) if status == "processing" else None,
            claim_expires_at=claim_expires_at,
            claimed_by="dead-worker" if status == "processing" else None,
            dead_lettered_at=datetime.now(UTC) if status == "dead_letter" else None,
            sent_at=datetime.now(UTC) if status == "sent" else None,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row


async def _platform_headers(client, role: str) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    password = f"Outbox$Secret{suffix}"
    async with AsyncSessionLocal() as session:
        user = PlatformUser(
            email=f"outbox-{role}-{suffix}@test.local",
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
    response = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": user.email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_concurrent_drainers_deliver_claim_only_once(monkeypatch, tenant_id) -> None:
    row = await _insert_event(tenant_id)
    entered_delivery = asyncio.Event()
    release_delivery = asyncio.Event()
    delivery_ids: list = []

    async def delayed_success(event):
        delivery_ids.append(event.id)
        entered_delivery.set()
        await release_delivery.wait()
        return True, {"occurrence_id": str(uuid4())}, None

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_post_to_governance", delayed_success)

    async with AdminSessionLocal() as first, AdminSessionLocal() as second:
        first_task = asyncio.create_task(service.drain_outbox(first, worker_id="worker-a", lease_seconds=60))
        await asyncio.wait_for(entered_delivery.wait(), timeout=5)
        second_counts = await service.drain_outbox(
            second,
            worker_id="worker-b",
            lease_seconds=60,
        )
        release_delivery.set()
        first_counts = await first_task

    assert delivery_ids == [row.id]
    assert first_counts["sent"] == 1
    assert second_counts["scanned"] == 0


@pytest.mark.asyncio
async def test_transient_failure_uses_first_backoff_slot(monkeypatch, tenant_id) -> None:
    fixed_now = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    row = await _insert_event(tenant_id, next_attempt_at=fixed_now - timedelta(seconds=1))

    async def transient_failure(_event):
        return False, None, "upstream_503"

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(service, "_post_to_governance", transient_failure)

    async with AdminSessionLocal() as session:
        counts = await service.drain_outbox(session, worker_id="retry-worker")
        persisted = await session.get(OutboxEvent, row.id)

    assert counts["retried"] == 1
    assert persisted is not None
    assert persisted.status == "pending"
    assert persisted.attempt_count == 1
    assert persisted.next_attempt_at == fixed_now + timedelta(seconds=60)


@pytest.mark.asyncio
async def test_terminal_4xx_moves_directly_to_dead_letter(monkeypatch, tenant_id) -> None:
    row = await _insert_event(tenant_id)

    async def terminal_failure(_event):
        return False, None, "client_error_422"

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_post_to_governance", terminal_failure)

    async with AdminSessionLocal() as session:
        counts = await service.drain_outbox(session, worker_id="terminal-worker")
        persisted = await session.get(OutboxEvent, row.id)

    assert counts["dead_letter"] == 1
    assert persisted is not None
    assert persisted.status == "dead_letter"
    assert persisted.attempt_count == 1
    assert persisted.dead_lettered_at is not None


@pytest.mark.asyncio
async def test_expired_claim_is_reclaimed(monkeypatch, tenant_id) -> None:
    row = await _insert_event(
        tenant_id,
        status="processing",
        claim_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    async def success(_event):
        return True, {"occurrence_id": str(uuid4())}, None

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_post_to_governance", success)

    async with AdminSessionLocal() as session:
        counts = await service.drain_outbox(session, worker_id="recovery-worker")
        persisted = await session.get(OutboxEvent, row.id)

    assert counts["reclaimed"] == 1
    assert counts["sent"] == 1
    assert persisted is not None
    assert persisted.status == "sent"
    assert persisted.claimed_by is None


@pytest.mark.asyncio
async def test_legacy_processing_claim_without_expiry_is_reclaimed(monkeypatch, tenant_id) -> None:
    row = await _insert_event(
        tenant_id,
        status="processing",
        claim_expires_at=None,
    )

    async def success(_event):
        return True, {"occurrence_id": str(uuid4())}, None

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_post_to_governance", success)

    async with AdminSessionLocal() as session:
        counts = await service.drain_outbox(session, worker_id="legacy-recovery-worker")
        persisted = await session.get(OutboxEvent, row.id)

    assert counts["reclaimed"] == 1
    assert counts["sent"] == 1
    assert persisted is not None
    assert persisted.status == "sent"
    assert persisted.claimed_by is None


@pytest.mark.asyncio
async def test_dead_letter_replay_preserves_operator_provenance(tenant_id) -> None:
    row = await _insert_event(tenant_id, status="dead_letter", attempt_count=6)
    operator_id = uuid4()
    async with AdminSessionLocal() as session:
        replayed = await service.replay_dead_letter(
            session,
            event_id=row.id,
            operator_id=operator_id,
            operator_role="platform_admin",
            reason="Contrato corrigido e validado pelo operador.",
        )
        audit = await session.scalar(
            select(PlatformAuditLog).where(
                PlatformAuditLog.action == "governance_outbox.replay",
                PlatformAuditLog.resource_id == row.id,
            )
        )

    assert replayed.status == "pending"
    assert replayed.attempt_count == 0
    assert replayed.total_attempt_count == 6
    assert replayed.replay_count == 1
    assert replayed.replayed_by == str(operator_id)
    assert replayed.replay_reason is not None
    assert replayed.replay_reason.startswith("Contrato corrigido")
    assert replayed.dead_lettered_at is None
    assert audit is not None
    assert audit.actor_id == operator_id
    assert audit.target_tenant_id == tenant_id
    assert audit.payload is not None
    assert audit.payload["previous_attempt_count"] == 6


@pytest.mark.asyncio
async def test_reconciliation_records_governance_receipt(monkeypatch, tenant_id) -> None:
    row = await _insert_event(tenant_id, status="sent")
    occurrence_id = uuid4()
    case_id = uuid4()

    async def receipt(_event):
        return True, {"occurrence_id": str(occurrence_id), "case_id": str(case_id)}, None

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_get_governance_receipt", receipt)

    async with AdminSessionLocal() as session:
        counts = await service.reconcile_outbox(session)
        persisted = await session.get(OutboxEvent, row.id)

    assert counts["confirmed"] >= 1
    assert persisted is not None
    assert persisted.governance_occurrence_id == occurrence_id
    assert persisted.governance_case_id == case_id
    assert persisted.reconciled_at is not None


@pytest.mark.asyncio
async def test_missing_receipt_is_rescheduled_without_reconciliation_stampede(monkeypatch, tenant_id) -> None:
    fixed_now = datetime(2026, 8, 9, 20, 0, tzinfo=UTC)
    row = await _insert_event(tenant_id, status="sent")

    async def missing_receipt(_event):
        return False, None, "receipt_not_found"

    monkeypatch.setattr(service, "get_settings", _enabled_settings)
    monkeypatch.setattr(service, "_utcnow", lambda: fixed_now)
    monkeypatch.setattr(service, "_get_governance_receipt", missing_receipt)

    async with AdminSessionLocal() as session:
        first = await service.reconcile_outbox(session)
        second = await service.reconcile_outbox(session)
        persisted = await session.get(OutboxEvent, row.id)

    assert first["missing"] == 1
    assert second["scanned"] == 0
    assert persisted is not None
    assert persisted.reconciliation_attempt_count == 1
    assert persisted.next_reconciliation_at == fixed_now + timedelta(seconds=60)
    assert persisted.claimed_by is None


@pytest.mark.asyncio
async def test_platform_outbox_api_separates_read_and_replay_roles(async_client, tenant_id) -> None:
    row = await _insert_event(tenant_id, status="dead_letter", attempt_count=6)
    support_headers = await _platform_headers(async_client, "platform_support")
    admin_headers = await _platform_headers(async_client, "platform_admin")

    listing = await async_client.get(
        "/api/v1/platform/outbox/dead-letters",
        params={"tenant_id": str(tenant_id)},
        headers=support_headers,
    )
    forbidden = await async_client.post(
        f"/api/v1/platform/outbox/{row.id}/replay",
        json={"reason": "Contrato corrigido pelo suporte."},
        headers=support_headers,
    )
    replayed = await async_client.post(
        f"/api/v1/platform/outbox/{row.id}/replay",
        json={"reason": "Contrato corrigido e aprovado pelo administrador."},
        headers=admin_headers,
    )

    assert listing.status_code == 200
    assert listing.json()[0]["id"] == str(row.id)
    assert "payload" not in listing.json()[0]
    assert forbidden.status_code == 403
    assert replayed.status_code == 200
    assert replayed.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_tenant_token_cannot_access_platform_outbox(async_client, auth_headers) -> None:
    response = await async_client.get(
        "/api/v1/platform/outbox/health",
        headers=auth_headers,
    )

    assert response.status_code in {401, 403}
