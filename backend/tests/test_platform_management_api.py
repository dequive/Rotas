"""Platform management API tests (Phase 25 — Plan 02).

8 tests covering the 8 platform management endpoints:
  1. platform_admin can list tenants
  2. platform_billing can list tenants
  3. platform_admin can suspend and reactivate a tenant
  4. platform_support cannot suspend a tenant (403)
  5. platform_billing cannot change plan (403)
  6. platform_admin can change plan
  7. platform_support cannot list platform users (403)
  8. Suspend creates an audit log entry visible via GET /audit-log
"""

from uuid import uuid4

import httpx
import pytest

from app.core.passwords import hash_password
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.platform.models import PlatformUser
from app.modules.tenants.models import Tenant

import_all_models()


# ── helpers ────────────────────────────────────────────────────────────────────


async def _make_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def _create_platform_user(role: str, suffix: str) -> tuple[PlatformUser, str]:
    """Insert a PlatformUser into the DB and return (user, cleartext_password)."""
    password = f"Mgmt$Secret{suffix}"
    async with AsyncSessionLocal() as db:
        user = PlatformUser(
            email=f"mgmt-{role}-{suffix}@test.local",
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user, password


async def _create_tenant(suffix: str) -> Tenant:
    """Insert a Tenant and return the ORM object."""
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Mgmt Test Tenant {suffix}",
            slug=f"mgmt-{suffix}",
        )
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


async def _login_platform(client: httpx.AsyncClient, email: str, password: str) -> dict:
    """POST /platform/auth/login and return Authorization header dict."""
    resp = await client.post(
        "/api/v1/platform/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Platform login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


# ── tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_platform_admin_can_list_tenants() -> None:
    """GET /platform/tenants with platform_admin returns 200 and a list."""
    suffix = uuid4().hex[:8]
    admin_user, admin_pw = await _create_platform_user("platform_admin", suffix)
    await _create_tenant(f"a-{suffix}")
    await _create_tenant(f"b-{suffix}")

    async with await _make_client() as client:
        headers = await _login_platform(client, admin_user.email, admin_pw)
        resp = await client.get("/api/v1/platform/tenants", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 2
    slugs = {t["slug"] for t in body}
    assert f"mgmt-a-{suffix}" in slugs
    assert f"mgmt-b-{suffix}" in slugs


@pytest.mark.asyncio
async def test_platform_billing_can_list_tenants() -> None:
    """GET /platform/tenants with platform_billing also returns 200."""
    suffix = uuid4().hex[:8]
    billing_user, billing_pw = await _create_platform_user("platform_billing", suffix)

    async with await _make_client() as client:
        headers = await _login_platform(client, billing_user.email, billing_pw)
        resp = await client.get("/api/v1/platform/tenants", headers=headers)

    assert resp.status_code == 200, resp.text
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_platform_admin_can_suspend_and_reactivate_tenant() -> None:
    """POST suspend sets is_active=False; POST reactivate sets it back to True."""
    suffix = uuid4().hex[:8]
    admin_user, admin_pw = await _create_platform_user("platform_admin", suffix)
    tenant = await _create_tenant(suffix)
    tid = str(tenant.id)

    async with await _make_client() as client:
        headers = await _login_platform(client, admin_user.email, admin_pw)

        # Suspend
        resp = await client.post(f"/api/v1/platform/tenants/{tid}/suspend", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_active"] is False

        # Verify via GET detail
        resp = await client.get(f"/api/v1/platform/tenants/{tid}", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_active"] is False

        # Reactivate
        resp = await client.post(f"/api/v1/platform/tenants/{tid}/reactivate", headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_platform_support_cannot_suspend_tenant() -> None:
    """platform_support POST /suspend must return 403."""
    suffix = uuid4().hex[:8]
    support_user, support_pw = await _create_platform_user("platform_support", suffix)
    tenant = await _create_tenant(suffix)

    async with await _make_client() as client:
        headers = await _login_platform(client, support_user.email, support_pw)
        resp = await client.post(
            f"/api/v1/platform/tenants/{tenant.id}/suspend",
            headers=headers,
        )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_platform_billing_cannot_change_plan() -> None:
    """platform_billing PATCH /plan must return 403."""
    suffix = uuid4().hex[:8]
    billing_user, billing_pw = await _create_platform_user("platform_billing", suffix)
    tenant = await _create_tenant(suffix)

    async with await _make_client() as client:
        headers = await _login_platform(client, billing_user.email, billing_pw)
        resp = await client.patch(
            f"/api/v1/platform/tenants/{tenant.id}/plan",
            json={"plan": "enterprise"},
            headers=headers,
        )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_platform_admin_can_change_plan() -> None:
    """platform_admin PATCH /plan returns 200 and tenant.plan is updated."""
    suffix = uuid4().hex[:8]
    admin_user, admin_pw = await _create_platform_user("platform_admin", suffix)
    tenant = await _create_tenant(suffix)
    tid = str(tenant.id)

    async with await _make_client() as client:
        headers = await _login_platform(client, admin_user.email, admin_pw)
        resp = await client.patch(
            f"/api/v1/platform/tenants/{tid}/plan",
            json={"plan": "enterprise"},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["plan"] == "enterprise"


@pytest.mark.asyncio
async def test_platform_support_cannot_list_platform_users() -> None:
    """platform_support GET /platform-users must return 403."""
    suffix = uuid4().hex[:8]
    support_user, support_pw = await _create_platform_user("platform_support", suffix)

    async with await _make_client() as client:
        headers = await _login_platform(client, support_user.email, support_pw)
        resp = await client.get("/api/v1/platform/platform-users", headers=headers)

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_suspend_creates_audit_log_entry() -> None:
    """Suspending a tenant creates a platform_audit_logs row with action='tenant.suspend'."""
    suffix = uuid4().hex[:8]
    admin_user, admin_pw = await _create_platform_user("platform_admin", suffix)
    tenant = await _create_tenant(suffix)
    tid = str(tenant.id)

    async with await _make_client() as client:
        headers = await _login_platform(client, admin_user.email, admin_pw)

        # Suspend
        resp = await client.post(f"/api/v1/platform/tenants/{tid}/suspend", headers=headers)
        assert resp.status_code == 200, resp.text

        # Read audit log
        resp = await client.get(
            f"/api/v1/platform/tenants/{tid}/audit-log",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        entries = resp.json()
        assert isinstance(entries, list)
        assert len(entries) >= 1
        actions = [e["action"] for e in entries]
        assert "tenant.suspend" in actions, f"Expected tenant.suspend in {actions}"

        # Cleanup: reactivate so other tests that use the same DB aren't affected
        await client.post(f"/api/v1/platform/tenants/{tid}/reactivate", headers=headers)
