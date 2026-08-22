import asyncio
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.passwords import hash_password
from app.core.totp import generate_totp_code
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.auth import service as auth_service
from app.modules.drivers.models import Driver, DriverDevice, DriverSession
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Auth {suffix}", slug=f"auth-{suffix}")
        other_tenant = Tenant(name=f"Tenant Other {suffix}", slug=f"other-{suffix}")
        db.add_all([tenant, other_tenant])
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"owner-{suffix}@example.test",
            password_hash=hash_password("secure-password"),
            full_name="Owner Auth",
            role="owner",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name="Driver Auth",
            phone=f"25884{suffix[:7]}",
        )
        db.add_all([user, driver])
        await db.commit()
        return tenant, other_tenant, user, driver


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.mark.asyncio
async def test_login_refresh_logout_and_tenant_mismatch() -> None:
    tenant, other_tenant, user, _driver = await create_entities()
    async with await create_api_client() as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()

        tenant_response = await client.get(
            "/api/v1/tenants/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert tenant_response.status_code == 200
        assert tenant_response.json()["id"] == str(tenant.id)

        mismatch_response = await client.get(
            "/api/v1/tenants/me",
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "X-Tenant-Id": str(other_tenant.id),
            },
        )
        assert mismatch_response.status_code == 403

        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        rotated_tokens = refresh_response.json()
        assert rotated_tokens["refresh_token"] != tokens["refresh_token"]

        replay_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert replay_response.status_code == 401

        logout_response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": rotated_tokens["refresh_token"]},
        )
        assert logout_response.status_code == 200

        revoked_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": rotated_tokens["refresh_token"]},
        )
        assert revoked_response.status_code == 401


@pytest.mark.asyncio
async def test_concurrent_refresh_rotates_a_token_only_once(monkeypatch) -> None:
    _tenant, _other_tenant, user, _driver = await create_entities()
    original_create_tokens = auth_service._create_user_tokens
    first_refresh_entered = asyncio.Event()
    release_first_refresh = asyncio.Event()
    create_calls = 0

    async def delayed_create_tokens(*args, **kwargs):
        nonlocal create_calls
        create_calls += 1
        if create_calls == 1:
            first_refresh_entered.set()
            try:
                await asyncio.wait_for(release_first_refresh.wait(), timeout=0.2)
            except TimeoutError:
                pass
        else:
            release_first_refresh.set()
        return await original_create_tokens(*args, **kwargs)

    async with await create_api_client() as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
        )
        refresh_token = login_response.json()["refresh_token"]
        monkeypatch.setattr(auth_service, "_create_user_tokens", delayed_create_tokens)

        first = asyncio.create_task(
            client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        )
        await asyncio.wait_for(first_refresh_entered.wait(), timeout=1)
        second = asyncio.create_task(
            client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        )
        responses = await asyncio.gather(first, second)

    assert sorted(response.status_code for response in responses) == [200, 401]
    assert create_calls == 1


@pytest.mark.asyncio
async def test_user_can_list_and_revoke_own_session() -> None:
    tenant, _other_tenant, user, _driver = await create_entities()
    async with await create_api_client() as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
            headers={"User-Agent": "ROTAS test browser"},
        )
        assert login_response.status_code == 200
        tokens = login_response.json()

        sessions_response = await client.get(
            "/api/v1/auth/sessions",
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "X-Tenant-Id": str(tenant.id),
            },
        )
        assert sessions_response.status_code == 200
        sessions = sessions_response.json()
        assert len(sessions) == 1
        assert sessions[0]["active"] is True
        assert sessions[0]["user_agent"] == "ROTAS test browser"

        revoke_response = await client.delete(
            f"/api/v1/auth/sessions/{sessions[0]['id']}",
            headers={
                "Authorization": f"Bearer {tokens['access_token']}",
                "X-Tenant-Id": str(tenant.id),
            },
        )
        assert revoke_response.status_code == 200
        assert revoke_response.json()["revoked"] is True

        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 401


@pytest.mark.asyncio
async def test_mfa_setup_confirm_and_login_challenge() -> None:
    tenant, _other_tenant, user, _driver = await create_entities()
    async with await create_api_client() as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
        )
        tokens = login_response.json()
        auth_headers = {
            "Authorization": f"Bearer {tokens['access_token']}",
            "X-Tenant-Id": str(tenant.id),
        }

        setup_response = await client.post("/api/v1/auth/mfa/setup", headers=auth_headers)
        assert setup_response.status_code == 200
        secret = setup_response.json()["secret"]
        assert secret

        confirm_response = await client.post(
            "/api/v1/auth/mfa/confirm",
            headers=auth_headers,
            json={"code": generate_totp_code(secret)},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["enabled"] is True

        challenged_login = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
        )
        assert challenged_login.status_code == 200
        challenge_payload = challenged_login.json()
        assert challenge_payload["mfa_required"] is True

        verify_response = await client.post(
            "/api/v1/auth/mfa/verify",
            json={
                "challenge_token": challenge_payload["mfa_challenge"],
                "code": generate_totp_code(secret),
            },
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["access_token"]

        replay_response = await client.post(
            "/api/v1/auth/mfa/verify",
            json={
                "challenge_token": challenge_payload["mfa_challenge"],
                "code": generate_totp_code(secret),
            },
        )
        assert replay_response.status_code == 401


@pytest.mark.asyncio
async def test_driver_pairing_consumes_code_and_rotates_session() -> None:
    _tenant, _other_tenant, user, driver = await create_entities()
    async with await create_api_client() as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
        )
        access_token = login_response.json()["access_token"]

        code_response = await client.post(
            f"/api/v1/drivers/{driver.id}/pairing-code",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert code_response.status_code == 200

        pair_payload = {
            "pairing_code": code_response.json()["pairing_code"],
            "device_id": "driver-phone-auth",
            "device_name": "Driver phone",
        }
        pair_response = await client.post("/api/v1/driver-auth/pair", json=pair_payload)
        assert pair_response.status_code == 200
        tokens = pair_response.json()

        consumed_response = await client.post("/api/v1/driver-auth/pair", json=pair_payload)
        assert consumed_response.status_code == 401

        bootstrap_response = await client.get(
            "/api/v1/sync/bootstrap",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert bootstrap_response.status_code == 200

        refresh_response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        assert refresh_response.json()["refresh_token"] != tokens["refresh_token"]


@pytest.mark.asyncio
async def test_driver_pairing_concurrency_accepts_exactly_one_device() -> None:
    tenant, _other_tenant, user, driver = await create_entities()
    async with await create_api_client() as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "secure-password"},
        )
        code_response = await client.post(
            f"/api/v1/drivers/{driver.id}/pairing-code",
            headers={
                "Authorization": f"Bearer {login_response.json()['access_token']}"
            },
        )
        assert code_response.status_code == 200
        pairing_code = code_response.json()["pairing_code"]

        responses = await asyncio.gather(
            client.post(
                "/api/v1/driver-auth/pair",
                json={
                    "pairing_code": pairing_code,
                    "device_id": "pair-race-device-a",
                    "device_name": "Pair race A",
                },
            ),
            client.post(
                "/api/v1/driver-auth/pair",
                json={
                    "pairing_code": pairing_code,
                    "device_id": "pair-race-device-b",
                    "device_name": "Pair race B",
                },
            ),
        )

    assert sorted(response.status_code for response in responses) == [200, 401]
    winner = next(response.json() for response in responses if response.status_code == 200)
    loser = next(response.json() for response in responses if response.status_code == 401)
    assert winner["access_token"]
    assert winner["refresh_token"]
    assert loser["error"]["code"] == "invalid_pairing_code"

    async with AsyncSessionLocal() as db:
        devices = (
            await db.scalars(
                select(DriverDevice).where(
                    DriverDevice.tenant_id == tenant.id,
                    DriverDevice.driver_id == driver.id,
                )
            )
        ).all()
        session_count = await db.scalar(
            select(func.count(DriverSession.id)).where(
                DriverSession.tenant_id == tenant.id,
                DriverSession.driver_id == driver.id,
            )
        )
    assert len(devices) == 1
    assert devices[0].device_id in {"pair-race-device-a", "pair-race-device-b"}
    assert session_count == 1


@pytest.mark.asyncio
async def test_driver_device_identity_is_unique_per_driver() -> None:
    tenant, _other_tenant, _user, driver = await create_entities()
    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                DriverDevice(
                    tenant_id=tenant.id,
                    driver_id=driver.id,
                    device_id="duplicate-physical-device",
                ),
                DriverDevice(
                    tenant_id=tenant.id,
                    driver_id=driver.id,
                    device_id="duplicate-physical-device",
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            await db.commit()
        await db.rollback()


@pytest.mark.asyncio
async def test_alg_none_token_rejected() -> None:
    """SEC-05: A token with alg=none must be rejected with HTTP 401."""
    import base64
    import json

    # Craft a forged JWT with alg=none — no signature required
    header = (
        base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
        .rstrip(b"=")
        .decode()
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(
                {
                    "sub": "dashboard:fake-user-id",
                    "typ": "access",
                    "scope": "dashboard",
                    "tenant_id": "00000000-0000-0000-0000-000000000001",
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "driver_id": None,
                    "role": "admin",
                    "device_id": None,
                }
            ).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    forged_token = f"{header}.{payload}."  # empty signature

    async with await create_api_client() as client:
        response = await client.get(
            "/api/v1/tenants/me",
            headers={"Authorization": f"Bearer {forged_token}"},
        )
    # Will FAIL until PyJWT migration in Plan 02 (python-jose accepts alg=none)
    assert response.status_code == 401, (
        f"Expected 401 for alg=none token, got {response.status_code} — CVE-2025-61152 still open!"
    )


@pytest.mark.asyncio
async def test_refresh_token_rate_limited() -> None:
    """SEC-03: The /auth/refresh endpoint must rate limit after 10 rapid requests."""
    async with await create_api_client() as client:
        for _ in range(10):
            await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "fake-token"},
            )
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "fake-token"},
        )
    assert response.status_code == 429
