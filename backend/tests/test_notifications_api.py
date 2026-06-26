"""NOTIF-01/02/03: Notifications API integration tests.

Covers: enqueue, idempotency, conflict, list, get-by-id, cross-tenant 404.
Requires notification_outbox table (migrations applied).
"""

from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.tenants.models import Tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_tenant(suffix: str | None = None) -> Tenant:
    s = suffix or uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Notif {s}", slug=f"notif-{s}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


def _auth(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


def _client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _email_payload(ref: str | None = None, recipient: str | None = None) -> dict:
    return {
        "request_reference": ref or f"test-notif-{uuid4().hex[:12]}",
        "recipient": recipient or "dest@example.com",
        "subject": "Teste de notificacao",
        "body_text": "Corpo da mensagem de teste.",
    }


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_enqueue_email_returns_201():
    """POST /notifications/email with valid payload returns 201 and queued notification."""
    tenant = await _create_tenant()
    payload = _email_payload()

    async with _client() as c:
        resp = await c.post(
            "/api/v1/notifications/email",
            json=payload,
            headers=_auth(tenant.id),
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "queued"
    assert body["recipient"] == payload["recipient"]
    assert body["request_reference"] == payload["request_reference"]
    assert "id" in body


async def test_enqueue_email_idempotent_same_payload():
    """Sending the same request_reference + same payload twice returns the same notification."""
    tenant = await _create_tenant()
    payload = _email_payload()

    async with _client() as c:
        r1 = await c.post("/api/v1/notifications/email", json=payload, headers=_auth(tenant.id))
        r2 = await c.post("/api/v1/notifications/email", json=payload, headers=_auth(tenant.id))

    assert r1.status_code == 201, r1.text
    # Second call returns same record — status is 201 (new) or 200-range; id must match
    assert r2.status_code in (200, 201), r2.text
    assert r1.json()["id"] == r2.json()["id"]


async def test_enqueue_email_conflict_different_payload():
    """Same request_reference with different recipient returns 409."""
    tenant = await _create_tenant()
    ref = f"conflict-ref-{uuid4().hex[:8]}"

    async with _client() as c:
        r1 = await c.post(
            "/api/v1/notifications/email",
            json=_email_payload(ref=ref, recipient="first@example.com"),
            headers=_auth(tenant.id),
        )
        r2 = await c.post(
            "/api/v1/notifications/email",
            json=_email_payload(ref=ref, recipient="second@example.com"),
            headers=_auth(tenant.id),
        )

    assert r1.status_code == 201, r1.text
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "notification_request_reference_reused"


async def test_list_notifications():
    """GET /notifications returns list scoped to tenant including enqueued items."""
    tenant = await _create_tenant()

    async with _client() as c:
        await c.post(
            "/api/v1/notifications/email",
            json=_email_payload(),
            headers=_auth(tenant.id),
        )
        await c.post(
            "/api/v1/notifications/email",
            json=_email_payload(),
            headers=_auth(tenant.id),
        )
        resp = await c.get("/api/v1/notifications", headers=_auth(tenant.id))

    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list)
    assert len(items) >= 2


async def test_list_notifications_filter_by_status():
    """GET /notifications?status=queued returns only queued notifications."""
    tenant = await _create_tenant()
    payload = _email_payload()

    async with _client() as c:
        enq = await c.post("/api/v1/notifications/email", json=payload, headers=_auth(tenant.id))
        assert enq.status_code == 201

        resp = await c.get(
            "/api/v1/notifications",
            params={"status": "queued"},
            headers=_auth(tenant.id),
        )

    assert resp.status_code == 200, resp.text
    items = resp.json()
    notif_id = enq.json()["id"]
    ids = [i["id"] for i in items]
    assert notif_id in ids
    assert all(i["status"] == "queued" for i in items)


async def test_get_notification_cross_tenant_returns_404():
    """Tenant B cannot retrieve a notification created by tenant A."""
    tenant_a = await _create_tenant("a-" + uuid4().hex[:6])
    tenant_b = await _create_tenant("b-" + uuid4().hex[:6])

    async with _client() as c:
        create_resp = await c.post(
            "/api/v1/notifications/email",
            json=_email_payload(),
            headers=_auth(tenant_a.id),
        )
        assert create_resp.status_code == 201, create_resp.text
        notif_id = create_resp.json()["id"]

        # Tenant B tries to read tenant A's notification
        get_resp = await c.get(
            f"/api/v1/notifications/{notif_id}",
            headers=_auth(tenant_b.id),
        )

    assert get_resp.status_code == 404, get_resp.text
    assert get_resp.json()["error"]["code"] == "notification_not_found"
