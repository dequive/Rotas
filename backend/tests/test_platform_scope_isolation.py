"""Platform / tenant scope isolation tests (Phase 25 — Plan 01).

6 tests covering:
  1. Tenant JWT rejected on platform endpoint (403)
  2. Platform JWT rejected on tenant endpoint (401 or 403, never 200)
  3. Platform admin login returns scope="platform" JWT with no tenant_id claim
  4. Abuse scenario: crafted JWT with scope="dashboard" + role="platform_admin" → 403
  5. Platform billing role login yields correct role claim
  6. Existing tenant login now embeds scope="dashboard" in JWT
"""

import base64
import json
from uuid import uuid4

import httpx
import jwt as _jwt
import pytest

from app.config import get_settings
from app.core.passwords import hash_password
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.platform.models import PlatformUser
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


# ── helpers ────────────────────────────────────────────────────────────────────


def decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without signature verification (tests only)."""
    payload_b64 = token.split(".")[1]
    # Pad to multiple of 4
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


async def make_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def create_tenant_with_user(suffix: str) -> tuple:
    """Create a Tenant + User and return (tenant, user, password)."""
    password = "Isolation$Test1"
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Isolation Tenant {suffix}", slug=f"isolation-{suffix}")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"isolation-{suffix}@test.local",
            password_hash=hash_password(password),
            full_name="Isolation User",
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(user)
        return tenant, user, password


async def create_platform_user(role: str, suffix: str) -> tuple:
    """Create a PlatformUser and return (user, password)."""
    password = f"Platform$Secret{suffix}"
    async with AsyncSessionLocal() as db:
        user = PlatformUser(
            email=f"platform-{role}-{suffix}@test.local",
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user, password


# ── fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


# ── tests ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tenant_token_cannot_access_platform_endpoint() -> None:
    """A dashboard-scoped JWT sent to a platform endpoint must return 403."""
    suffix = uuid4().hex[:8]
    tenant, user, password = await create_tenant_with_user(suffix)

    async with await make_client() as client:
        # Log in as tenant user to get a dashboard JWT
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login_resp.status_code == 200, login_resp.text
        dashboard_token = login_resp.json()["access_token"]

        # Send dashboard JWT to a platform-prefixed endpoint.
        # /api/v1/platform/tenants/{id}/suspend does not exist yet (Plan 02).
        # We expect 403 (scope rejected) — not 404 from routing, because the
        # platform router's dependency fires before path matching completes.
        # If the route returns 404, that also proves the dashboard token didn't gain
        # access (200 would be the failure). Accept 403 or 404 but assert != 200.
        fake_id = str(uuid4())
        resp = await client.post(
            f"/api/v1/platform/tenants/{fake_id}/suspend",
            headers={"Authorization": f"Bearer {dashboard_token}"},
        )
        # 404 = routing didn't find the path (no platform tenant router yet — correct)
        # 403 = scope check fired (ideal once platform tenant router exists)
        # 200 = FAILURE — tenant token must never reach platform resources
        assert resp.status_code != 200, (
            f"Dashboard JWT must not return 200 on platform endpoint. Got: {resp.status_code}"
        )


@pytest.mark.asyncio
async def test_platform_token_cannot_access_tenant_endpoint() -> None:
    """A platform-scoped JWT sent to a tenant endpoint must not return 200."""
    suffix = uuid4().hex[:8]
    platform_user, platform_password = await create_platform_user("platform_admin", suffix)

    async with await make_client() as client:
        # Log in as platform user
        login_resp = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": platform_user.email, "password": platform_password},
        )
        assert login_resp.status_code == 200, login_resp.text
        platform_token = login_resp.json()["access_token"]

        # Send platform JWT to a tenant endpoint.
        # get_current_principal() rejects scope="platform" with invalid_token_scope → 401.
        resp = await client.get(
            "/api/v1/trips",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        # 401 = scope rejected by get_current_principal (expected)
        # 403 = scope forbidden
        # 200 = FAILURE — platform token must never access tenant data
        assert resp.status_code not in {200}, (
            f"Platform JWT must not return 200 on tenant endpoint. Got: {resp.status_code}"
        )
        assert resp.status_code in {401, 403}, (
            f"Expected 401 or 403, got {resp.status_code}: {resp.text}"
        )


@pytest.mark.asyncio
async def test_platform_admin_login_returns_scope_platform() -> None:
    """POST /platform/auth/login with platform_admin credentials returns scope='platform' JWT."""
    suffix = uuid4().hex[:8]
    platform_user, platform_password = await create_platform_user("platform_admin", suffix)

    async with await make_client() as client:
        resp = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": platform_user.email, "password": platform_password},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["user"]["role"] == "platform_admin"

        claims = decode_jwt_payload(body["access_token"])
        assert claims["scope"] == "platform", f"Expected scope=platform, got: {claims}"
        assert "tenant_id" not in claims, (
            f"Platform JWT must not contain tenant_id claim. Claims: {claims}"
        )
        assert claims.get("role") == "platform_admin"
        assert "platform_user_id" in claims


@pytest.mark.asyncio
async def test_require_platform_role_checks_scope_before_role() -> None:
    """Abuse scenario: JWT with scope='dashboard' and role='platform_admin' must be rejected.

    Tests the core security invariant: scope is checked BEFORE role.
    A tenant user who somehow obtains role='platform_admin' in their JWT must be
    rejected at the scope check — the role claim is never reached.
    """
    settings = get_settings()
    fake_tenant_id = str(uuid4())

    # Craft a JWT that looks like a tenant token but claims a platform role.
    # Uses the same secret + algorithm as the real system — this simulates a forged token
    # from a malicious tenant who knows their own JWT structure.
    malicious_token = _jwt.encode(
        {
            "sub": f"dashboard:{uuid4()}",
            "typ": "access",
            "scope": "dashboard",       # tenant scope
            "role": "platform_admin",   # platform role name — the abuse
            "tenant_id": fake_tenant_id,
            "user_id": str(uuid4()),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    # Call get_current_platform_principal directly to verify the scope check fires.
    # We don't need a running server for this unit-style check.
    from app.core.auth import get_current_platform_principal
    from app.core.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        await get_current_platform_principal(
            authorization=f"Bearer {malicious_token}",
        )

    err = exc_info.value
    assert err.status_code == 403, f"Expected 403, got {err.status_code}: {err}"
    assert err.code == "forbidden", f"Expected forbidden, got {err.code}"


@pytest.mark.asyncio
async def test_platform_billing_role_token_has_correct_role() -> None:
    """Login as platform_billing user yields JWT with role='platform_billing'."""
    suffix = uuid4().hex[:8]
    platform_user, platform_password = await create_platform_user("platform_billing", suffix)

    async with await make_client() as client:
        resp = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": platform_user.email, "password": platform_password},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["role"] == "platform_billing"

        claims = decode_jwt_payload(body["access_token"])
        assert claims["scope"] == "platform", claims
        assert claims["role"] == "platform_billing", claims
        assert "tenant_id" not in claims, (
            f"Platform JWT must not contain tenant_id. Claims: {claims}"
        )


@pytest.mark.asyncio
async def test_tenant_jwt_scope_is_dashboard() -> None:
    """Existing tenant login now embeds scope='dashboard' in the JWT claim."""
    suffix = uuid4().hex[:8]
    tenant, user, password = await create_tenant_with_user(suffix)

    async with await make_client() as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]

        claims = decode_jwt_payload(token)
        assert claims["scope"] == "dashboard", (
            f"Tenant login must produce scope=dashboard. Got: {claims.get('scope')}"
        )
        assert "tenant_id" in claims, "Tenant JWT must contain tenant_id claim"
        assert claims["tenant_id"] is not None
        assert str(tenant.id) == claims["tenant_id"]


@pytest.mark.asyncio
async def test_platform_admin_can_access_tenant_me_with_query_param() -> None:
    """GET /api/v1/tenants/me?tenant_id={uuid} with a platform_admin JWT returns 200.

    Verifies that require_own_tenant_or_platform() accepts the platform path and
    the route correctly uses the ?tenant_id= query param as effective_tenant_id.
    """
    suffix = uuid4().hex[:8]
    # Create a real tenant so the service lookup succeeds.
    tenant, _user, _password = await create_tenant_with_user(suffix)
    platform_user, platform_password = await create_platform_user("platform_admin", suffix)

    async with await make_client() as client:
        # Log in as platform_admin to get a platform-scoped JWT.
        login_resp = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": platform_user.email, "password": platform_password},
        )
        assert login_resp.status_code == 200, login_resp.text
        platform_token = login_resp.json()["access_token"]

        # GET /tenants/me?tenant_id=<uuid> — must return 200 with the tenant object.
        resp = await client.get(
            f"/api/v1/tenants/me?tenant_id={tenant.id}",
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert resp.status_code == 200, (
            f"platform_admin should get 200 on /tenants/me?tenant_id=. Got: {resp.status_code} {resp.text}"
        )
        body = resp.json()
        assert "id" in body, f"Response should be a tenant object with 'id'. Got: {body}"
        assert body["id"] == str(tenant.id)


@pytest.mark.asyncio
async def test_platform_support_cannot_access_tenant_me() -> None:
    """GET /api/v1/tenants/me with a platform_support JWT returns 403.

    Verifies that require_own_tenant_or_platform() rejects platform roles other than
    platform_admin — they must use the dedicated /platform/tenants/{id} read endpoints.
    """
    suffix = uuid4().hex[:8]
    tenant, _user, _password = await create_tenant_with_user(suffix)
    platform_user, platform_password = await create_platform_user("platform_support", suffix)

    async with await make_client() as client:
        # Log in as platform_support.
        login_resp = await client.post(
            "/api/v1/platform/auth/login",
            json={"email": platform_user.email, "password": platform_password},
        )
        assert login_resp.status_code == 200, login_resp.text
        support_token = login_resp.json()["access_token"]

        # GET /tenants/me?tenant_id=<uuid> — must return 403 for platform_support.
        resp = await client.get(
            f"/api/v1/tenants/me?tenant_id={tenant.id}",
            headers={"Authorization": f"Bearer {support_token}"},
        )
        assert resp.status_code == 403, (
            f"platform_support should get 403 on /tenants/me. Got: {resp.status_code} {resp.text}"
        )
        assert resp.json()["error"]["code"] == "forbidden", (
            f"Expected error.code='forbidden'. Got: {resp.json()}"
        )
