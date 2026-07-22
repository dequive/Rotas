from app.modules.workshop.models import WorkOrder
from app.modules.workshop.schemas import WorkOrderCloseRequest
from app.modules.workshop.service import close_work_order
import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import pytest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from uuid import uuid4
import pytest
from app.core.errors import ApiError



from sqlalchemy import select
from app.modules.billing.models import BillingDocument, BillingItem, ClientPayment
from app.modules.workshop.workshop_billing_service import confirm_workshop_invoice
from app.modules.clients.models import Client
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.catalog_models import ServiceCatalogItem
from app.modules.workshop.inventory_service import (
    create_part_reservations,
    issue_parts_for_work_order,
    record_inventory_adjustment,
)
from app.modules.workshop.labor_service import (
    add_task_labor_session,
    get_staff_hourly_rate,
    get_work_order_profitability,
    set_staff_hourly_rate,
    void_task_labor_session,
)
from app.modules.workshop.models import (
    MaintenancePartUsed,
    SparePartInventory,
    TaskLaborLog,
    WorkOrder,
    WorkOrderTask,
    WorkshopStaffRate,
)
from app.modules.workshop.quote_models import WorkshopQuote, WorkshopQuoteItem
from app.modules.workshop.quote_schemas import QuoteCreate as WorkshopQuoteCreate, QuoteItemCreate as WorkshopQuoteItemCreate
from app.modules.workshop.quote_service import accept_quote, create_quote
from app.modules.workshop.service import create_work_order, close_work_order
from app.modules.workshop.schemas import WorkOrderCreate
from app.modules.workshop.workshop_billing_service import create_workshop_invoice


@pytest.mark.asyncio
async def test_staff_hourly_rate_historical_effective_from_selection(db, tenant_id, test_user):
    """Teste #1: Seleção histórica da taxa horária com base na data completed_at (effective_from <= completed_at DESC LIMIT 1)."""


    # Taxa 1: 400 MZN a partir de 01/01/2026
    rate1 = await set_staff_hourly_rate(db, tenant_id, test_user.id, 400.00, date(2026, 1, 1), actor_id=test_user.id)
    # Taxa 2: 600 MZN a partir de 01/06/2026
    rate2 = await set_staff_hourly_rate(db, tenant_id, test_user.id, 600.00, date(2026, 6, 1), actor_id=test_user.id)

    # 1. Sessão concluída a 15/05/2026 -> Deve aplicar Taxa 1 (400 MZN)
    rate_may = await get_staff_hourly_rate(db, tenant_id, test_user.id, datetime(2026, 5, 15, tzinfo=UTC))
    assert rate_may == Decimal("400.00")

    # 2. Sessão concluída a 05/06/2026 -> Deve aplicar Taxa 2 (600 MZN)
    rate_june = await get_staff_hourly_rate(db, tenant_id, test_user.id, datetime(2026, 6, 5, tzinfo=UTC))
    assert rate_june == Decimal("600.00")


@pytest.mark.asyncio
async def test_multi_mechanic_labor_logging_and_void_exclusion(db, tenant_id, test_user):
    """Teste #2: Múltiplos mecânicos na mesma tarefa e estorno (Void) com exclusão do cálculo de custo."""


    # Mecânico A (Taxa 500 MZN/h) e Mecânico B (Taxa 300 MZN/h)
    mec_a_id = test_user.id
    mec_b_id = test_user.id  # Para teste, reutiliza utilizador com taxas diferentes por data

    rate_a = await set_staff_hourly_rate(db, tenant_id, mec_a_id, 500.00, date(2026, 1, 1))

    vehicle = Vehicle(tenant_id=tenant_id, plate="LAB-01")
    db.add(vehicle)
    await db.flush()

    wo_payload = WorkOrderCreate(vehicle_id=vehicle.id, planned_work="Reparação Motor")
    wo = await create_work_order(db, tenant_id, wo_payload, actor_id=test_user.id)
    task = WorkOrderTask(tenant_id=tenant_id, work_order_id=wo["id"], description="Diagnóstico e Desmontagem", status="in_progress")
    db.add(task)
    await db.flush()

    # 1. Registar Log 1: Mecânico A trabalhou 120 minutos (2h * 500 = 1.000 MZN)
    log1 = await add_task_labor_session(
        db, tenant_id, task.id, mec_a_id, minutes_worked=120, completed_at=datetime(2026, 2, 1, tzinfo=UTC), actor_id=test_user.id
    )
    assert log1.total_labor_cost == Decimal("1000.00")

    # 2. Registar Log 2 (Erróneo): Mecânico A anotou 300 minutos por engano (5h * 500 = 2.500 MZN)
    log2 = await add_task_labor_session(
        db, tenant_id, task.id, mec_a_id, minutes_worked=300, completed_at=datetime(2026, 2, 1, tzinfo=UTC), actor_id=test_user.id
    )
    assert log2.total_labor_cost == Decimal("2500.00")

    # 3. Estornar (Void) Log 2 por erro de digitação
    voided_log2 = await void_task_labor_session(db, tenant_id, log2.id, void_reason="Erro de digitação de minutos", actor_id=test_user.id)
    assert voided_log2.voided_at is not None
    assert voided_log2.void_reason == "Erro de digitação de minutos"

    # 4. Apurar rentabilidade preliminar: Apenas Log 1 entra no custo de mão de obra (1.000 MZN)
    profitability = await get_work_order_profitability(db, tenant_id, wo["id"])
    assert profitability["total_labor_minutes"] == 120  # Excluiu os 300 min estornados!
    assert profitability["total_labor_cost"] == 1000.0  # Excluiu os 2500 MZN estornados!


@pytest.mark.asyncio
async def test_post_billing_labor_immutability_guard_409(db, tenant_id, test_user):
    """Teste #3: Guarda 409 de imutabilidade pós-faturação ao tentar adicionar ou estornar mão de obra."""


    client = Client(tenant_id=tenant_id, trading_name="Empresa B Lda", nuit="888000111")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="IMMUT-01", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    wo_payload = WorkOrderCreate(vehicle_id=vehicle.id, client_id=client.id, origin_type="reception", planned_work="Troca")
    wo = await create_work_order(db, tenant_id, wo_payload, actor_id=test_user.id)
    await set_staff_hourly_rate(db, tenant_id, test_user.id, 500.00, date(2026, 1, 1))
    task = WorkOrderTask(tenant_id=tenant_id, work_order_id=wo["id"], description="Troca Pastilhas", status="completed", completed_by=test_user.id, actual_minutes=60)
    db.add(task)
    await db.flush()

    # Adicionar mão de obra inicial (60 min)
    log = await add_task_labor_session(db, tenant_id, task.id, test_user.id, minutes_worked=60, actor_id=test_user.id)

    # Emitir fatura de oficina e confirmar
    wo_obj = await db.get(WorkOrder, wo["id"])
    wo_obj.status = "quality_check"
    wo_obj.labor_cost = Decimal("1000.00")
    await db.flush()
    await close_work_order(db, tenant_id, wo["id"], payload=WorkOrderCloseRequest(notes="Done"), actor_id=test_user.id)
    invoice = await create_workshop_invoice(db, tenant_id, wo["id"], actor_id=test_user.id)
    await confirm_workshop_invoice(db, tenant_id, invoice["id"], actor_id=test_user.id)

    # 1. Tentar adicionar nova sessão de mão de obra -> Retorna HTTP 409 work_order_already_billed
    with pytest.raises(ApiError) as exc_add:
        await add_task_labor_session(db, tenant_id, task.id, test_user.id, minutes_worked=30, actor_id=test_user.id)
    assert exc_add.value.code == "work_order_already_billed"
    assert exc_add.value.status_code == 409

    # 2. Tentar estornar sessão existente -> Retorna HTTP 409 work_order_already_billed
    with pytest.raises(ApiError) as exc_void:
        await void_task_labor_session(db, tenant_id, log.id, void_reason="Tentativa pós-fatura", actor_id=test_user.id)
    assert exc_void.value.code == "work_order_already_billed"
    assert exc_void.value.status_code == 409


@pytest.mark.asyncio
async def test_work_order_profitability_with_multi_quote_consolidated_invoice_fk_join(db, tenant_id, test_user):
    """Teste #4: Validação da Integridade por FK Direta (BillingItem.work_order_id) com Orçamento Original + Orçamento Suplementar."""


    client = Client(tenant_id=tenant_id, trading_name="Cliente Frota X", nuit="777000222")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="PROFIT-01", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    # Peça de Stock (Filtro) a 500 MZN WACC
    part = SparePartInventory(
        tenant_id=tenant_id, sku="OIL-10W40", name="Filtro de Óleo HD", current_quantity=Decimal("10.000"), average_unit_cost=Decimal("500.00")
    )
    db.add(part)
    await db.flush()

    # 1. Orçamento Original (10.000 MZN)
    q1_create = WorkshopQuoteCreate(
        client_id=client.id,
        vehicle_id=vehicle.id,
        items=[WorkshopQuoteItemCreate(item_type="labor", description="Serviço Base", quantity=1.0, unit_price=10000.0)],
    )
    q1 = await create_quote(db, tenant_id, q1_create, actor_id=test_user.id)
    await accept_quote(db, tenant_id, q1["id"], actor_id=test_user.id)

    # Buscar a OS criada automaticamente pelo accept_quote
    wo_res = await db.execute(select(WorkOrder).where(WorkOrder.tenant_id == tenant_id, WorkOrder.vehicle_id == vehicle.id))
    wo = wo_res.scalars().first()
    assert wo is not None

    # 2. Orçamento Suplementar (4.000 MZN de peças adicionais)
    q2_create = WorkshopQuoteCreate(
        client_id=client.id,
        vehicle_id=vehicle.id,
        is_supplemental=True,
        related_work_order_id=wo.id,
        items=[WorkshopQuoteItemCreate(item_type="part", description="Filtro de Óleo HD", quantity=2.0, unit_price=2000.0, part_id=part.id)],
    )
    q2 = await create_quote(db, tenant_id, q2_create, actor_id=test_user.id)
    await accept_quote(db, tenant_id, q2["id"], actor_id=test_user.id)

    # Consumir as 2 unidades de peça na OS (Custo WACC = 2 * 500 = 1.000 MZN)
    await issue_parts_for_work_order(db, tenant_id, wo.id, part.id, Decimal("2.0"), actor_id=test_user.id)

    # Adicionar tarefa e registar mão de obra (180 min = 3h @ 500 MZN/h = 1.500 MZN)
    await set_staff_hourly_rate(db, tenant_id, test_user.id, 500.00, date(2026, 1, 1))
    task = WorkOrderTask(tenant_id=tenant_id, work_order_id=wo.id, description="Serviço Base", status="completed", completed_by=test_user.id, actual_minutes=60)
    db.add(task)
    await db.flush()

    await add_task_labor_session(db, tenant_id, task.id, test_user.id, minutes_worked=180, actor_id=test_user.id)

    # 3. Emitir Fatura Consolidada de Oficina (Soma Q1 10.000 + Q2 4.000 = 14.000 MZN)
    wo.status = "quality_check"
    await db.flush()
    invoice = await create_workshop_invoice(db, tenant_id, wo.id, actor_id=test_user.id)
    await confirm_workshop_invoice(db, tenant_id, invoice["id"], actor_id=test_user.id)

    # 4. Apurar Rentabilidade com verificação da Chave Estrangeira BillingItem.work_order_id
    profitability = await get_work_order_profitability(db, tenant_id, wo.id)

    # Validações Estritas:
    # Receita Faturada Consolidada = 14.000.00 MZN
    assert profitability["total_revenue"] == 14000.0
    # Custo Mão de Obra = 1.500.00 MZN
    assert profitability["total_labor_cost"] == 1500.0
    # Custo Peças WACC = 1.000.00 MZN
    assert profitability["total_parts_cost"] == 1000.0
    # Custo Total = 2.500.00 MZN
    assert profitability["total_cost"] == 2500.0
    # Margem Bruta MZN = 14.000 - 2.500 = 11.500.00 MZN
    assert profitability["gross_profit_mzn"] == 11500.0
    # Margem Bruta % = (11.500 / 14.000) * 100 = 82.14%
    assert profitability["gross_profit_margin_percent"] == 82.14
    assert profitability["is_profitable"] is True
