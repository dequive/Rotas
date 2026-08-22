"""Workshop Labor & OS Profitability Service.

Gestão de Taxas Horárias, Apontamento de Mão de Obra e Rentabilidade da OS.

Resolução das Regras de Ouro:
  1. Junção por FK Direta `BillingItem.work_order_id` (#1):
     Calcula a receita da OS via JOIN direto em BillingItem.work_order_id == wo.id com status ('issued', 'paid').
     Suporta faturas consolidadas com orçamento original e suplementares sem
     depender de correspondências frágeis de texto.
  2. Suporte a Estorno (`void_task_labor_session`):
     Log de mão de obra possui `voided_at` e `void_reason`. Sessões estornadas são excluídas da soma de custos.
  3. Taxa Horária Vigente à Data `completed_at`:
     Busca a taxa com `effective_from <= completed_at` ORDER BY effective_from DESC LIMIT 1.
  4. Filosofia Comercial (Preço Fixo vs Custo Interno):
     Tempo excedente ajusta a margem de rentabilidade interna sem afetar a fatura comercial do cliente.
  5. Imutabilidade Pós-Faturação:
     Registar ou estornar mão de obra em OS fechada ou facturada devolve HTTP 409 `work_order_already_billed`.
"""

import sys
from pathlib import Path

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.clients.models import Client
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenancePartUsed,
    TaskLaborLog,
    WorkOrder,
    WorkOrderTask,
    WorkshopStaffRate,
)


async def set_staff_hourly_rate(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    hourly_rate: Decimal | float,
    effective_from: date,
    *,
    actor_id: UUID | None = None,
) -> WorkshopStaffRate:
    """Registar ou atualizar taxa horária histórica de um mecânico."""
    rate_val = Decimal(str(hourly_rate)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if rate_val <= 0:
        raise ApiError("invalid_hourly_rate", "Hourly rate must be greater than zero.", status_code=400)

    # Verificar se já existe registo para a mesma data
    res = await db.execute(
        select(WorkshopStaffRate).where(
            WorkshopStaffRate.tenant_id == tenant_id,
            WorkshopStaffRate.user_id == user_id,
            WorkshopStaffRate.effective_from == effective_from,
        )
    )
    existing = res.scalars().first()
    if existing:
        existing.hourly_rate = rate_val
        await db.commit()
        await db.refresh(existing)
        return existing

    rate_record = WorkshopStaffRate(
        tenant_id=tenant_id,
        user_id=user_id,
        hourly_rate=rate_val,
        effective_from=effective_from,
    )
    db.add(rate_record)
    await db.commit()
    await db.refresh(rate_record)
    return rate_record


async def get_staff_hourly_rate(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    at_date: date | datetime,
) -> Decimal:
    """Obter taxa horária vigente do mecânico à data indicada (`effective_from <= at_date` DESC LIMIT 1)."""
    target_date = at_date.date() if isinstance(at_date, datetime) else at_date

    res = await db.execute(
        select(WorkshopStaffRate.hourly_rate)
        .where(
            WorkshopStaffRate.tenant_id == tenant_id,
            WorkshopStaffRate.user_id == user_id,
            WorkshopStaffRate.effective_from <= target_date,
        )
        .order_by(WorkshopStaffRate.effective_from.desc())
        .limit(1)
    )
    rate = res.scalar_one_or_none()
    if rate is None:
        # Taxa padrão base se não houver registo prévio cadastrado
        return Decimal("500.00")
    return rate


async def _assert_work_order_mutable(db: AsyncSession, tenant_id: UUID, work_order_id: UUID) -> WorkOrder:
    """Valida se a OS pode aceitar alterações de mão de obra (Imutabilidade Pós-Faturação 409)."""
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    if wo.status in ("closed", "invoiced", "cancelled"):
        raise ApiError(
            "work_order_already_billed", "Work order is closed/billed and cannot accept labor edits.", status_code=409
        )

    # Verificar se existe fatura emitida/paga para esta OS via BillingItem.work_order_id
    billed_res = await db.execute(
        select(BillingDocument.id)
        .join(BillingItem, BillingItem.billing_document_id == BillingDocument.id)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.work_order_id == work_order_id,
            BillingDocument.status.in_(("issued", "paid")),
        )
        .limit(1)
    )
    if billed_res.scalar_one_or_none() is not None:
        raise ApiError("work_order_already_billed", "Work order has an issued/paid billing document.", status_code=409)

    return wo


async def add_task_labor_session(
    db: AsyncSession,
    tenant_id: UUID,
    task_id: UUID,
    user_id: UUID,
    minutes_worked: int,
    *,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    actor_id: UUID | None = None,
) -> TaskLaborLog:
    """Adicionar sessão de mão de obra efetuada por um mecânico numa tarefa."""
    if minutes_worked <= 0:
        raise ApiError("invalid_minutes", "Minutes worked must be greater than zero.", status_code=400)

    task = await db.get(WorkOrderTask, task_id)
    if not task or task.tenant_id != tenant_id:
        raise ApiError("task_not_found", "Work order task not found.", status_code=404)

    # Validar Imutabilidade da OS (HTTP 409)
    await _assert_work_order_mutable(db, tenant_id, task.work_order_id)

    comp_time = completed_at or datetime.now(UTC)
    hourly_rate = await get_staff_hourly_rate(db, tenant_id, user_id, comp_time)

    # Custo = (minutos / 60) * taxa horária
    cost = (Decimal(minutes_worked) / Decimal("60")) * hourly_rate
    cost_val = cost.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    log = TaskLaborLog(
        tenant_id=tenant_id,
        work_order_task_id=task.id,
        user_id=user_id,
        started_at=started_at,
        completed_at=comp_time,
        minutes_worked=minutes_worked,
        hourly_rate_applied=hourly_rate,
        total_labor_cost=cost_val,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def void_task_labor_session(
    db: AsyncSession,
    tenant_id: UUID,
    labor_log_id: UUID,
    void_reason: str,
    *,
    actor_id: UUID | None = None,
) -> TaskLaborLog:
    """Estornar/Anular uma sessão de mão de obra errónea (Void com justificativa)."""
    if not void_reason or not void_reason.strip():
        raise ApiError("invalid_void_reason", "Void reason is required.", status_code=400)

    log = await db.get(TaskLaborLog, labor_log_id)
    if not log or log.tenant_id != tenant_id:
        raise ApiError("labor_log_not_found", "Task labor log not found.", status_code=404)

    if log.voided_at is not None:
        return log  # Idempotente: já estornado

    task = await db.get(WorkOrderTask, log.work_order_task_id)
    if not task:
        raise ApiError("task_not_found", "Associated task not found.", status_code=404)

    # Validar Imutabilidade da OS (HTTP 409)
    await _assert_work_order_mutable(db, tenant_id, task.work_order_id)

    log.voided_at = datetime.now(UTC)
    log.void_reason = void_reason.strip()
    await db.commit()
    await db.refresh(log)
    return log


async def _compute_work_order_profitability_data(
    db: AsyncSession,
    tenant_id: UUID,
    wo: WorkOrder,
) -> dict:
    """Função core compartilhada para apuração de rentabilidade de uma OS.

    Chave de Integridade (#1): Receita faturada calculada via JOIN direto
    em `BillingItem.work_order_id == wo.id` com `BillingDocument.status IN ('issued', 'paid')`.
    Segrega estritamente:
      - confirmed_revenue: soma de BillingItem de faturas emitidas/pagas ('issued', 'paid')
      - projected_revenue: estimativa da OS / orçamento se ainda não facturada
      - total_labor_cost: custo total de mão-de-obra das sessões ativas
      - total_parts_cost: custo líquido de peças (emissões - devoluções)
    """
    # 1. Receita Faturada Confirmada (JOIN direto por FK BillingItem.work_order_id)
    revenue_res = await db.execute(
        select(func.coalesce(func.sum(BillingItem.amount), Decimal("0.00")))
        .join(BillingDocument, BillingDocument.id == BillingItem.billing_document_id)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.work_order_id == wo.id,
            BillingDocument.status.in_(("issued", "paid")),
        )
    )
    confirmed_revenue = Decimal(str(revenue_res.scalar_one()))

    # 2. Receita Projetada (Pipeline de orçamentos/OS em curso ainda não facturadas)
    projected_revenue = Decimal("0.00")
    if confirmed_revenue == Decimal("0.00") and wo.estimated_cost:
        projected_revenue = Decimal(str(wo.estimated_cost))

    # 3. Custo Direto de Mão de Obra (TaskLaborLog não estornados)
    labor_res = await db.execute(
        select(
            func.coalesce(func.sum(TaskLaborLog.minutes_worked), 0),
            func.coalesce(func.sum(TaskLaborLog.total_labor_cost), Decimal("0.00")),
        )
        .join(WorkOrderTask, WorkOrderTask.id == TaskLaborLog.work_order_task_id)
        .where(
            WorkOrderTask.tenant_id == tenant_id,
            WorkOrderTask.work_order_id == wo.id,
            TaskLaborLog.voided_at.is_(None),
        )
    )
    labor_row = labor_res.first()
    total_labor_minutes = int(labor_row[0]) if labor_row else 0
    total_labor_cost = Decimal(str(labor_row[1])) if labor_row else Decimal("0.00")

    # 4. Custo líquido de peças: emissões menos devoluções
    parts_res = await db.execute(
        select(
            func.coalesce(
                func.sum(
                    func.coalesce(MaintenancePartUsed.net_total_cost, MaintenancePartUsed.total_cost)
                ),
                Decimal("0.00"),
            )
        ).where(
            MaintenancePartUsed.tenant_id == tenant_id,
            MaintenancePartUsed.work_order_id == wo.id,
        )
    )
    total_parts_cost = Decimal(str(parts_res.scalar_one()))

    total_cost = total_labor_cost + total_parts_cost
    effective_revenue_for_wo = confirmed_revenue if confirmed_revenue > Decimal("0.00") else projected_revenue
    gross_profit = effective_revenue_for_wo - total_cost

    gross_profit_margin_pct = Decimal("0.00")
    if effective_revenue_for_wo > Decimal("0.00"):
        margin_pct = (gross_profit / effective_revenue_for_wo) * Decimal("100")
        gross_profit_margin_pct = margin_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "work_order_id": wo.id,
        "work_order_number": wo.work_order_number,
        "status": wo.status,
        "confirmed_revenue": confirmed_revenue,
        "projected_revenue": projected_revenue,
        "effective_revenue": effective_revenue_for_wo,
        "total_labor_minutes": total_labor_minutes,
        "total_labor_cost": total_labor_cost,
        "total_parts_cost": total_parts_cost,
        "total_cost": total_cost,
        "gross_profit_mzn": gross_profit,
        "gross_profit_margin_percent": gross_profit_margin_pct,
        "is_profitable": gross_profit >= Decimal("0.00"),
    }


async def get_work_order_profitability(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
) -> dict:
    """Relatório de Margem e Rentabilidade Direta de uma OS individual."""
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    data = await _compute_work_order_profitability_data(db, tenant_id, wo)
    return {
        "work_order_id": data["work_order_id"],
        "work_order_number": data["work_order_number"],
        "total_revenue": float(data["effective_revenue"]),
        "confirmed_revenue": float(data["confirmed_revenue"]),
        "projected_revenue": float(data["projected_revenue"]),
        "total_labor_minutes": data["total_labor_minutes"],
        "total_labor_cost": float(data["total_labor_cost"]),
        "total_parts_cost": float(data["total_parts_cost"]),
        "total_cost": float(data["total_cost"]),
        "gross_profit_mzn": float(data["gross_profit_mzn"]),
        "gross_profit_margin_percent": float(data["gross_profit_margin_percent"]),
        "is_profitable": data["is_profitable"],
    }


async def get_workshop_profitability_summary(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    start_date: date | datetime | None = None,
    end_date: date | datetime | None = None,
    client_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Relatório Consolidado de Rentabilidade & BI da Oficina Auto por Tenant.

    Aplica as 5 Regras de Ouro:
    1. Reutilização do core `_compute_work_order_profitability_data` por OS
    2. Segregação rigorosa: confirmed_revenue (KPI primário) vs projected_revenue (Pipeline)
    3. Proteção RBAC com WORKSHOP_FINANCE_READ
    4. Guard 404 estrito ao filtrar por cliente ou viatura de outro tenant
    5. Precisão Decimal em todos os acumuladores antes de serializar
    """
    # Cross-tenant 404 guards para filtros foreign explicitados
    if client_id:
        client = await db.get(Client, client_id)
        if not client or client.tenant_id != tenant_id:
            raise ApiError("client_not_found", "Client not found.", status_code=404)

    if vehicle_id:
        vehicle = await db.get(Vehicle, vehicle_id)
        if not vehicle or vehicle.tenant_id != tenant_id:
            raise ApiError("vehicle_not_found", "Vehicle not found.", status_code=404)

    # Base query de WorkOrders do tenant
    query = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)

    if vehicle_id:
        query = query.where(WorkOrder.vehicle_id == vehicle_id)

    if status_filter:
        query = query.where(WorkOrder.status == status_filter)

    if start_date:
        s_dt = (
            start_date
            if isinstance(start_date, datetime)
            else datetime.combine(start_date, datetime.min.time(), tzinfo=UTC)
        )
        query = query.where(WorkOrder.created_at >= s_dt)

    if end_date:
        e_dt = (
            end_date
            if isinstance(end_date, datetime)
            else datetime.combine(end_date, datetime.max.time(), tzinfo=UTC)
        )
        query = query.where(WorkOrder.created_at <= e_dt)

    query = query.order_by(WorkOrder.created_at.desc())

    res = await db.execute(query)
    all_wos = list(res.scalars().all())

    # Pre-fetch de viaturas e clientes associados para o relatório
    client_map = {}
    vehicle_map = {}
    vehicle_obj_map = {}

    vehicle_ids = {wo.vehicle_id for wo in all_wos if wo.vehicle_id}

    if vehicle_ids:
        v_res = await db.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
        for v in v_res.scalars().all():
            vehicle_obj_map[v.id] = v
            vehicle_map[v.id] = f"{v.brand or ''} {v.model or ''} ({v.plate})".strip()

    client_ids = {v.customer_client_id for v in vehicle_obj_map.values() if v.customer_client_id}

    if client_ids:
        c_res = await db.execute(select(Client).where(Client.id.in_(client_ids)))
        for c in c_res.scalars().all():
            client_map[c.id] = c.trading_name or c.legal_name or f"Cliente #{str(c.id)[:6]}"

    # Se client_id tiver sido passado, filtrar all_wos pelas viaturas pertencentes a esse cliente
    if client_id:
        all_wos = [
            wo
            for wo in all_wos
            if wo.vehicle_id in vehicle_obj_map and vehicle_obj_map[wo.vehicle_id].customer_client_id == client_id
        ]

    # Acumuladores em Decimal para precisão perfeita
    tot_confirmed_revenue = Decimal("0.00")
    tot_projected_revenue = Decimal("0.00")
    tot_labor_cost = Decimal("0.00")
    tot_parts_cost = Decimal("0.00")
    tot_cost = Decimal("0.00")
    negative_margin_count = 0

    items_output = []

    for wo in all_wos:
        data = await _compute_work_order_profitability_data(db, tenant_id, wo)

        c_rev = data["confirmed_revenue"]
        p_rev = data["projected_revenue"]
        l_cost = data["total_labor_cost"]
        pt_cost = data["total_parts_cost"]
        t_cost = data["total_cost"]

        tot_confirmed_revenue += c_rev
        tot_projected_revenue += p_rev
        tot_labor_cost += l_cost
        tot_parts_cost += pt_cost
        tot_cost += t_cost

        eff_rev = data["effective_revenue"]
        wo_profit = eff_rev - t_cost
        if wo_profit < Decimal("0.00"):
            negative_margin_count += 1

        v_obj = vehicle_obj_map.get(wo.vehicle_id) if wo.vehicle_id else None
        client_name = (
            client_map.get(v_obj.customer_client_id, "Cliente Geral")
            if v_obj and v_obj.customer_client_id
            else "Frota Própria"
        )
        vehicle_name = vehicle_map.get(wo.vehicle_id, "Viatura Desconhecida") if wo.vehicle_id else "S/V"

        items_output.append(
            {
                "id": str(wo.id),
                "wo_number": wo.work_order_number,
                "client": client_name,
                "vehicle": vehicle_name,
                "status": wo.status,
                "confirmed_revenue": float(c_rev),
                "projected_revenue": float(p_rev),
                "effective_revenue": float(eff_rev),
                "labor_cost": float(l_cost),
                "parts_cost": float(pt_cost),
                "total_cost": float(t_cost),
                "margin_mzn": float(wo_profit),
                "margin_pct": float(data["gross_profit_margin_percent"]),
                "is_profitable": data["is_profitable"],
                "created_at": wo.created_at.isoformat() if wo.created_at else None,
            }
        )

    # Margem % média baseada na Receita Confirmada
    avg_confirmed_margin_pct = Decimal("0.00")
    if tot_confirmed_revenue > Decimal("0.00"):
        avg_confirmed_margin_pct = (
            (tot_confirmed_revenue - tot_cost) / tot_confirmed_revenue * Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Paginação na lista de items
    paginated_items = items_output[offset : offset + limit]

    return {
        "summary": {
            "confirmed_revenue": float(tot_confirmed_revenue),
            "projected_revenue": float(tot_projected_revenue),
            "total_labor_cost": float(tot_labor_cost),
            "total_parts_cost": float(tot_parts_cost),
            "total_cost": float(tot_cost),
            "confirmed_gross_profit": float(tot_confirmed_revenue - tot_cost),
            "confirmed_gross_margin_pct": float(avg_confirmed_margin_pct),
            "negative_margin_count": negative_margin_count,
            "total_work_orders": len(all_wos),
        },
        "work_orders": paginated_items,
        "total_count": len(all_wos),
        "limit": limit,
        "offset": offset,
    }
