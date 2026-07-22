"""Workshop Labor & OS Profitability Service — Gestão de Taxas Horárias, Apontamento de Mão de Obra e Rentabilidade da OS.

Resolução das Regras de Ouro:
  1. Junção por FK Direta `BillingItem.work_order_id` (#1):
     Calcula a receita da OS via JOIN direto em BillingItem.work_order_id == wo.id com status ('issued', 'paid').
     Suporta automaticamente faturas consolidadas contendo orçamento original + suplementares sem fragilidades de string.
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
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.billing.models import BillingDocument, BillingItem
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
        raise ApiError("work_order_already_billed", "Work order is closed/billed and cannot accept labor edits.", status_code=409)

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


async def get_work_order_profitability(
    db: AsyncSession,
    tenant_id: UUID,
    work_order_id: UUID,
) -> dict:
    """Relatório de Margem e Rentabilidade Direta da OS.

    Chave de Integridade (#1): Receita faturada calculada via JOIN direto
    em `BillingItem.work_order_id == wo.id` com `BillingDocument.status IN ('issued', 'paid')`.
    Suporta automaticamente faturas consolidadas com orçamentos originais e suplementares!
    """
    wo = await db.get(WorkOrder, work_order_id)
    if not wo or wo.tenant_id != tenant_id:
        raise ApiError("work_order_not_found", "Work order not found.", status_code=404)

    # 1. Receita Faturada Comercial (JOIN direto por FK BillingItem.work_order_id)
    revenue_res = await db.execute(
        select(func.coalesce(func.sum(BillingItem.amount), Decimal("0.00")))
        .join(BillingDocument, BillingDocument.id == BillingItem.billing_document_id)
        .where(
            BillingItem.tenant_id == tenant_id,
            BillingItem.work_order_id == wo.id,
            BillingDocument.status.in_(("issued", "paid")),
        )
    )
    total_revenue = Decimal(str(revenue_res.scalar_one()))

    # Se ainda não houver fatura confirmada/paga, considera a estimativa de custo/quote para apuração preliminar
    if total_revenue == Decimal("0.00") and wo.estimated_cost:
        total_revenue = Decimal(str(wo.estimated_cost))

    # 2. Custo Direto de Mão de Obra (TaskLaborLog não estornados)
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

    # 3. Custo Direto de Peças (MaintenancePartUsed WACC)
    parts_res = await db.execute(
        select(func.coalesce(func.sum(MaintenancePartUsed.total_cost), Decimal("0.00"))).where(
            MaintenancePartUsed.tenant_id == tenant_id,
            MaintenancePartUsed.work_order_id == wo.id,
        )
    )
    total_parts_cost = Decimal(str(parts_res.scalar_one()))

    # 4. Apuração da Margem Bruta
    total_cost = total_labor_cost + total_parts_cost
    gross_profit = total_revenue - total_cost

    gross_profit_margin_pct = Decimal("0.00")
    if total_revenue > Decimal("0.00"):
        margin_pct = (gross_profit / total_revenue) * Decimal("100")
        gross_profit_margin_pct = margin_pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "work_order_id": wo.id,
        "work_order_number": wo.work_order_number,
        "total_revenue": float(total_revenue),
        "total_labor_minutes": total_labor_minutes,
        "total_labor_cost": float(total_labor_cost),
        "total_parts_cost": float(total_parts_cost),
        "total_cost": float(total_cost),
        "gross_profit_mzn": float(gross_profit),
        "gross_profit_margin_percent": float(gross_profit_margin_pct),
        "is_profitable": gross_profit >= Decimal("0.00"),
    }
