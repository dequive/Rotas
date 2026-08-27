from uuid import uuid4

import pytest

from app.core.limiter import limiter
from app.database import AsyncSessionLocal
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder
from app.modules.workshop.warranty_models import ServiceWarranty

limiter.enabled = False


@pytest.fixture
async def workshop_tenant_headers(async_client):
    suffix = uuid4().hex[:8]
    reg = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Oficina Cat {suffix}",
            "company_slug": f"oficina-c-{suffix}",
            "owner_full_name": "Gestor Cat",
            "owner_email": f"gestor-c-{suffix}@example.test",
            "owner_password": "password123",
            "product_modules": ["tms", "oficina"],
        },
    )
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant"]["id"]
    return {"Authorization": f"Bearer {token}"}, tenant_id


@pytest.mark.asyncio
async def test_catalog_crud_and_guards(async_client, workshop_tenant_headers):
    headers, tenant_id = workshop_tenant_headers

    # 1. Create Catalog Item
    item_res = await async_client.post(
        "/api/v1/workshop/catalog",
        json={
            "code": "MOO-001",
            "name": "Mudança de Óleo e Filtro",
            "category": "mecanica",
            "standard_duration_minutes": 45,
            "base_price": 2500.0,
            "includes_parts": True,
        },
        headers=headers,
    )
    assert item_res.status_code == 201
    item_data = item_res.json()
    item_id = item_data["id"]
    assert item_data["code"] == "MOO-001"
    assert item_data["base_price"] == 2500.0

    # Duplicate code should fail (409)
    dup_res = await async_client.post(
        "/api/v1/workshop/catalog",
        json={
            "code": "MOO-001",
            "name": "Duplicado",
        },
        headers=headers,
    )
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "code_already_exists"

    # List items
    list_res = await async_client.get(
        "/api/v1/workshop/catalog?category=mecanica",
        headers=headers,
    )
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # Update item
    up_res = await async_client.patch(
        f"/api/v1/workshop/catalog/{item_id}",
        json={"base_price": 2800.0},
        headers=headers,
    )
    assert up_res.status_code == 200
    assert up_res.json()["base_price"] == 2800.0


@pytest.mark.asyncio
async def test_warranty_issuance_and_claim(async_client, workshop_tenant_headers):
    headers, tenant_id = workshop_tenant_headers

    async with AsyncSessionLocal() as db:
        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"AFM-{uuid4().hex[:4].upper()}-MC",
            current_km=50000,
        )
        db.add(vehicle)
        await db.flush()

        wo = WorkOrder(
            tenant_id=tenant_id,
            vehicle_id=vehicle.id,
            work_order_number=f"OS-WAR-{uuid4().hex[:4]}",
            planned_work="Reparação da caixa de velocidades",
            status="completed",
        )
        db.add(wo)
        await db.commit()
        vehicle_id = vehicle.id
        wo_id = wo.id

    # 1. Create Warranty
    war_res = await async_client.post(
        "/api/v1/workshop/warranties",
        json={
            "work_order_id": str(wo_id),
            "vehicle_id": str(vehicle_id),
            "warranty_type": "full_service",
            "duration_months": 6,
            "duration_km": 5000,
            "km_at_service": 50000,
        },
        headers=headers,
    )
    assert war_res.status_code == 201
    war_data = war_res.json()
    war_id = war_data["id"]
    assert war_data["status"] == "active"

    # 2. Claim Warranty exceeding km limit (50000 + 6000 = 56000 km -> > 55000 max)
    claim_fail = await async_client.post(
        f"/api/v1/workshop/warranties/{war_id}/claim",
        json={
            "current_km": 56000,
            "claim_reason": "Barulho na caixa de velocidades",
        },
        headers=headers,
    )
    assert claim_fail.status_code == 409
    assert claim_fail.json()["error"]["code"] == "warranty_km_exceeded"

    # Verify status changed to expired
    async with AsyncSessionLocal() as db:
        w_db = await db.get(ServiceWarranty, war_id)
        assert w_db is not None
        assert w_db.status == "expired"
