"""
Phase 22 Plan 03 — Custom tenant roles API tests.

Tests cover:
  - Creating a role with valid permissions
  - Rejecting unknown permissions
  - Cross-tenant isolation on list
  - JWT perms reflect custom role at login
  - Non-admin cannot create roles
  - Cross-tenant PATCH returns 404
"""

from uuid import uuid4

import httpx
import jwt as _jwt
import pytest

from app.config import get_settings
from app.core.passwords import hash_password
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


_transport = httpx.ASGITransport(app=app)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_transport, base_url="http://testserver")


async def _make_tenant(suffix: str | None = None) -> Tenant:
    s = suffix or uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Roles-Test-{s}", slug=f"roles-{s}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


async def _make_user(tenant_id, role: str, *, password: str | None = None) -> User:
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"{role}-{uuid4().hex[:8]}@roles.test",
            password_hash=hash_password(password or "Password123!"),
            full_name=f"Roles {role.title()} Tester",
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


def _jwt_headers(tenant_id, user: User, *, perms: list[str] | None = None) -> dict[str, str]:
    """Build auth headers with a signed JWT (mirrors require_permission() expectations)."""
    settings = get_settings()
    payload: dict = {
        "typ": "access",
        "sub": f"user:{user.id}",
        "role": user.role,
        "scope": "dashboard",
        "tenant_id": str(tenant_id),
        "user_id": str(user.id),
    }
    if perms is not None:
        payload["perms"] = perms
    token = _jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


async def _owner_headers(tenant_id) -> dict[str, str]:
    user = await _make_user(tenant_id, "owner")
    # owner gets ADMIN_USERS via ROLE_PERMISSIONS — include perms in JWT
    from app.core.rbac import ROLE_PERMISSIONS
    perms = list(ROLE_PERMISSIONS.get("owner", frozenset()))
    return _jwt_headers(tenant_id, user, perms=perms)


# ── TR-01: create role success ────────────────────────────────────────────────


async def test_create_tenant_role_success():
    tenant = await _make_tenant()
    headers = await _owner_headers(tenant.id)
    async with _client() as c:
        r = await c.post(
            "/api/v1/users/tenant-roles",
            headers=headers,
            json={
                "name": "Director",
                "slug": "director",
                "permissions": ["billing.read", "billing.write"],
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["slug"] == "director"
    assert "id" in body
    assert "billing.read" in body["permissions"]


# ── TR-02: unknown permission rejected ───────────────────────────────────────


async def test_create_tenant_role_unknown_permission_rejected():
    tenant = await _make_tenant()
    headers = await _owner_headers(tenant.id)
    async with _client() as c:
        r = await c.post(
            "/api/v1/users/tenant-roles",
            headers=headers,
            json={
                "name": "BadRole",
                "slug": "bad-role",
                "permissions": ["billing.read", "totally.fake"],
            },
        )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "invalid_permissions"


# ── TR-03: list returns only own-tenant roles ─────────────────────────────────


async def test_list_tenant_roles_returns_only_own_tenant():
    tenant_a = await _make_tenant()
    tenant_b = await _make_tenant()
    headers_a = await _owner_headers(tenant_a.id)
    headers_b = await _owner_headers(tenant_b.id)

    # Tenant A creates 2 roles
    async with _client() as c:
        for slug in ("role-alpha", "role-beta"):
            r = await c.post(
                "/api/v1/users/tenant-roles",
                headers=headers_a,
                json={"name": slug.title(), "slug": slug, "permissions": ["billing.read"]},
            )
            assert r.status_code == 201, r.text

        # Tenant B lists its own roles — should be empty
        r = await c.get("/api/v1/users/tenant-roles", headers=headers_b)
    assert r.status_code == 200, r.text
    assert r.json() == []


# ── TR-04: JWT perms reflect custom role at login ─────────────────────────────


async def test_assign_custom_role_jwt_perms_reflect_custom_role():
    tenant = await _make_tenant()
    headers = await _owner_headers(tenant.id)
    password = "Password123!"

    async with _client() as c:
        # Create a custom role with billing.read only
        r = await c.post(
            "/api/v1/users/tenant-roles",
            headers=headers,
            json={"name": "BillingOnly", "slug": "billing-only", "permissions": ["billing.read"]},
        )
        assert r.status_code == 201, r.text
        role_id = r.json()["id"]

        # Create a viewer user (has fleet.read in standard role permissions)
        viewer = await _make_user(tenant.id, "viewer", password=password)
        viewer_headers = _jwt_headers(tenant.id, viewer, perms=["admin.users"])

        # Assign custom role (reuse owner headers for the assign endpoint)
        r = await c.post(
            f"/api/v1/users/{viewer.id}/role",
            headers=headers,
            json={"custom_role_id": str(role_id)},
        )
        assert r.status_code == 200, r.text

        # Viewer logs in — JWT should carry custom role perms
        settings = get_settings()
        r = await c.post(
            "/api/v1/auth/login",
            json={
                "email": viewer.email,
                "password": password,
                "tenant_slug": (await _get_tenant_slug(tenant.id)),
            },
        )
        assert r.status_code == 200, r.text
        access_token = r.json()["access_token"]

    decoded = _jwt.decode(
        access_token,
        get_settings().jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    perms = decoded.get("perms", [])
    assert "billing.read" in perms, f"Expected billing.read in perms, got: {perms}"
    assert "fleet.read" not in perms, f"fleet.read should not be in custom-role perms, got: {perms}"


async def _get_tenant_slug(tenant_id) -> str:
    async with AsyncSessionLocal() as db:
        t = await db.get(Tenant, tenant_id)
        return t.slug


# ── TR-05: non-admin cannot create role ──────────────────────────────────────


async def test_non_admin_cannot_create_role():
    tenant = await _make_tenant()
    manager = await _make_user(tenant.id, "manager")
    from app.core.rbac import ROLE_PERMISSIONS
    perms = list(ROLE_PERMISSIONS.get("manager", frozenset()))
    manager_headers = _jwt_headers(tenant.id, manager, perms=perms)

    async with _client() as c:
        r = await c.post(
            "/api/v1/users/tenant-roles",
            headers=manager_headers,
            json={"name": "ShouldFail", "slug": "should-fail", "permissions": ["billing.read"]},
        )
    assert r.status_code == 403, r.text


# ── TR-06: cross-tenant PATCH returns 404 ────────────────────────────────────


async def test_patch_tenant_role_cross_tenant_denied():
    tenant_a = await _make_tenant()
    tenant_b = await _make_tenant()
    headers_a = await _owner_headers(tenant_a.id)
    headers_b = await _owner_headers(tenant_b.id)

    async with _client() as c:
        # Tenant A creates a role
        r = await c.post(
            "/api/v1/users/tenant-roles",
            headers=headers_a,
            json={"name": "TenantARole", "slug": "tenant-a-role", "permissions": ["billing.read"]},
        )
        assert r.status_code == 201, r.text
        role_id = r.json()["id"]

        # Tenant B tries to PATCH that role_id — should get 404
        r = await c.patch(
            f"/api/v1/users/tenant-roles/{role_id}",
            headers=headers_b,
            json={"name": "Hijacked"},
        )
    assert r.status_code == 404, r.text
