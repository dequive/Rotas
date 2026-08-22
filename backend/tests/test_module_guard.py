from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.limiter import limiter
from app.database import AsyncSessionLocal
from app.modules.tenants.models import Tenant

limiter.enabled = False


@pytest.mark.asyncio
async def test_onboarding_default_and_custom_product_modules(async_client):
    suffix = uuid4().hex[:8]
    # Default onboarding: product_modules = ["tms"]
    res1 = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"TMS Transportes {suffix}",
            "company_slug": f"tms-trans-{suffix}",
            "owner_full_name": "Gestor TMS",
            "owner_email": f"tms-{suffix}@example.test",
            "owner_password": "password123",
        },
    )
    assert res1.status_code == 201
    assert res1.json()["tenant"]["product_modules"] == ["tms"]

    # Custom onboarding with ["tms", "oficina"]
    suffix2 = uuid4().hex[:8]
    res2 = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Oficina e Frota {suffix2}",
            "company_slug": f"oficina-frota-{suffix2}",
            "owner_full_name": "Gestor Oficina",
            "owner_email": f"oficina-{suffix2}@example.test",
            "owner_password": "password123",
            "product_modules": ["tms", "oficina"],
        },
    )
    assert res2.status_code == 201
    assert sorted(res2.json()["tenant"]["product_modules"]) == ["oficina", "tms"]

    # Invalid product module rejected
    suffix3 = uuid4().hex[:8]
    res3 = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Empresa Invalida {suffix3}",
            "owner_full_name": "Gestor Invalido",
            "owner_email": f"invalid-{suffix3}@example.test",
            "owner_password": "password123",
            "product_modules": ["tms", "invalid_module"],
        },
    )
    assert res3.status_code == 422


@pytest.mark.asyncio
async def test_tenant_cannot_self_upgrade_product_modules(async_client):
    suffix = uuid4().hex[:8]
    reg = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Upgrade Tenant {suffix}",
            "owner_full_name": "Owner Upgrade",
            "owner_email": f"upgrade-{suffix}@example.test",
            "owner_password": "password123",
        },
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Commercial entitlements are platform-managed; tenant owners cannot
    # self-upgrade by calling the tenant-plane endpoint.
    patch_res = await async_client.patch(
        "/api/v1/tenants/me/modules",
        json={"product_modules": ["tms", "oficina"]},
        headers=headers,
    )
    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "entitlement_managed_by_platform"

    async with AsyncSessionLocal() as db:
        tenant_id = reg.json()["tenant"]["id"]
        tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
        assert tenant is not None
        assert tenant.product_modules == ["tms"]
