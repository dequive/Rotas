"""
Permission-based RBAC tests — Phase 22 Plan 01.

Verifies:
  - ROLE_PERMISSIONS matrix correctness for all 5 roles
  - Principal.has_any_permission() returns correct True/False
  - require_permission() dependency grants/denies correctly
  - JWT round-trip embeds "perms" claim at login
  - Tokens without "perms" claim fall back to ROLE_PERMISSIONS transparently
"""

from uuid import uuid4

import httpx
import jwt as _jwt
import pytest

from app.config import get_settings
from app.core.auth import Principal
from app.core.errors import ApiError
from app.core.passwords import hash_password
from app.core.rbac import (
    ALL_PERMISSIONS,
    BILLING_READ,
    BILLING_VOID,
    BILLING_WRITE,
    FLEET_READ,
    FLEET_WRITE,
    TRIPS_DISPATCH,
    WORKSHOP_WRITE,
    require_permission,
)
from app.core.tokens import create_access_token
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_tenant() -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"RBAC-Perm-{suffix}", slug=f"rbac-perm-{suffix}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


async def _dashboard_headers(tenant_id, role: str) -> dict[str, str]:
    """Create a real User with the given role and return JWT Bearer headers."""
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"{role}-{uuid4().hex[:8]}@rbac-perm.test",
            password_hash="$argon2id$test",
            full_name=f"RBAC Perm {role.title()} Tester",
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    token = _jwt.encode(
        {
            "typ": "access",
            "sub": f"user:{user_id}",
            "role": role,
            "scope": "dashboard",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


_transport = httpx.ASGITransport(app=app)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_transport, base_url="http://testserver")


def _make_principal(role: str, permissions: frozenset[str] | None = None) -> Principal:
    return Principal(
        subject="test:user",
        tenant_id=uuid4(),
        scope="dashboard",
        role=role,
        permissions=permissions,
    )


# ── Test 1: owner has every permission ────────────────────────────────────────


async def test_permission_matrix_owner():
    owner = _make_principal("owner")
    for perm in ALL_PERMISSIONS:
        assert owner.has_any_permission(frozenset({perm})), f"owner missing {perm}"


# ── Test 2: viewer has only *.read permissions ────────────────────────────────


async def test_permission_matrix_viewer():
    viewer = _make_principal("viewer")
    # Viewer CAN read
    assert viewer.has_any_permission(frozenset({FLEET_READ}))
    assert viewer.has_any_permission(frozenset({BILLING_READ}))
    # Viewer CANNOT write or perform privileged actions
    assert not viewer.has_any_permission(frozenset({FLEET_WRITE}))
    assert not viewer.has_any_permission(frozenset({BILLING_WRITE}))
    assert not viewer.has_any_permission(frozenset({TRIPS_DISPATCH}))
    from app.core.rbac import ADMIN_USERS

    assert not viewer.has_any_permission(frozenset({ADMIN_USERS}))


# ── Test 3: mechanic has workshop write but not billing ───────────────────────


async def test_permission_matrix_mechanic():
    mechanic = _make_principal("mechanic")
    # Mechanic CAN do workshop things and read fleet/drivers/trips/fuel
    assert mechanic.has_any_permission(frozenset({WORKSHOP_WRITE}))
    assert mechanic.has_any_permission(frozenset({FLEET_READ}))
    # Mechanic CANNOT access billing, write fleet, dispatch trips, or admin
    assert not mechanic.has_any_permission(frozenset({BILLING_READ}))
    assert not mechanic.has_any_permission(frozenset({FLEET_WRITE}))
    assert not mechanic.has_any_permission(frozenset({TRIPS_DISPATCH}))
    from app.core.rbac import ADMIN_USERS

    assert not mechanic.has_any_permission(frozenset({ADMIN_USERS}))


# ── Test 4: require_permission() raises 403 for viewer on trips.dispatch ──────


async def test_viewer_forbidden_on_require_permission():
    dep = require_permission(TRIPS_DISPATCH)
    viewer = _make_principal("viewer")
    with pytest.raises(ApiError) as exc_info:
        await dep(principal=viewer)
    assert exc_info.value.status_code == 403
    assert "required_permissions" in exc_info.value.details
    assert exc_info.value.details["required_permissions"] == [TRIPS_DISPATCH]


# ── Test 5: require_permission() allows mechanic on workshop.write ────────────


async def test_mechanic_workshop_write_allowed():
    dep = require_permission(WORKSHOP_WRITE)
    mechanic = _make_principal("mechanic")
    result = await dep(principal=mechanic)
    assert result.role == "mechanic"  # returns the principal on success


# ── Test 6: require_permission() denies mechanic on billing.write ─────────────


async def test_mechanic_billing_write_denied():
    dep = require_permission(BILLING_WRITE)
    mechanic = _make_principal("mechanic")
    with pytest.raises(ApiError) as exc_info:
        await dep(principal=mechanic)
    assert exc_info.value.status_code == 403


# ── Test 7: JWT round-trip — login response includes "perms" claim ────────────


async def test_jwt_roundtrip_includes_perms():
    """Integration: login as manager → access_token JWT must contain 'perms' claim."""
    settings = get_settings()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"JWT-Perm-{suffix}", slug=f"jwt-perm-{suffix}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        tenant_id = tenant.id

    pw = "PermsTest!2026"
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"manager-{suffix}@jwt-perm.test",
            password_hash=hash_password(pw),
            full_name="Manager JWT Tester",
            role="manager",
            is_active=True,
        )
        db.add(user)
        await db.commit()

    async with _client() as c:
        r = await c.post(
            "/api/v1/auth/login",
            json={"email": f"manager-{suffix}@jwt-perm.test", "password": pw},
        )
    assert r.status_code == 200, r.text
    access_token = r.json()["access_token"]

    claims = _jwt.decode(
        access_token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    assert "perms" in claims, "JWT missing 'perms' claim after login"
    perms_set = set(claims["perms"])
    assert "trips.dispatch" in perms_set
    assert "billing.write" in perms_set
    assert "billing.void_payment" not in perms_set  # manager is excluded from void_payment


# ── Test 8: tokens without "perms" claim fall back to ROLE_PERMISSIONS ────────


async def test_existing_token_without_perms_falls_back():
    """Tokens minted before Phase 22 (no 'perms' claim) still resolve permissions via role."""
    settings = get_settings()
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Fallback-{suffix}", slug=f"fallback-{suffix}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        tenant_id = tenant.id

    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"admin-{suffix}@fallback.test",
            password_hash="$argon2id$test",
            full_name="Admin Fallback",
            role="admin",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    # Mint a token WITHOUT passing permissions= (simulates pre-Phase-22 token)
    old_token, _ = create_access_token(
        tenant_id=tenant_id,
        user_id=user_id,
        scope="dashboard",
        role="admin",
        permissions=None,  # no perms claim
    )

    # Verify "perms" key is absent from raw JWT claims
    raw = _jwt.decode(
        old_token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
    )
    assert "perms" not in raw, "Token should not have 'perms' when permissions=None"

    # Call an authenticated endpoint with this legacy token — should succeed (admin can read fleet)
    async with _client() as c:
        r = await c.get(
            "/api/v1/vehicles",
            headers={
                "Authorization": f"Bearer {old_token}",
                "X-Tenant-Id": str(tenant_id),
            },
        )
    assert r.status_code == 200, f"Legacy token (no perms claim) should still work: {r.text}"

    # Also verify the Principal constructed from this token falls back correctly
    admin_principal = _make_principal("admin", permissions=None)
    assert admin_principal.has_any_permission(frozenset({FLEET_READ})), (
        "admin should have fleet.read via ROLE_PERMISSIONS fallback"
    )
    assert admin_principal.has_any_permission(frozenset({BILLING_VOID})), (
        "admin should have billing.void_payment via ROLE_PERMISSIONS fallback"
    )
