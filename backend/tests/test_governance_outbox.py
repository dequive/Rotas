from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.outbox import service
from app.modules.outbox.models import OutboxEvent


class _Response:
    def __init__(self, status_code: int, body: dict | None = None):
        self.status_code = status_code
        self._body = body or {}

    def json(self) -> dict:
        return self._body


class _Client:
    def __init__(self, response: _Response, capture: dict):
        self._response = response
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url: str, *, headers: dict, json: dict):
        self._capture.update(url=url, headers=headers, body=json)
        return self._response


class _ArqRedis:
    def __init__(self):
        self.calls: list[tuple[tuple, dict]] = []

    async def enqueue_job(self, *args, **kwargs):
        self.calls.append((args, kwargs))


def _event() -> OutboxEvent:
    event_id = uuid4()
    return OutboxEvent(
        id=event_id,
        tenant_id=uuid4(),
        aggregate_type="operational_exception",
        aggregate_id=uuid4(),
        event_type="vehicle.breakdown",
        payload={
            "event_type": "vehicle.breakdown",
            "severity": "alta",
            "title": "Avaria",
            "occurred_at": datetime.now(UTC).isoformat(),
            "entities": [],
            "idempotency_key": f"rotas:event:{event_id}",
        },
        status="pending",
        attempt_count=0,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_governance_delivery_uses_canonical_adapter_contract(monkeypatch):
    capture: dict = {}
    response = _Response(201, {"case_id": str(uuid4())})
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            governance_engine_url="https://governance.internal/",
            governance_api_key="secret",
        ),
    )
    monkeypatch.setattr(
        service.httpx,
        "AsyncClient",
        lambda **_kwargs: _Client(response, capture),
    )

    ok, body, error = await service._post_to_governance(_event())

    assert ok is True
    assert error is None
    assert body == response._body
    assert capture["url"] == "https://governance.internal/api/v1/adapters/rotas/events"
    assert capture["headers"]["X-API-Key"] == "secret"
    assert "Authorization" not in capture["headers"]
    assert capture["body"]["idempotency_key"].startswith("rotas:event:")


@pytest.mark.asyncio
async def test_governance_idempotency_replay_is_success(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            governance_engine_url="https://governance.internal",
            governance_api_key="secret",
        ),
    )
    monkeypatch.setattr(
        service.httpx,
        "AsyncClient",
        lambda **_kwargs: _Client(_Response(409), {}),
    )

    ok, body, error = await service._post_to_governance(_event())

    assert (ok, body, error) == (True, {}, None)


@pytest.mark.asyncio
async def test_governance_contract_failure_is_terminal(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(
            governance_engine_url="https://governance.internal",
            governance_api_key="secret",
        ),
    )
    monkeypatch.setattr(
        service.httpx,
        "AsyncClient",
        lambda **_kwargs: _Client(_Response(422), {}),
    )

    ok, body, error = await service._post_to_governance(_event())

    assert ok is False
    assert body is None
    assert error == "client_error_422"


@pytest.mark.asyncio
async def test_internal_outbox_failure_isolated_by_savepoint(monkeypatch, db, tenant_id):
    successful = OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type="work_order",
        aggregate_id=uuid4(),
        event_type="workshop.internal.test.success",
        payload={"work_order_id": str(uuid4())},
        status="pending",
        attempt_count=0,
    )
    failing = OutboxEvent(
        tenant_id=tenant_id,
        aggregate_type="work_order",
        aggregate_id=uuid4(),
        event_type="workshop.internal.test.failure",
        payload={"work_order_id": str(uuid4())},
        status="pending",
        attempt_count=0,
    )
    db.add_all([successful, failing])
    await db.commit()

    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(ff_governance_outbox=False),
    )

    async def fake_internal_handler(_session, row, _arq_redis=None):
        if row.id == successful.id:
            return True, {"id": str(row.aggregate_id)}, None
        return False, None, "simulated_failure"

    monkeypatch.setattr(service, "_process_internal_event", fake_internal_handler)

    counts = await service.drain_outbox(db)
    rows = (
        (
            await db.execute(
                select(OutboxEvent).where(OutboxEvent.id.in_([successful.id, failing.id]))
            )
        )
        .scalars()
        .all()
    )
    status_by_id = {row.id: row.status for row in rows}

    # Other tests may legitimately leave unrelated internal events pending in
    # the shared integration database; assert this batch's outcomes by ID.
    assert counts["sent"] >= 1
    assert counts["retried"] >= 1
    assert counts["dead_letter"] == 0
    assert status_by_id[successful.id] == "sent"
    assert status_by_id[failing.id] == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event_type", "payload", "task_name"),
    [
        (
            "billing.internal.export.dispatch",
            {
                "job_id": str(uuid4()),
                "document_id": str(uuid4()),
                "export_format": "pdf",
                "tenant_id": str(uuid4()),
            },
            "generate_billing_export",
        ),
        (
            "billing.internal.compliance_report.dispatch",
            {
                "job_id": str(uuid4()),
                "month": "2026-07",
                "tenant_id": str(uuid4()),
            },
            "task_export_compliance_report",
        ),
    ],
)
async def test_billing_internal_dispatch_uses_deterministic_arq_job_id(
    event_type, payload, task_name
):
    redis = _ArqRedis()
    row = OutboxEvent(
        id=uuid4(),
        tenant_id=uuid4(),
        aggregate_type="export_job",
        aggregate_id=uuid4(),
        event_type=event_type,
        payload=payload,
        status="pending",
        attempt_count=0,
        created_at=datetime.now(UTC),
    )

    ok, body, error = await service._process_internal_event(AsyncMock(), row, redis)

    assert ok is True
    assert error is None
    assert body == {"job_id": payload["job_id"]}
    assert len(redis.calls) == 1
    args, kwargs = redis.calls[0]
    assert args[0] == task_name
    assert kwargs["_job_id"] == f"outbox:{row.id}"


@pytest.mark.asyncio
async def test_billing_internal_dispatch_retries_when_arq_is_unavailable():
    row = OutboxEvent(
        id=uuid4(),
        tenant_id=uuid4(),
        aggregate_type="export_job",
        aggregate_id=uuid4(),
        event_type="billing.internal.export.dispatch",
        payload={
            "job_id": str(uuid4()),
            "document_id": str(uuid4()),
            "export_format": "xlsx",
            "tenant_id": str(uuid4()),
        },
        status="pending",
        attempt_count=0,
        created_at=datetime.now(UTC),
    )

    ok, body, error = await service._process_internal_event(AsyncMock(), row)

    assert ok is False
    assert body is None
    assert error == "arq_redis_unavailable"
