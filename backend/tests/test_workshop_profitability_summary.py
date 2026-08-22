import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jwt as _jwt

from app.config import get_settings
from app.core.errors import ApiError
from app.database import AsyncSessionLocal
from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.clients.models import Client
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle
from app.modules.workshop import labor_service
from app.modules.workshop.models import (
    MaintenancePartUsed,
    SparePartInventory,
    TaskLaborLog,
    WorkOrder,
    WorkOrderTask,
    WorkshopStaffRate,
)


def auth_headers(
    tenant_id: UUID | str, user_id: UUID | str | None = None, role: str = "admin"
) -> dict:
    settings = get_settings()
    token = _jwt.encode(
        {
            "typ": "access",
            "sub": f"user:{user_id or uuid4()}",
            "role": role,
            "scope": "dashboard",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id or uuid4()),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


@pytest.mark.asyncio
async def test_empty_tenant_profitability_summary():
    """Teste #1: Tenant sem OSs devolve HTTP 200 OK com métricas a zero e lista vazia."""
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Tenant Vazio {suffix}",
            slug=f"tenant-vazio-{suffix}",
            product_modules=["tms", "oficina"],
        )
        db.add(tenant)
        await db.flush()
        tenant_id = tenant.id
        await db.commit()

    async with AsyncSessionLocal() as db:
        summary = await labor_service.get_workshop_profitability_summary(db, tenant_id)

    assert summary["summary"]["confirmed_revenue"] == 0.0
    assert summary["summary"]["projected_revenue"] == 0.0
    assert summary["summary"]["total_cost"] == 0.0
    assert summary["summary"]["confirmed_gross_profit"] == 0.0
    assert summary["summary"]["negative_margin_count"] == 0
    assert summary["summary"]["total_work_orders"] == 0
    assert summary["work_orders"] == []


@pytest.mark.asyncio
async def test_shared_calculation_parity_and_revenue_segregation():
    """Teste #2: Paridade entre endpoint singular e sumário + segregação de receita confirmada vs projetada."""
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Oficina Paridade {suffix}",
            slug=f"oficina-paridade-{suffix}",
            product_modules=["tms", "oficina"],
        )
        db.add(tenant)
        await db.flush()

        client = Client(
            tenant_id=tenant.id,
            trading_name=f"Cliente {suffix}",
            nuit=f"111222{suffix[:3]}",
            client_type="organization",
        )
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"PAR-{suffix[:4].upper()}",
            current_km=10000,
            customer_client_id=client.id,
        )
        user = User(
            tenant_id=tenant.id,
            email=f"user.{suffix}@rotas.mz",
            password_hash="hash",
            full_name="Mecânico 1",
            role="admin",
        )
        db.add_all([client, vehicle, user])
        await db.flush()

        # Configurar taxa horária de Mão-de-Obra
        rate = WorkshopStaffRate(
            tenant_id=tenant.id,
            user_id=user.id,
            hourly_rate=Decimal("1000.00"),
            effective_from=date.today() - timedelta(days=10),
        )
        db.add(rate)
        await db.flush()

        # Criar Peça
        part = SparePartInventory(
            tenant_id=tenant.id,
            sku=f"PART-{suffix}",
            name="Filtro Paridade",
            current_quantity=Decimal("10.000"),
            average_unit_cost=Decimal("500.00"),
        )
        db.add(part)
        await db.flush()

        # Criar OS com estimativa inicial de 5.000 MT
        wo = WorkOrder(
            tenant_id=tenant.id,
            vehicle_id=vehicle.id,
            work_order_number=f"OS-PAR-{suffix}",
            planned_work="Reparação e substituição de filtro",
            estimated_cost=Decimal("5000.00"),
            status="in_progress",
        )
        db.add(wo)
        await db.flush()

        task = WorkOrderTask(
            tenant_id=tenant.id, work_order_id=wo.id, description="Tarefa 1", status="in_progress"
        )
        db.add(task)
        await db.flush()

        # 60 minutos de mão-de-obra = 1.000 MT
        labor = TaskLaborLog(
            tenant_id=tenant.id,
            work_order_task_id=task.id,
            user_id=user.id,
            completed_at=datetime.now(UTC),
            minutes_worked=60,
            hourly_rate_applied=Decimal("1000.00"),
            total_labor_cost=Decimal("1000.00"),
        )
        # Peça utilizada: 1 unidade x 500 MT = 500 MT
        part_used = MaintenancePartUsed(
            tenant_id=tenant.id,
            work_order_id=wo.id,
            inventory_id=part.id,
            request_reference="REQ-1",
            quantity=Decimal("1.000"),
            returned_quantity=Decimal("0.000"),
            unit_cost=Decimal("500.00"),
            total_cost=Decimal("500.00"),
            net_total_cost=Decimal("500.00"),
        )
        db.add_all([labor, part_used])
        await db.flush()

        tenant_id = tenant.id
        wo_id = wo.id
        await db.commit()

    # 1. Apuração enquanto não facturada (apenas projected_revenue)
    async with AsyncSessionLocal() as db:
        single_rep = await labor_service.get_work_order_profitability(db, tenant_id, wo_id)
        summary_rep = await labor_service.get_workshop_profitability_summary(db, tenant_id)

    assert single_rep["confirmed_revenue"] == 0.0
    assert single_rep["projected_revenue"] == 5000.0
    assert single_rep["total_cost"] == 1500.0  # 1000 MO + 500 Peça

    wo_sum = summary_rep["work_orders"][0]
    assert wo_sum["confirmed_revenue"] == 0.0
    assert wo_sum["projected_revenue"] == 5000.0
    assert wo_sum["total_cost"] == 1500.0
    assert wo_sum["margin_mzn"] == 3500.0  # 5000 - 1500

    # 2. Emitir Fatura de 6.000 MT para esta OS (confirming revenue)
    now_utc = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        b_doc = BillingDocument(
            tenant_id=tenant_id,
            client_name="Cliente Paridade",
            document_type="invoice",
            invoice_number=f"FT-{suffix}",
            status="issued",
            total_amount=Decimal("6000.00"),
            billing_period_start=now_utc,
            billing_period_end=now_utc,
        )
        db.add(b_doc)
        await db.flush()

        b_item = BillingItem(
            tenant_id=tenant_id,
            billing_document_id=b_doc.id,
            work_order_id=wo_id,
            delivered_at=now_utc,
            amount=Decimal("6000.00"),
        )
        db.add(b_item)
        await db.commit()

    # 3. Apuração pós-faturação (confirmed_revenue = 6000.0)
    async with AsyncSessionLocal() as db:
        single_post = await labor_service.get_work_order_profitability(db, tenant_id, wo_id)
        summary_post = await labor_service.get_workshop_profitability_summary(db, tenant_id)

    assert single_post["confirmed_revenue"] == 6000.0
    assert single_post["projected_revenue"] == 0.0
    assert single_post["total_cost"] == 1500.0
    assert single_post["gross_profit_mzn"] == 4500.0  # 6000 - 1500

    wo_post = summary_post["work_orders"][0]
    assert wo_post["confirmed_revenue"] == 6000.0
    assert wo_post["projected_revenue"] == 0.0
    assert wo_post["total_cost"] == 1500.0
    assert wo_post["margin_mzn"] == 4500.0
    assert summary_post["summary"]["confirmed_revenue"] == 6000.0
    assert summary_post["summary"]["confirmed_gross_profit"] == 4500.0


@pytest.mark.asyncio
async def test_negative_margin_and_foreign_404_guard():
    """Teste #3 & #4: Deteção de OS com prejuízo + Guard 404 estrito ao filtrar por cliente/viatura de outro tenant."""
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        tenant_a = Tenant(
            name=f"Tenant A {suffix}",
            slug=f"tenant-a-{suffix}",
            product_modules=["tms", "oficina"],
        )
        tenant_b = Tenant(
            name=f"Tenant B {suffix}",
            slug=f"tenant-b-{suffix}",
            product_modules=["tms", "oficina"],
        )
        db.add_all([tenant_a, tenant_b])
        await db.flush()

        user_a = User(
            tenant_id=tenant_a.id,
            email=f"user.a.{suffix}@rotas.mz",
            password_hash="hash",
            full_name="Mecânico A",
            role="admin",
        )
        client_b = Client(
            tenant_id=tenant_b.id,
            trading_name=f"Cliente B {suffix}",
            nuit=f"999888{suffix[:3]}",
            client_type="organization",
        )
        vehicle_b = Vehicle(tenant_id=tenant_b.id, plate=f"TEN-B-{suffix[:4].upper()}")
        db.add_all([user_a, client_b, vehicle_b])
        await db.flush()

        # OS no Tenant A com prejuízo (custo 3000 > receita estimada 1000)
        wo_a = WorkOrder(
            tenant_id=tenant_a.id,
            work_order_number=f"OS-A-{suffix}",
            planned_work="Reparação geral",
            estimated_cost=Decimal("1000.00"),
            status="in_progress",
        )
        db.add(wo_a)
        await db.flush()

        task_a = WorkOrderTask(
            tenant_id=tenant_a.id, work_order_id=wo_a.id, description="Fix", status="in_progress"
        )
        db.add(task_a)
        await db.flush()

        labor_a = TaskLaborLog(
            tenant_id=tenant_a.id,
            work_order_task_id=task_a.id,
            user_id=user_a.id,
            completed_at=datetime.now(UTC),
            minutes_worked=180,
            hourly_rate_applied=Decimal("1000.00"),
            total_labor_cost=Decimal("3000.00"),
        )
        db.add(labor_a)
        await db.flush()

        tenant_a_id = tenant_a.id
        client_b_id = client_b.id
        vehicle_b_id = vehicle_b.id
        await db.commit()

    async with AsyncSessionLocal() as db:
        summary_a = await labor_service.get_workshop_profitability_summary(db, tenant_a_id)

    assert summary_a["summary"]["negative_margin_count"] == 1
    assert summary_a["work_orders"][0]["is_profitable"] is False
    assert summary_a["work_orders"][0]["margin_mzn"] == -2000.0

    # Tentar consultar no Tenant A com cliente ou viatura pertencente ao Tenant B -> HTTP 404
    async with AsyncSessionLocal() as db:
        with pytest.raises(ApiError) as exc_client:
            await labor_service.get_workshop_profitability_summary(
                db, tenant_a_id, client_id=client_b_id
            )
        assert exc_client.value.status_code == 404
        assert exc_client.value.code == "client_not_found"

        with pytest.raises(ApiError) as exc_vehicle:
            await labor_service.get_workshop_profitability_summary(
                db, tenant_a_id, vehicle_id=vehicle_b_id
            )
        assert exc_vehicle.value.status_code == 404
        assert exc_vehicle.value.code == "vehicle_not_found"


@pytest.mark.asyncio
async def test_rbac_finance_read_guard_api(async_client):
    """Teste #5: Mecânico sem permissão WORKSHOP_FINANCE_READ recebe HTTP 403 Forbidden ao tentar aceder ao sumário."""
    suffix = uuid4().hex[:6]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(
            name=f"Tenant RBAC {suffix}",
            slug=f"tenant-rbac-{suffix}",
            product_modules=["tms", "oficina"],
        )
        db.add(tenant)
        await db.flush()
        tenant_id = tenant.id
        user_mech = User(
            tenant_id=tenant_id,
            email=f"mech.{suffix}@rotas.mz",
            password_hash="hash",
            full_name="Mecânico",
            role="mechanic",
        )
        db.add(user_mech)
        await db.flush()
        user_mech_id = user_mech.id
        await db.commit()

    headers_mech = auth_headers(tenant_id, user_id=str(user_mech_id), role="mechanic")
    res = await async_client.get("/api/v1/workshop/profitability/summary", headers=headers_mech)
    assert res.status_code == 403
