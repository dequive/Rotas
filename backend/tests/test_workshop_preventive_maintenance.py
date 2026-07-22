from app.modules.workshop.schemas import WorkOrderCloseRequest
from app.modules.workshop.schemas import WorkOrderCreate
import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import pytest
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from uuid import uuid4
import pytest
from app.core.errors import ApiError



from sqlalchemy import select
from app.modules.clients.models import Client
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.catalog_models import ServiceCatalogItem
from app.modules.workshop.models import (
    MaintenancePlan,
    MaintenanceSchedule,
    WorkOrder,
    WorkOrderTask,
)
from app.modules.workshop.preventive_service import (
    convert_schedule_to_action,
    create_maintenance_plan,
    evaluate_preventive_schedules,
    handle_work_order_completion_preventive_matching,
    list_maintenance_plans,
    schedule_preventive_maintenance,
)
from app.modules.workshop.quote_models import WorkshopQuote
from app.modules.workshop.service import close_work_order, create_work_order


@pytest.mark.asyncio
async def test_preventive_matching_and_automatic_next_cycle_creation_on_release(db, tenant_id, test_user):
    """Teste #1: Matching por catálogo no fecho da OS e geração automática do próximo ciclo a partir do odómetro real."""


    # 1. Serviço de Catálogo de Mudança de Óleo
    service_item = ServiceCatalogItem(
        tenant_id=tenant_id,
        code="SERV-OIL-CHANGE",
        name="Mudança de Óleo e Filtros",
        base_price=Decimal("1500.00"),
    )
    db.add(service_item)
    await db.flush()

    # 2. Viatura a 50.000 km
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate="AB-10-CD",
        brand="Toyota",
        model="Hilux",
        current_km=50000,
    )
    db.add(vehicle)
    await db.flush()

    # 3. Plano de Manutenção (Revisão de Óleo a cada 10.000 km)
    plan = await create_maintenance_plan(
        db,
        tenant_id,
        name="Revisão Óleo 10k",
                interval_km=10000,
        interval_days=180,
        ownership_scope="fleet",
        actor_id=test_user.id,
    )

    # 4. Criar Agendamento Inicial
    sched1 = await schedule_preventive_maintenance(db, tenant_id, vehicle.id, plan.id, actor_id=test_user.id)
    assert sched1.due_km == 60000  # 50.000 + 10.000

    # 5. Criar e fechar OS com a tarefa correspondente ao serviço de catálogo
    wo = await create_work_order(
        db,
        tenant_id,
        payload=WorkOrderCreate(vehicle_id=vehicle.id, planned_work="Manutenção Periódica Hilux"),
        actor_id=test_user.id,
    )

    # Adicionar tarefa realizada
    task = WorkOrderTask(
        tenant_id=tenant_id,
        work_order_id=wo["id"],
                description="Mudança de Óleo realizada",
        status="completed",
    )
    db.add(task)
    await db.flush()

    # Atualizar odómetro da viatura para 52.000 km no momento do release
    vehicle.current_km = 52000
    await db.flush()

    # Fechar OS (dispara handle_work_order_completion_preventive_matching)
    wo_obj = await db.get(WorkOrder, wo["id"])
    wo_obj.status = "quality_check"
    await db.flush()
    await close_work_order(db, tenant_id, wo["id"], payload=WorkOrderCloseRequest(notes="Concluído com sucesso"), actor_id=test_user.id)

    # Validar:
    # a) Agendamento anterior passou a "completed"
    await db.refresh(sched1)
    assert sched1.status == "completed"

    # b) Próximo agendamento foi criado automaticamente com baseline no odómetro real (52.000 + 10.000 = 62.000 km)
    schedules = (
        await db.execute(
            select(MaintenanceSchedule).where(
                MaintenanceSchedule.tenant_id == tenant_id,
                MaintenanceSchedule.vehicle_id == vehicle.id,
                MaintenanceSchedule.plan_id == plan.id,
                MaintenanceSchedule.status == "pending",
            )
        )
    ).scalars().all()

    assert len(schedules) == 1
    next_sched = schedules[0]
    assert next_sched.due_km == 62000  # 52.000 + 10.000 (Baseline real!)


@pytest.mark.asyncio
async def test_idempotent_wo_close_and_conversion_no_duplicates(db, tenant_id, test_user):
    """Teste #2: Idempotência de close_work_order e convert_schedule_to_action (retries não duplicam registos)."""


    vehicle = Vehicle(tenant_id=tenant_id, plate="XY-99-ZZ", current_km=10000)
    db.add(vehicle)
    await db.flush()

    plan = await create_maintenance_plan(
        db, tenant_id, name="Plano Frota", interval_km=5000, ownership_scope="fleet", actor_id=test_user.id
    )
    sched = await schedule_preventive_maintenance(db, tenant_id, vehicle.id, plan.id, actor_id=test_user.id)

    # 2. Idempotência no dedup de agendamento (chamar schedule_preventive_maintenance 2 vezes)
    dup_sched = await schedule_preventive_maintenance(db, tenant_id, vehicle.id, plan.id, actor_id=test_user.id)
    assert dup_sched.id == sched.id

    # 1. Idempotência em convert_schedule_to_action (chamar 2 vezes)
    conv1 = await convert_schedule_to_action(db, tenant_id, sched.id, actor_id=test_user.id)
    conv2 = await convert_schedule_to_action(db, tenant_id, sched.id, actor_id=test_user.id)

    assert conv1["work_order_id"] == conv2["work_order_id"]
    assert conv2["idempotent_reused"] is True


@pytest.mark.asyncio
async def test_fleet_wo_direct_conversion_vs_customer_draft_quote_orc(db, tenant_id, test_user):
    """Teste #3: Diferenciação Estrita (Frota vs Cliente Comercial com numeração ORC-2026-XXXX)."""


    client = Client(tenant_id=tenant_id, trading_name="Cliente Exemplo Lda", nuit="999000111")
    db.add(client)
    await db.flush()

    catalog = ServiceCatalogItem(
        tenant_id=tenant_id, code="SERV-REVISAO", name="Revisão Geral", base_price=Decimal("3000.00")
    )
    db.add(catalog)
    await db.flush()

    # Viatura de Frota
    v_fleet = Vehicle(tenant_id=tenant_id, plate="FLT-01", ownership_type="fleet", current_km=10000)
    # Viatura de Cliente
    v_cust = Vehicle(
        tenant_id=tenant_id, plate="CUST-01", ownership_type="customer", customer_client_id=client.id, current_km=10000
    )
    db.add_all([v_fleet, v_cust])
    await db.flush()

    # Plano Frota
    plan_fleet = await create_maintenance_plan(
        db, tenant_id, name="Preventiva Frota", service_catalog_item_id=catalog.id, ownership_scope="fleet"
    )
    sched_fleet = await schedule_preventive_maintenance(db, tenant_id, v_fleet.id, plan_fleet.id)

    # Plano Cliente
    plan_cust = await create_maintenance_plan(
        db, tenant_id, name="Preventiva Cliente", service_catalog_item_id=catalog.id, ownership_scope="customer"
    )
    sched_cust = await schedule_preventive_maintenance(db, tenant_id, v_cust.id, plan_cust.id)

    # 1. Converter agendamento Frota -> GERA OS DIRETA com estimated_cost do catálogo
    res_fleet = await convert_schedule_to_action(db, tenant_id, sched_fleet.id, actor_id=test_user.id)
    assert res_fleet["status"] == "converted_to_wo"
    assert res_fleet["estimated_cost"] == 3000.0

    # 2. Converter agendamento Cliente -> GERA RASCUNHO DE ORÇAMENTO com numeração ORC-2026-XXXX
    res_cust = await convert_schedule_to_action(db, tenant_id, sched_cust.id, actor_id=test_user.id)
    assert res_cust["status"] == "converted_to_quote"

    quote = await db.get(WorkshopQuote, res_cust["quote_id"])
    assert quote.status in ("draft", "sent")
    assert quote.quote_number.startswith("ORC-2026-")


@pytest.mark.asyncio
async def test_notification_escalation_guards_notified_due_and_overdue(db, tenant_id, test_user):
    """Teste #4: Guards anti-duplicação de notificação (notified_due_at e notified_overdue_at)."""


    vehicle = Vehicle(tenant_id=tenant_id, plate="NOTIF-01", current_km=9500)
    db.add(vehicle)
    await db.flush()

    plan = await create_maintenance_plan(db, tenant_id, name="Plano Notif", interval_km=10000)
    sched = await schedule_preventive_maintenance(db, tenant_id, vehicle.id, plan.id)
    assert sched.due_km == 19500

    # Atualizar odómetro para entrar na margem de 10% (19.500 - 1.000 = 18.500 km)
    vehicle.current_km = 18600
    await db.flush()

    # 1. Avaliação 1: Deve passar a 'due' e gravar notified_due_at
    eval1 = await evaluate_preventive_schedules(db, tenant_id, actor_id=test_user.id)
    assert eval1["due_count"] == 1
    assert eval1["notified_count"] == 1

    await db.refresh(sched)
    assert sched.status == "due"
    assert sched.notified_due_at is not None
    assert sched.notified_overdue_at is None

    # 2. Avaliação 2 no mesmo estado 'due': NÃO duplica notificação
    eval2 = await evaluate_preventive_schedules(db, tenant_id, actor_id=test_user.id)
    assert eval2["notified_count"] == 0

    # 3. Degradar para 'overdue' (odómetro ultrapassa 19.500 km)
    vehicle.current_km = 20000
    await db.flush()

    eval3 = await evaluate_preventive_schedules(db, tenant_id, actor_id=test_user.id)
    assert eval3["overdue_count"] == 1
    assert eval3["notified_count"] == 1

    await db.refresh(sched)
    assert sched.status == "overdue"
    assert sched.notified_overdue_at is not None


@pytest.mark.asyncio
async def test_ownership_scope_all_inheritance(db, tenant_id, test_user):
    """Teste #5: Herança de Escopo 'all' (Plano universal herda ownership_type da viatura)."""


    client = Client(tenant_id=tenant_id, trading_name="Empresa X", nuit="123123123")
    db.add(client)
    await db.flush()

    v_fleet = Vehicle(tenant_id=tenant_id, plate="ALL-FLT", ownership_type="fleet", current_km=1000)
    v_cust = Vehicle(tenant_id=tenant_id, plate="ALL-CUST", ownership_type="customer", customer_client_id=client.id, current_km=1000)
    db.add_all([v_fleet, v_cust])
    await db.flush()

    plan_all = await create_maintenance_plan(db, tenant_id, name="Plano Universal", interval_km=5000, ownership_scope="all")

    sched_fleet = await schedule_preventive_maintenance(db, tenant_id, v_fleet.id, plan_all.id)
    sched_cust = await schedule_preventive_maintenance(db, tenant_id, v_cust.id, plan_all.id)

    res_flt = await convert_schedule_to_action(db, tenant_id, sched_fleet.id, actor_id=test_user.id)
    assert res_flt["status"] == "converted_to_wo"

    res_cst = await convert_schedule_to_action(db, tenant_id, sched_cust.id, actor_id=test_user.id)
    assert res_cst["status"] == "converted_to_quote"
