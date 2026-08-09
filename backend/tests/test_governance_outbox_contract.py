from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

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
            "description": "Viatura imobilizada.",
            "occurred_at": datetime.now(UTC).isoformat(),
            "entities": [],
            "idempotency_key": f"rotas:event:{event_id}",
        },
        status="pending",
        attempt_count=0,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_governance_delivery_uses_canonical_adapter_contract(monkeypatch) -> None:
    capture: dict = {}
    response = _Response(
        201,
        {
            "occurrence_id": str(uuid4()),
            "numero": "EVT-2026-000001",
            "case_id": str(uuid4()),
            "case_reference": "CASE-2026-000001",
        },
    )
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
    assert capture["body"]["payload"]["outbox_event_id"]


@pytest.mark.asyncio
async def test_governance_idempotency_conflict_is_delivery_success(monkeypatch) -> None:
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

    assert await service._post_to_governance(_event()) == (True, {}, None)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 425, 429, 500, 503])
async def test_transient_governance_response_remains_retryable(monkeypatch, status_code) -> None:
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
        lambda **_kwargs: _Client(_Response(status_code), {}),
    )

    assert await service._post_to_governance(_event()) == (
        False,
        None,
        f"upstream_{status_code}",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
async def test_terminal_governance_contract_response_is_not_success(monkeypatch, status_code) -> None:
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
        lambda **_kwargs: _Client(_Response(status_code), {}),
    )

    assert await service._post_to_governance(_event()) == (
        False,
        None,
        f"client_error_{status_code}",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("url", "api_key", "expected_error"),
    [
        ("", "secret", "governance_engine_url not configured"),
        ("https://governance.internal", "", "governance_api_key not configured"),
    ],
)
async def test_governance_configuration_fails_closed(monkeypatch, url, api_key, expected_error) -> None:
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(governance_engine_url=url, governance_api_key=api_key),
    )

    assert await service._post_to_governance(_event()) == (False, None, expected_error)
