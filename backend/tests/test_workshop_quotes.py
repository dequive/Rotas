from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.limiter import limiter
from app.database import AsyncSessionLocal
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import WorkOrder, WorkOrderTask
from app.modules.workshop.quote_models import WorkshopQuote
from app.modules.workshop.quote_service import expire_outdated_quotes

limiter.enabled = False


@pytest.fixture
async def workshop_tenant_headers(async_client):
    suffix = uuid4().hex[:8]
    reg = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Oficina Quotes {suffix}",
            "company_slug": f"oficina-q-{suffix}",
            "owner_full_name": "Gestor Oficina",
            "owner_email": f"gestor-q-{suffix}@example.test",
            "owner_password": "password123",
            "product_modules": ["tms", "oficina"],
        },
    )
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant"]["id"]
    return {"Authorization": f"Bearer {token}"}, tenant_id


@pytest.mark.asyncio
async def test_quote_crud_and_acceptance_initial(async_client, workshop_tenant_headers):
    headers, tenant_id = workshop_tenant_headers

    async with AsyncSessionLocal() as db:
        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"AFM-{uuid4().hex[:4].upper()}-MC",
            ownership_type="customer",
        )
        db.add(vehicle)
        await db.commit()
        vehicle_id = vehicle.id

    # 1. Create Initial Quote
    create_res = await async_client.post(
        "/api/v1/workshop/quotes",
        json={
            "vehicle_id": str(vehicle_id),
            "is_supplemental": False,
            "tax_total": 500.0,
            "notes": "Orçamento inicial para revisão de travões",
            "items": [
                {
                    "item_type": "labor",
                    "description": "Substituição de pastilhas dianteiras",
                    "quantity": 2.0,
                    "unit_price": 1500.0,
                    "warranty_months": 6,
                    "warranty_km": 10000,
                },
                {
                    "item_type": "part",
                    "description": "Jogo de pastilhas de travão Bosch",
                    "quantity": 1.0,
                    "unit_price": 2500.0,
                    "warranty_months": 12,
                    "warranty_km": 20000,
                },
            ],
        },
        headers=headers,
    )
    assert create_res.status_code == 201
    q_data = create_res.json()
    quote_id = q_data["id"]
    assert q_data["quote_number"].startswith("ORC-")
    assert q_data["status"] == "sent"
    assert q_data["labor_total"] == 3000.0
    assert q_data["parts_total"] == 2500.0
    assert q_data["tax_total"] == 500.0
    assert q_data["total_amount"] == 6000.0

    # 2. Accept Quote (Initial -> Creates New WorkOrder)
    accept_res = await async_client.post(
        f"/api/v1/workshop/quotes/{quote_id}/accept",
        headers=headers,
        json={"acceptance_channel": "email", "accepted_by_person_name": "Test Client"},
    )
    assert accept_res.status_code == 200
    acc_data = accept_res.json()
    assert acc_data["quote"]["status"] == "converted"
    work_order_id = acc_data["work_order_id"]
    assert work_order_id is not None

    # Verify WorkOrder was created with tasks and origin_type='quote'
    async with AsyncSessionLocal() as db:
        wo = await db.get(WorkOrder, work_order_id)
        assert wo is not None
        assert wo.work_order_number.startswith("OS-")
        assert wo.status == "approved"
        assert wo.origin_type == "quote"

        tasks_res = await db.execute(
            select(WorkOrderTask).where(WorkOrderTask.work_order_id == work_order_id)
        )
        tasks = tasks_res.scalars().all()
        assert len(tasks) == 2


@pytest.mark.asyncio
async def test_quote_acceptance_supplemental(async_client, workshop_tenant_headers):
    headers, tenant_id = workshop_tenant_headers

    async with AsyncSessionLocal() as db:
        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"AFM-{uuid4().hex[:4].upper()}-MC",
            ownership_type="customer",
        )
        db.add(vehicle)
        await db.flush()

        base_wo = WorkOrder(
            tenant_id=tenant_id,
            vehicle_id=vehicle.id,
            work_order_number=f"OS-BASE-{uuid4().hex[:4]}",
            planned_work="Trabalho inicial",
            status="in_progress",
            origin_type="direct",
        )
        db.add(base_wo)
        await db.commit()
        vehicle_id = vehicle.id
        base_wo_id = base_wo.id

    # Create Supplemental Quote pointing to base_wo_id
    sup_res = await async_client.post(
        "/api/v1/workshop/quotes",
        json={
            "vehicle_id": str(vehicle_id),
            "is_supplemental": True,
            "related_work_order_id": str(base_wo_id),
            "items": [
                {
                    "item_type": "part",
                    "description": "Disco de travão rectificado",
                    "quantity": 2.0,
                    "unit_price": 1200.0,
                }
            ],
        },
        headers=headers,
    )
    assert sup_res.status_code == 201
    sup_quote_id = sup_res.json()["id"]

    # Accept Supplemental Quote
    acc_res = await async_client.post(
        f"/api/v1/workshop/quotes/{sup_quote_id}/accept",
        headers=headers,
        json={"acceptance_channel": "telefone", "accepted_by_person_name": "Test Client"},
    )
    assert acc_res.status_code == 200
    assert acc_res.json()["work_order_id"] == str(base_wo_id)

    # Verify no new WorkOrder created, items appended to base_wo
    async with AsyncSessionLocal() as db:
        tasks_res = await db.execute(
            select(WorkOrderTask).where(WorkOrderTask.work_order_id == base_wo_id)
        )
        tasks = tasks_res.scalars().all()
        assert len(tasks) == 1
        assert "[Suplementar ORC-" in tasks[0].description


@pytest.mark.asyncio
async def test_quote_rejection_and_expiration(async_client, workshop_tenant_headers):
    headers, tenant_id = workshop_tenant_headers

    async with AsyncSessionLocal() as db:
        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"AFM-{uuid4().hex[:4].upper()}-MC",
        )
        db.add(vehicle)
        await db.commit()
        vehicle_id = vehicle.id

    # 1. Create quote to reject
    q1 = await async_client.post(
        "/api/v1/workshop/quotes",
        json={
            "vehicle_id": str(vehicle_id),
            "items": [{"description": "Diagnóstico elétrico", "unit_price": 1000.0}],
        },
        headers=headers,
    )
    q1_id = q1.json()["id"]

    rej_res = await async_client.post(
        f"/api/v1/workshop/quotes/{q1_id}/reject",
        json={"reason": "Valor considerado elevado pelo cliente"},
        headers=headers,
    )
    assert rej_res.status_code == 200
    assert rej_res.json()["status"] == "rejected"

    # 2. Expiration worker test
    expired_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    q2 = await async_client.post(
        "/api/v1/workshop/quotes",
        json={
            "vehicle_id": str(vehicle_id),
            "valid_until": expired_time,
            "items": [{"description": "Mão de obra", "unit_price": 500.0}],
        },
        headers=headers,
    )
    q2_id = q2.json()["id"]

    async with AsyncSessionLocal() as db:
        expired_count = await expire_outdated_quotes(db)
        assert expired_count >= 1

        q2_db = await db.get(WorkshopQuote, q2_id)
        assert q2_db is not None
        assert q2_db.status == "expired"


@pytest.mark.asyncio
async def test_accept_quote_with_traceable_channel_and_person_name(
    async_client, workshop_tenant_headers
):
    headers, tenant_id = workshop_tenant_headers

    async with AsyncSessionLocal() as db:
        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"AFM-{uuid4().hex[:4].upper()}-TR",
        )
        db.add(vehicle)
        await db.commit()
        vehicle_id = vehicle.id

    # 1. Create quote
    q1 = await async_client.post(
        "/api/v1/workshop/quotes",
        json={
            "vehicle_id": str(vehicle_id),
            "items": [{"description": "Revisao Geral", "unit_price": 5000.0}],
        },
        headers=headers,
    )
    q1_id = q1.json()["id"]

    # 2. Accept with channel & person name
    accept1 = await async_client.post(
        f"/api/v1/workshop/quotes/{q1_id}/accept",
        json={
            "acceptance_channel": "whatsapp",
            "accepted_by_person_name": "Antonio Muchanga",
        },
        headers=headers,
    )
    assert accept1.status_code == 200
    q1_res = accept1.json()["quote"]
    assert q1_res["acceptance_channel"] == "whatsapp"
    assert q1_res["accepted_by_person_name"] == "Antonio Muchanga"

    # Verify DB persistence
    async with AsyncSessionLocal() as db:
        quote_db = await db.get(WorkshopQuote, q1_id)
        assert quote_db is not None
        assert quote_db.acceptance_channel == "whatsapp"
        assert quote_db.accepted_by_person_name == "Antonio Muchanga"

    # 3. Create second quote and accept without channel/person_name (verify nullable backend fallback)
    q2 = await async_client.post(
        "/api/v1/workshop/quotes",
        json={
            "vehicle_id": str(vehicle_id),
            "items": [{"description": "Troca de Oleo", "unit_price": 1500.0}],
        },
        headers=headers,
    )
    q2_id = q2.json()["id"]

    accept2 = await async_client.post(
        f"/api/v1/workshop/quotes/{q2_id}/accept",
        json={},
        headers=headers,
    )
    assert accept2.status_code == 200
    q2_res = accept2.json()["quote"]
    assert q2_res["acceptance_channel"] is None
    assert q2_res["accepted_by_person_name"] is None

    async with AsyncSessionLocal() as db:
        quote2_db = await db.get(WorkshopQuote, q2_id)
        assert quote2_db is not None
        assert quote2_db.acceptance_channel is None
        assert quote2_db.accepted_by_person_name is None
