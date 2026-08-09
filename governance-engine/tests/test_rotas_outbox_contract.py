import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
from httpx import ASGITransport

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.outbox import service as outbox_service  # noqa: E402
from app.modules.outbox.models import OutboxEvent  # noqa: E402

from main import app as governance_app  # noqa: E402


async def test_rotas_outbox_reaches_real_governance_adapter(
    monkeypatch, api_key_raw, tenant_id
) -> None:
    real_async_client = httpx.AsyncClient
    transport = ASGITransport(app=governance_app)
    async with real_async_client(
        transport=transport,
        base_url="http://governance.internal",
        headers={"X-API-Key": api_key_raw},
    ) as client:
        bootstrap = await client.post(
            "/api/v1/adapters/rotas/bootstrap",
            json={
                "tenant_id": str(tenant_id),
                "tenant_name": "Contract tenant",
                "tenant_slug": f"contract-{tenant_id.hex[:8]}",
            },
        )
    assert bootstrap.status_code == 200, bootstrap.text

    monkeypatch.setattr(
        outbox_service,
        "get_settings",
        lambda: SimpleNamespace(
            governance_engine_url="http://governance.internal",
            governance_api_key=api_key_raw,
        ),
    )

    def governance_client_factory(**_kwargs):
        return real_async_client(
            transport=ASGITransport(app=governance_app),
            base_url="http://governance.internal",
        )

    monkeypatch.setattr(outbox_service.httpx, "AsyncClient", governance_client_factory)

    event_id = uuid4()
    idempotency_key = f"rotas:contract:{event_id}"
    row = OutboxEvent(
        id=event_id,
        tenant_id=tenant_id,
        aggregate_type="operational_exception",
        aggregate_id=uuid4(),
        event_type="vehicle.breakdown",
        payload={
            "event_type": "vehicle.breakdown",
            "severity": "alta",
            "title": "Contract test breakdown",
            "description": "End-to-end ASGI contract verification.",
            "occurred_at": datetime.now(UTC).isoformat(),
            "entities": [
                {
                    "entity_type": "vehicle",
                    "external_id": str(uuid4()),
                    "role": "sujeito",
                    "display_name": "MZ-PR-13",
                    "snapshot": {"plate": "MZ-PR-13"},
                }
            ],
            "idempotency_key": idempotency_key,
            "payload": {"contract_test": True},
        },
        status="pending",
        attempt_count=0,
        created_at=datetime.now(UTC),
    )

    first_ok, first_body, first_error = await outbox_service._post_to_governance(row)
    replay_ok, replay_body, replay_error = await outbox_service._post_to_governance(row)

    assert first_ok is True
    assert first_error is None
    assert first_body is not None
    assert first_body["numero"].startswith("EVT-")
    assert first_body["case_id"] is not None
    assert replay_ok is True
    assert replay_error is None
    assert replay_body is not None
    assert replay_body["occurrence_id"] == first_body["occurrence_id"]
