from uuid import uuid4

import pytest

from app.core.limiter import limiter

limiter.enabled = False


@pytest.fixture
async def workshop_tenant_headers(async_client):
    suffix = uuid4().hex[:8]
    reg = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Oficina Bays {suffix}",
            "company_slug": f"oficina-b-{suffix}",
            "owner_full_name": "Gestor Bays",
            "owner_email": f"gestor-b-{suffix}@example.test",
            "owner_password": "password123",
            "product_modules": ["tms", "oficina"],
        },
    )
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant"]["id"]
    return {"Authorization": f"Bearer {token}"}, tenant_id


@pytest.mark.asyncio
async def test_work_bay_crud(async_client, workshop_tenant_headers):
    headers, tenant_id = workshop_tenant_headers

    # 1. Create WorkBay
    create_res = await async_client.post(
        "/api/v1/workshop/bays",
        json={
            "name": "Baía 1 - Elevador 4T",
            "category": "mecanica",
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    bay_data = create_res.json()
    bay_id = bay_data["id"]
    assert bay_data["name"] == "Baía 1 - Elevador 4T"
    assert bay_data["is_active"] is True

    # 2. List WorkBays
    list_res = await async_client.get(
        "/api/v1/workshop/bays",
        headers=headers,
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 3. Update WorkBay
    up_res = await async_client.patch(
        f"/api/v1/workshop/bays/{bay_id}",
        json={"is_active": False},
        headers=headers,
    )
    assert up_res.status_code == 200
    assert up_res.json()["is_active"] is False
