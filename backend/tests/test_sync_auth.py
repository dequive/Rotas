from uuid import uuid4

import httpx
import pytest

from app.core.passwords import hash_password
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def create_manager_user():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"SyncAuthTenant {suffix}", slug=f"sync-auth-{suffix}")
        db.add(tenant)
        await db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"manager-{suffix}@example.test",
            password_hash=hash_password("password123"),
            full_name="Test Manager",
            role="manager",
        )
        db.add(user)
        await db.commit()
        return tenant, user


async def test_manager_token_rejected_on_sync_batch():
    """AUTH-03: Manager dashboard tokens must be rejected on /sync/batch with HTTP 403."""
    tenant, user = await create_manager_user()
    async with await create_api_client() as client:
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "password123"},
        )
        assert login_resp.status_code == 200
        manager_token = login_resp.json()["access_token"]

        # Manager token on sync/batch must be rejected — only driver tokens allowed
        response = await client.post(
            "/api/v1/sync/batch",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"items": []},
        )
    # Will FAIL until AUTH-03 fix in Plan 02 (currently returns 200 with get_current_principal)
    assert response.status_code == 403


async def test_manager_token_rejected_on_sync_bootstrap():
    """AUTH-03: Manager dashboard tokens must be rejected on /sync/bootstrap with HTTP 403."""
    tenant, user = await create_manager_user()
    async with await create_api_client() as client:
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": user.email, "password": "password123"},
        )
        manager_token = login_resp.json()["access_token"]

        response = await client.get(
            "/api/v1/sync/bootstrap",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
    assert response.status_code == 403
