import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import pytest
from sqlalchemy import select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.clients.models import Client
from app.modules.outbox.models import OutboxEvent
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    SparePartInventory,
    WorkshopTool,
)

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def create_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_workshop_full_e2e_and_multitenant_isolation():
    """Teste integrado da Oficina Auto e prova estrita de isolamento multi-tenant.
    
    Cobre:
    1. Tenant A & Tenant B isolados.
    2. Receção (REC) -> Orçamento (ORC) -> Aceitação -> Ordem de Serviço (OS).
    3. Atribuição de tarefas e sessões de mão-de-obra por mecânico.
    4. Emissão física de peças e devolução parcial com ajuste líquido de rentabilidade.
    5. Requisição e devolução de Ferramenta Especial + controlo de calibração.
    6. Quality Check (QC) -> Fecho financeiro -> evento transacional no outbox.
    7. Levantamento de viatura (guarda HTTP 409 de pessoa não autorizada).
    8. Prova de Isolamento Multi-Tenant: Tenant B tentando aceder a recursos do Tenant A recebe HTTP 404.
    """
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        # Seed Tenant A
        tenant_a = Tenant(
            name=f"Oficina Auto A {suffix}",
            slug=f"oficina-a-{suffix}",
            product_modules=["tms", "oficina"],
        )
        db.add(tenant_a)
        await db.flush()

        user_a = User(
            tenant_id=tenant_a.id,
            email=f"admin.a.{suffix}@rotas.mz",
            password_hash="hash",
            full_name="Gestor Tenant A",
            role="admin",
        )
        mechanic_a = User(
            tenant_id=tenant_a.id,
            email=f"mec.a.{suffix}@rotas.mz",
            password_hash="hash",
            full_name="Mecânico Tenant A",
            role="mechanic",
        )
        client_a = Client(
            tenant_id=tenant_a.id,
            trading_name="Empresa Transportes A",
            nuit="111222333",
            client_type="organization",
        )
        db.add_all([user_a, mechanic_a, client_a])
        await db.flush()

        vehicle_a = Vehicle(
            tenant_id=tenant_a.id,
            plate=f"AFM-{suffix[:4].upper()}-A",
            brand="Toyota",
            model="Hilux",
            current_km=50000,
            customer_client_id=client_a.id,
        )
        part_a = SparePartInventory(
            tenant_id=tenant_a.id,
            sku=f"FIL-A-{suffix}",
            name="Filtro de Óleo Heavy Duty",
            current_quantity=Decimal("10.000"),
            minimum_quantity=Decimal("2.000"),
            average_unit_cost=Decimal("1200.00"),
        )
        tool_a = WorkshopTool(
            tenant_id=tenant_a.id,
            code=f"TORQ-A-{suffix}",
            name="Torquímetro Digital 200Nm",
            status="available",
        )
        db.add_all([vehicle_a, part_a, tool_a])
        await db.flush()

        # Seed Tenant B (para teste de isolamento cross-tenant)
        tenant_b = Tenant(
            name=f"Oficina Auto B {suffix}",
            slug=f"oficina-b-{suffix}",
            product_modules=["tms", "oficina"],
        )
        db.add(tenant_b)
        await db.flush()

        user_b = User(
            tenant_id=tenant_b.id,
            email=f"admin.b.{suffix}@rotas.mz",
            password_hash="hash",
            full_name="Gestor Tenant B",
            role="admin",
        )
        db.add(user_b)
        await db.flush()

        tenant_a_id = tenant_a.id
        tenant_b_id = tenant_b.id
        mechanic_a_id = mechanic_a.id
        vehicle_a_id = vehicle_a.id
        client_a_id = client_a.id
        part_a_id = part_a.id
        tool_a_id = tool_a.id

        await db.commit()

    headers_a = auth_headers(tenant_a_id)
    headers_b = auth_headers(tenant_b_id)

    async with await create_api_client() as client:
        # -----------------------------------------------------------------------
        # 1. Calibração da Ferramenta Especial (Tenant A)
        # -----------------------------------------------------------------------
        calib_res = await client.post(
            f"/api/v1/workshop/tools/{tool_a_id}/calibrations",
            json={
                "calibrated_at": datetime.now(UTC).isoformat(),
                "next_due_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                "notes": f"Certificado INNOQ #{suffix}",
            },
            headers=headers_a,
        )
        assert calib_res.status_code == 201

        # -----------------------------------------------------------------------
        # 2. Check-in de Receção da Viatura (REC)
        # -----------------------------------------------------------------------
        reception_res = await client.post(
            "/api/v1/workshop/receptions",
            json={
                "vehicle_id": str(vehicle_a_id),
                "client_id": str(client_a_id),
                "odometer_at_reception": 50000,
                "reported_issues": "Revisão geral de 50.000 km e mudança de pastilhas",
                "delivered_by_name": "Carlos Motorista",
                "delivered_by_phone": "+258840001111",
                "pickup_authorized_by_name": "Eng. António Muchanga",
                "pickup_authorized_by_phone": "+258849998888",
            },
            headers=headers_a,
        )
        assert reception_res.status_code == 201
        rec_id = reception_res.json()["id"]

        # -----------------------------------------------------------------------
        # 3. Orçamento Comercial (ORC) -> Aprovação pelo Cliente
        # -----------------------------------------------------------------------
        quote_res = await client.post(
            "/api/v1/workshop/quotes",
            json={
                "vehicle_id": str(vehicle_a_id),
                "client_id": str(client_a_id),
                "reception_id": str(rec_id),
                "items": [
                    {
                        "item_type": "part",
                        "description": "Filtro de Óleo Heavy Duty",
                        "part_id": str(part_a_id),
                        "quantity": 2,
                        "unit_price": 1800.0,
                    },
                    {
                        "item_type": "labor",
                        "description": "Mão de obra de substituição",
                        "quantity": 1,
                        "unit_price": 3000.0,
                    },
                ],
            },
            headers=headers_a,
        )
        assert quote_res.status_code == 201
        quote_id = quote_res.json()["id"]

        accept_res = await client.post(
            f"/api/v1/workshop/quotes/{quote_id}/accept",
            json={
                "acceptance_channel": "whatsapp",
                "accepted_by_person_name": "Eng. António Muchanga",
            },
            headers=headers_a,
        )
        assert accept_res.status_code == 200
        wo_id = accept_res.json()["work_order_id"]

        # -----------------------------------------------------------------------
        # 4. Iniciar OS & Atribuir Tarefa ao Mecânico
        # -----------------------------------------------------------------------
        start_res = await client.post(
            f"/api/v1/workshop/work-orders/{wo_id}/start",
            json={},
            headers=headers_a,
        )
        assert start_res.status_code == 200

        tasks_res = await client.get(f"/api/v1/workshop/work-orders/{wo_id}/tasks", headers=headers_a)
        assert tasks_res.status_code == 200
        tasks = tasks_res.json()
        assert len(tasks) > 0
        task_id = tasks[0]["id"]

        assign_res = await client.patch(
            f"/api/v1/workshop/work-orders/{wo_id}/tasks/{task_id}",
            json={"assigned_to": str(mechanic_a_id)},
            headers=headers_a,
        )
        assert assign_res.status_code == 200

        # Lançar sessão de mão-de-obra do mecânico (90 min)
        labor_res = await client.post(
            f"/api/v1/workshop/tasks/{task_id}/labor",
            json={
                "user_id": str(mechanic_a_id),
                "minutes_worked": 90,
            },
            headers=headers_a,
        )
        assert labor_res.status_code == 201

        # -----------------------------------------------------------------------
        # 5. Emissão Física de Peças (2 unidades) & Devolução Parcial (1 sobra)
        # -----------------------------------------------------------------------
        issue_res = await client.post(
            f"/api/v1/workshop/work-orders/{wo_id}/parts/issue",
            json={"inventory_id": str(part_a_id), "quantity": 2, "notes": "Entrega física"},
            headers=headers_a,
        )
        assert issue_res.status_code == 200
        part_return_res = await client.post(
            f"/api/v1/workshop/work-orders/{wo_id}/parts/return",
            json={
                "inventory_id": str(part_a_id),
                "quantity": 1,
                "reason": "Peça sobressalente não utilizada",
            },
            headers=headers_a,
        )
        assert part_return_res.status_code == 200

        detail_res = await client.get(
            f"/api/v1/workshop/work-orders/{wo_id}", headers=headers_a
        )
        assert detail_res.status_code == 200
        part_line = detail_res.json()["parts_issued"][0]
        assert part_line["issued_quantity"] == 2.0
        assert part_line["returned_quantity"] == 1.0
        assert part_line["net_quantity"] == 1.0
        assert part_line["net_cost"] == 1200.0

        # -----------------------------------------------------------------------
        # 6. Checkout de Ferramenta Especial & Devolução Obrigatória antes de QC
        # -----------------------------------------------------------------------
        checkout_res = await client.post(
            f"/api/v1/workshop/work-orders/{wo_id}/tool-checkouts",
            json={
                "tool_id": str(tool_a_id),
                "checkout_reference": f"CHK-{suffix}",
                "checked_out_at": datetime.now(UTC).isoformat(),
                "notes": "Utilização para aperto de cabeça de motor",
            },
            headers=headers_a,
        )
        assert checkout_res.status_code == 200
        checkout_id = checkout_res.json()["id"]

        # Devolver a ferramenta
        return_tool_res = await client.post(
            f"/api/v1/workshop/tool-checkouts/{checkout_id}/return",
            json={
                "return_reference": f"RET-{suffix}",
                "returned_at": datetime.now(UTC).isoformat(),
                "notes": "Devolvido em perfeitas condições de calibração",
            },
            headers=headers_a,
        )
        assert return_tool_res.status_code == 200

        # -----------------------------------------------------------------------
        # 7. Inspecção de Qualidade (QC) & Conclusão com Faturação Outbox
        # -----------------------------------------------------------------------
        for task in tasks:
            complete_task_res = await client.post(
                f"/api/v1/workshop/work-orders/{wo_id}/tasks/{task['id']}/complete",
                json={"notes": "Serviço concluído e verificado."},
                headers=headers_a,
            )
            assert complete_task_res.status_code == 200

        quality_res = await client.post(
            f"/api/v1/workshop/work-orders/{wo_id}/quality-check",
            json={"notes": "Inspeção final aprovada."},
            headers=headers_a,
        )
        assert quality_res.status_code == 200

        close_res = await client.post(
            f"/api/v1/workshop/work-orders/{wo_id}/close",
            json={"actual_cost": 1200, "notes": "Viatura pronta para levantamento."},
            headers=headers_a,
        )
        assert close_res.status_code == 200
        assert close_res.json()["status"] == "closed"
        assert close_res.json()["billing_status"] == "billing_pending"

        async with AsyncSessionLocal() as db:
            outbox_msg = await db.scalar(
                select(OutboxEvent).where(
                    OutboxEvent.tenant_id == tenant_a_id,
                    OutboxEvent.event_type == "workshop.internal.invoice.create",
                )
            )
            assert outbox_msg is not None

        # -----------------------------------------------------------------------
        # 8. Validação de Levantamento Autorizado de Viatura (HTTP 409 Guard)
        # -----------------------------------------------------------------------
        unauthorized_release = await client.post(
            f"/api/v1/workshop/receptions/{rec_id}/release",
            json={
                "odometer_at_release": 50050,
                "picked_up_by_name": "Pessoa Desconhecida",
                "override_unauthorized_pickup": False,
            },
            headers=headers_a,
        )
        assert unauthorized_release.status_code == 409

        authorized_release = await client.post(
            f"/api/v1/workshop/receptions/{rec_id}/release",
            json={
                "odometer_at_release": 50050,
                "picked_up_by_name": "Eng. António Muchanga",
            },
            headers=headers_a,
        )
        assert authorized_release.status_code == 201
        assert authorized_release.json()["picked_up_by_name"] == "Eng. António Muchanga"

        # -----------------------------------------------------------------------
        # 9. PROVA ESTREITA DE ISOLAMENTO MULTI-TENANT
        # Tenant B tentando aceder aos recursos do Tenant A deve receber HTTP 404
        # -----------------------------------------------------------------------
        # Attempt 1: Leitura de Detalhes da OS do Tenant A usando headers do Tenant B
        wo_cross_res = await client.get(f"/api/v1/workshop/work-orders/{wo_id}", headers=headers_b)
        assert wo_cross_res.status_code == 404

        # Attempt 2: Leitura do Orçamento do Tenant A usando headers do Tenant B
        quote_cross_res = await client.get(f"/api/v1/workshop/quotes/{quote_id}", headers=headers_b)
        assert quote_cross_res.status_code == 404

        # Attempt 3: Leitura de Ferramenta do Tenant A usando headers do Tenant B
        tool_cross_res = await client.get(f"/api/v1/workshop/tools/{tool_a_id}/calibration-history", headers=headers_b)
        assert tool_cross_res.status_code == 404

        # Attempt 4: Relatório de Rentabilidade da OS do Tenant A via Tenant B
        profit_cross_res = await client.get(f"/api/v1/workshop/work-orders/{wo_id}/profitability", headers=headers_b)
        assert profit_cross_res.status_code == 404
