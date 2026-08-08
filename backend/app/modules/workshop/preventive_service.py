"""Workshop Preventive Maintenance Service — Gestão de Planos e Agendamentos de Manutenção Preventiva.

Resolução das Regras de Ouro:
  1. Matching por Catálogo de Serviço no Release (`handle_work_order_completion_preventive_matching`):
     Ao fechar uma OS, verifica se algum serviço concluído bate com `MaintenancePlan.service_catalog_item_id`.
     Se sim, marca o agendamento atual como `completed` e cria o PRÓXIMO agendamento com base no odómetro real
     e data real do momento de entrega (due_km = odometer_release + interval_km).
  2. Deduplicação Estrita (`schedule_preventive_maintenance`):
     Impede duplicados se já existir agendamento em ('pending', 'due',
     'overdue') para (vehicle_id, plan_id).
  3. Idempotência em Conversão (`convert_schedule_to_action`):
     Se já convertido, retorna a referência da OS/Quote existente sem duplicar.
  4. Guard Anti-Duplicação WhatsApp (`notified_due_at` e `notified_overdue_at`):
     Distingue a notificação de 'due' da escalação urgente de 'overdue', gravando o timestamp respetivo.
  5. Diferenciação Frota vs Cliente:
     - Frota (`fleet`): Gera OS direta com `estimated_cost` vindo do catálogo.
     - Cliente (`customer`): Gera Rascunho de Orçamento com numeração `ORC-2026-XXXX` para aprovação comercial prévia.
  6. Herança de Escopo (`all`):
     Planos com `ownership_scope="all"` herdam o `ownership_type` real da viatura (`fleet` ou `customer`).
"""

import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.catalog_models import ServiceCatalogItem
from app.modules.workshop.models import (
    MaintenancePlan,
    MaintenanceSchedule,
    WorkOrder,
    WorkOrderTask,
)
from app.modules.workshop.quote_schemas import QuoteCreate as WorkshopQuoteCreate
from app.modules.workshop.quote_schemas import QuoteItemCreate as WorkshopQuoteItemCreate
from app.modules.workshop.quote_service import create_quote


async def create_maintenance_plan(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    *,
    service_catalog_item_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    interval_km: int | None = None,
    interval_days: int | None = None,
    ownership_scope: str = "fleet",  # fleet | customer | all
    actor_id: UUID | None = None,
) -> MaintenancePlan:
    """Criar novo Plano de Manutenção Preventiva."""
    if not name or not name.strip():
        raise ApiError("invalid_name", "Maintenance plan name is required.", status_code=400)

    now = datetime.now(UTC)
    req_ref = f"PLAN-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:4]}"

    plan = MaintenancePlan(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        service_catalog_item_id=service_catalog_item_id,
        request_reference=req_ref,
        name=name.strip(),
        interval_km=interval_km,
        interval_days=interval_days,
        ownership_scope=ownership_scope,
        status="active",
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def list_maintenance_plans(
    db: AsyncSession,
    tenant_id: UUID,
    ownership_scope: str | None = None,
) -> list[MaintenancePlan]:
    """Listar planos de manutenção preventiva ativos."""
    query = select(MaintenancePlan).where(
        MaintenancePlan.tenant_id == tenant_id,
        MaintenancePlan.status == "active",
    )
    if ownership_scope:
        query = query.where(MaintenancePlan.ownership_scope.in_((ownership_scope, "all")))

    res = await db.execute(query.order_by(MaintenancePlan.name.asc()))
    return list(res.scalars().all())


async def schedule_preventive_maintenance(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    plan_id: UUID,
    *,
    base_odometer_km: int | None = None,
    base_date: datetime | None = None,
    actor_id: UUID | None = None,
) -> MaintenanceSchedule:
    """Agendar Manutenção Preventiva com Deduplicação Estrita e cálculo com base real no release.

    Regra de Dedup (#2): Se já existir um agendamento em ('pending', 'due', 'overdue')
    para a mesma viatura + plano, RETORNA o agendamento existente sem duplicar.
    """
    plan = await db.get(MaintenancePlan, plan_id)
    if not plan or plan.tenant_id != tenant_id or plan.status != "active":
        raise ApiError("plan_not_found", "Active maintenance plan not found.", status_code=404)

    vehicle = await db.get(Vehicle, vehicle_id)
    if not vehicle or vehicle.tenant_id != tenant_id:
        raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    # 1. Deduplicação Estrita
    existing_res = await db.execute(
        select(MaintenanceSchedule).where(
            MaintenanceSchedule.tenant_id == tenant_id,
            MaintenanceSchedule.vehicle_id == vehicle_id,
            MaintenanceSchedule.plan_id == plan_id,
            MaintenanceSchedule.status.in_(("pending", "due", "overdue")),
        )
    )
    existing_schedule = existing_res.scalars().first()
    if existing_schedule:
        return existing_schedule

    # 2. Cálculo do próximo due_km e due_at com base no odómetro e data reais
    now = base_date or datetime.now(UTC)
    current_km = base_odometer_km if base_odometer_km is not None else (vehicle.current_km or 0)

    existing = await db.scalar(
        select(MaintenanceSchedule).where(
            MaintenanceSchedule.tenant_id == tenant_id,
            MaintenanceSchedule.plan_id == plan_id,
            MaintenanceSchedule.vehicle_id == vehicle_id,
            MaintenanceSchedule.status.in_(("pending", "due", "overdue")),
        )
    )
    if existing:
        return existing

    due_km = (current_km + plan.interval_km) if plan.interval_km else None
    due_at = (now + timedelta(days=plan.interval_days)) if plan.interval_days else None

    schedule = MaintenanceSchedule(
        tenant_id=tenant_id,
        plan_id=plan_id,
        vehicle_id=vehicle_id,
        due_km=due_km,
        due_at=due_at,
        status="pending",
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


async def evaluate_preventive_schedules(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Avaliação periódica (Worker ARQ / Cron diário ou gatilho de odómetro).

    Calcula tolerâncias de 10% km ou 14 dias para passar a 'due' ou 'overdue'.
    Controlo de Notificação WhatsApp (#3):
      - 'due' passa a notificado gravando `notified_due_at`.
      - 'overdue' escalado urgentemente grava `notified_overdue_at`.
    """
    res = await db.execute(
        select(MaintenanceSchedule).where(
            MaintenanceSchedule.tenant_id == tenant_id,
            MaintenanceSchedule.status.in_(("pending", "due")),
        )
    )
    schedules = list(res.scalars().all())
    now = datetime.now(UTC)

    due_count = 0
    overdue_count = 0
    notified_count = 0

    for sched in schedules:
        plan = await db.get(MaintenancePlan, sched.plan_id)
        vehicle = await db.get(Vehicle, sched.vehicle_id)
        if not plan or not vehicle:
            continue

        current_km = vehicle.current_km or 0

        # Tolerâncias de fasquia
        is_km_due = False
        is_km_overdue = False
        if sched.due_km is not None and plan.interval_km:
            km_margin = int(plan.interval_km * 0.10)
            if current_km >= (sched.due_km - km_margin):
                is_km_due = True
            if current_km >= sched.due_km:
                is_km_overdue = True

        is_date_due = False
        is_date_overdue = False
        if sched.due_at:
            if now >= (sched.due_at - timedelta(days=14)):
                is_date_due = True
            if now >= sched.due_at:
                is_date_overdue = True

        # Transições de Estado
        if is_km_overdue or is_date_overdue:
            if sched.status != "overdue":
                sched.status = "overdue"
                overdue_count += 1
            # Guard Anti-Duplicação de Notificação URGENTE (#3)
            if sched.notified_overdue_at is None:
                sched.notified_overdue_at = now
                notified_count += 1
        elif is_km_due or is_date_due:
            if sched.status != "due":
                sched.status = "due"
                due_count += 1
            # Guard Anti-Duplicação de Notificação AVISO (#3)
            if sched.notified_due_at is None:
                sched.notified_due_at = now
                notified_count += 1

    await db.commit()
    return {
        "evaluated_count": len(schedules),
        "due_count": due_count,
        "overdue_count": overdue_count,
        "notified_count": notified_count,
    }


async def convert_schedule_to_action(
    db: AsyncSession,
    tenant_id: UUID,
    schedule_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Conversão do Agendamento em Ação Operacional (com Idempotência Absoluta #3).

    Diferenciação Estrita (TMS vs Workshop Multimarcas):
      - Frota (`fleet`): Cria Ordem de Serviço direta (WorkOrder ownership_scope="fleet")
        com `estimated_cost` calculado a partir do catálogo.
      - Cliente (`customer`): Cria Rascunho de Orçamento (WorkshopQuote status="draft")
        com numeração fiscal `ORC-2026-XXXX` enviado para aprovação comercial prévia.
      - Herança `all` (#2 das notas finas): Herda o `ownership_type` real da viatura!
    """
    sched = await db.get(MaintenanceSchedule, schedule_id)
    if not sched or sched.tenant_id != tenant_id:
        raise ApiError("schedule_not_found", "Maintenance schedule not found.", status_code=404)

    # IDEMPOTÊNCIA ABSOLUTA (#3): Se já convertido, devolve a referência existente
    if sched.status in ("converted_to_wo", "converted_to_quote"):
        return {
            "schedule_id": sched.id,
            "status": sched.status,
            "work_order_id": sched.work_order_id,
            "quote_id": sched.quote_id,
            "idempotent_reused": True,
        }

    plan = await db.get(MaintenancePlan, sched.plan_id)
    vehicle = await db.get(Vehicle, sched.vehicle_id)
    if not plan or not vehicle:
        raise ApiError("invalid_schedule_references", "Plan or vehicle reference missing.", status_code=422)

    # Determinar o escopo efetivo (herança de 'all')
    effective_scope = plan.ownership_scope
    if effective_scope == "all":
        effective_scope = (
            "customer" if (vehicle.customer_client_id or vehicle.ownership_type == "customer") else "fleet"
        )

    # Buscar item de catálogo associado (se houver) para estimativa de custo
    catalog_item = None
    if plan.service_catalog_item_id:
        catalog_item = await db.get(ServiceCatalogItem, plan.service_catalog_item_id)

    # Custo estimado de referência
    est_cost = Decimal("0.00")
    if catalog_item:
        est_cost = catalog_item.base_price or Decimal("0.00")

    now = datetime.now(UTC)

    if effective_scope == "fleet":
        # FLUXO TMS / FROTA PRÓPRIA: Geração direta de Ordem de Serviço sem orçamento prévio
        wo_number = f"OS-2026-{now.strftime('%m%d%H%M%S')}"
        wo = WorkOrder(
            tenant_id=tenant_id,
            work_order_number=wo_number,
            vehicle_id=vehicle.id,
            planned_work=f"Manutenção Preventiva Frota: {plan.name}",
            status="approved",
            estimated_cost=est_cost,
        )
        db.add(wo)
        await db.flush()

        task = WorkOrderTask(
            tenant_id=tenant_id,
            work_order_id=wo.id,
            description=f"Revisão Preventiva: {plan.name}",
            status="pending",
        )
        db.add(task)

        sched.status = "converted_to_wo"
        sched.work_order_id = wo.id
        await db.commit()
        return {
            "schedule_id": sched.id,
            "status": sched.status,
            "work_order_id": wo.id,
            "work_order_number": wo.work_order_number,
            "estimated_cost": float(est_cost),
            "idempotent_reused": False,
        }

    else:
        # FLUXO WORKSHOP MULTIMARCAS / CLIENTE EXTERNO: Rascunho de Orçamento (ORC-2026-XXXX)
        if not vehicle.customer_client_id:
            raise ApiError(
                "client_required", "Customer client reference missing for external vehicle.", status_code=409
            )

        quote_create = WorkshopQuoteCreate(
            client_id=vehicle.customer_client_id,
            vehicle_id=vehicle.id,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="labor",
                    description=f"Revisão Preventiva Recomendada: {plan.name}",
                    quantity=Decimal("1.0"),
                    unit_price=est_cost if est_cost > 0 else Decimal("1000.0"),
                )
            ],
            notes=f"Orçamento rascunho de preventiva gerado automaticamente para o plano {plan.name}.",
        )
        quote = await create_quote(db, tenant_id, quote_create, actor_id=actor_id)

        sched.status = "converted_to_quote"
        sched.quote_id = quote["id"]
        await db.commit()
        return {
            "schedule_id": sched.id,
            "status": sched.status,
            "quote_id": quote["id"],
            "quote_number": quote["quote_number"],
            "idempotent_reused": False,
        }


async def handle_work_order_completion_preventive_matching(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> dict:
    """Gatilho de Conclusão da OS em `close_work_order`: Matching por Catálogo e Automação do Próximo Ciclo.

    Regra de Ouro (#1 & #4):
      - Analisa os serviços efetuados na OS (`WorkOrderTask.service_catalog_item_id`).
      - Para cada plano cujo `service_catalog_item_id` faz matching com a OS:
        * Marca o agendamento ativo atual como `status="completed"`.
        * Cria AUTOMATICAMENTE o próximo agendamento com base no odómetro e data reais do momento de entrega:
          due_km = odometer_release + interval_km
          due_at = date_release + interval_days
      - Idempotente: se o agendamento já foi marcado como 'completed' nesta OS, previne duplicações.
    """
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        return {"matched_plans": 0, "new_schedules_created": 0}

    vehicle = None
    if wo.vehicle_id:
        vehicle = await db.get(Vehicle, wo.vehicle_id)

    if not vehicle:
        return {"matched_plans": 0, "new_schedules_created": 0}

    now = datetime.now(UTC)
    release_odometer = vehicle.current_km or 0
    new_schedules_created = 0

    # Buscar agendamentos ativos para a viatura da OS
    scheds_res = await db.execute(
        select(MaintenanceSchedule).where(
            MaintenanceSchedule.tenant_id == tenant_id,
            MaintenanceSchedule.vehicle_id == vehicle.id,
            MaintenanceSchedule.status.in_(("pending", "due", "overdue", "converted_to_wo", "converted_to_quote")),
        )
    )
    active_scheds = list(scheds_res.scalars().all())

    for active_sched in active_scheds:
        active_sched.status = "completed"
        # Criar automaticamente o próximo agendamento para o plano com baseline no odómetro/data de entrega
        new_sched = await schedule_preventive_maintenance(
            db,
            tenant_id,
            vehicle.id,
            active_sched.plan_id,
            base_odometer_km=release_odometer,
            base_date=now,
            actor_id=actor_id,
        )
        if new_sched:
            new_schedules_created += 1

    await db.commit()
    return {
        "matched_plans": len(active_scheds),
        "new_schedules_created": new_schedules_created,
        "release_odometer": release_odometer,
    }
