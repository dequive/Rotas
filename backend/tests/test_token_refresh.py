"""
Test stubs for AUTH-01 (manager refresh token) and AUTH-02 (driver refresh token).

RED criteria:
- test_refresh_token_rotation_issues_new_tokens: validates token rotation works AND
  old token is invalidated — this SHOULD PASS (backend already implements rotation)
  but must be confirmed as a contract test
- test_manager_login_stores_refresh_token: SHOULD PASS (backend already returns refresh_token)
- test_driver_pairing_returns_refresh_token: SHOULD PASS (backend already returns refresh_token)
- test_refresh_with_invalid_token_returns_401: SHOULD PASS (backend validates tokens)

These tests validate the backend contracts that frontend AUTH-01/AUTH-02 implementations
must rely on. If any backend contract is broken, these tests catch the regression.
"""
from uuid import uuid4

import httpx
import pytest

from app.core.passwords import hash_password
from app.core.tokens import create_opaque_token, hash_token
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver, DriverDevice
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def create_manager_user():
    """Create tenant + manager user, return (tenant, user, password)."""
    suffix = uuid4().hex[:8]
    password = "password123"
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Refresh Tenant {suffix}", slug=f"refresh-{suffix}")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"mgr-{suffix}@example.test",
            password_hash=hash_password(password),
            full_name="Test Manager",
            role="manager",
        )
        db.add(user)
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(user)
        return tenant, user, password


async def create_driver_with_pairing_code():
    """Create tenant + driver with an active pairing code.

    Returns (tenant, driver, device_id, raw_pairing_code).
    Uses create_opaque_token() to generate the code and stores the hash.
    """
    suffix = uuid4().hex[:8]
    device_id = f"device-refresh-{suffix}"
    raw_code = create_opaque_token()

    async with AsyncSessionLocal() as db:
        from datetime import UTC, datetime, timedelta

        tenant = Tenant(name=f"Driver Refresh Tenant {suffix}", slug=f"drv-refresh-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"DRR-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Refresh {suffix}",
            phone=f"25884{suffix[:7]}",
            status="active",
            pairing_code_hash=hash_token(raw_code),
            pairing_code_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(driver)
        return tenant, driver, device_id, raw_code


async def test_manager_login_stores_refresh_token():
    """AUTH-01: POST /api/v1/auth/login response must include refresh_token.

    This is the prerequisite for manager silent refresh — if refresh_token is absent,
    the auth.ts server action cannot store it in a cookie.

    NOTE: Backend already returns refresh_token — this test validates the contract is stable.
    SHOULD PASS immediately.
    """
    tenant, user, password = await create_manager_user()

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )

    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert data.get("refresh_token") is not None, (
        "Login response must include 'refresh_token' for AUTH-01 manager silent refresh"
    )
    assert data.get("access_token") is not None, "Login response must include 'access_token'"
    assert len(data["refresh_token"]) > 20, "refresh_token must be a non-trivial opaque token"


async def test_refresh_token_rotation_issues_new_tokens():
    """AUTH-01/AUTH-02: POST /api/v1/auth/refresh with valid refresh_token must return
    new access_token AND new refresh_token (rotation scheme). Old refresh_token must be
    invalid after first use.

    Validates the full rotation contract:
    1. Login returns access_token + refresh_token
    2. Refresh with valid token returns NEW access_token and NEW refresh_token
    3. Attempting to reuse the OLD refresh_token returns 401 (rotation enforced)
    """
    tenant, user, password = await create_manager_user()

    async with await create_api_client() as client:
        # Step 1: Login to get initial tokens
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": password},
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        original_access_token = login_data["access_token"]
        original_refresh_token = login_data["refresh_token"]

        # Step 2: Use refresh_token to get new tokens
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh_token},
        )
        assert refresh_resp.status_code == 200, f"Refresh failed: {refresh_resp.text}"
        new_data = refresh_resp.json()

        # New tokens must differ from original (rotation)
        assert new_data["access_token"] != original_access_token, (
            "Refresh must issue a NEW access_token (different from original)"
        )
        assert new_data["refresh_token"] != original_refresh_token, (
            "Refresh must issue a NEW refresh_token (rotation — original must be invalidated)"
        )

        # Step 3: Attempt to reuse the original (now revoked) refresh_token
        reuse_resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": original_refresh_token},
        )

    # Old token must be rejected (rotation enforcement)
    assert reuse_resp.status_code == 401, (
        f"Expected 401 when reusing revoked refresh_token, got {reuse_resp.status_code}: "
        f"{reuse_resp.text}"
    )


async def test_driver_pairing_returns_refresh_token():
    """AUTH-02: POST /api/v1/driver-auth/pair response must include refresh_token.

    pairDevice() in apps/driver/src/api.ts currently discards the refresh_token.
    This test validates the backend provides it so the frontend fix in AUTH-02 has
    something to consume.

    NOTE: Backend already returns refresh_token — this test validates the contract is stable.
    SHOULD PASS immediately.
    """
    tenant, driver, device_id, raw_code = await create_driver_with_pairing_code()

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/driver-auth/pair",
            json={
                "pairing_code": raw_code,
                "device_id": device_id,
                "device_name": "Test Android Device",
            },
        )

    assert response.status_code == 200, f"Pairing failed: {response.text}"
    data = response.json()
    assert data.get("refresh_token") is not None, (
        "Pairing response must include 'refresh_token' for AUTH-02 driver silent refresh"
    )
    assert data.get("access_token") is not None, "Pairing response must include 'access_token'"
    assert len(data["refresh_token"]) > 20, "refresh_token must be a non-trivial opaque token"


async def test_refresh_with_invalid_token_returns_401():
    """AUTH-01/AUTH-02: POST /api/v1/auth/refresh with nonexistent token must return 401.

    Validates that the refresh endpoint properly rejects fabricated / expired tokens.
    SHOULD PASS immediately (backend already validates).
    """
    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "completely-invalid-token-that-does-not-exist"},
        )

    assert response.status_code == 401, (
        f"Expected 401 for invalid refresh_token but got {response.status_code}: {response.text}"
    )
    body = response.json()
    # The error body must communicate token invalidity
    error_detail = str(body.get("detail", "")) + str(body.get("error", ""))
    assert "invalid_refresh_token" in error_detail or "invalid" in error_detail.lower(), (
        f"Expected error about invalid refresh token but got: {body}"
    )
