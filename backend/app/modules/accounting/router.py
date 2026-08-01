from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import Principal, get_current_principal
from app.core.deps import get_session
from app.core.rbac import ACCOUNTING_POST, ACCOUNTING_READ, require_permission
from app.modules.accounting.models import Account, JournalEntry, JournalItem
from app.modules.accounting.schemas import (
    AccountResponse,
    JournalEntryCreate,
    JournalEntryResponse,
    ProfitAndLossResponse,
    TrialBalanceLine,
)

router = APIRouter(prefix="/accounting", tags=["accounting"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts(
    principal: Annotated[Principal, Depends(require_permission(ACCOUNTING_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    stmt = (
        select(Account).where(Account.tenant_id == principal.tenant_id).order_by(Account.code.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED
)
async def create_manual_entry(
    payload: JournalEntryCreate,
    principal: Annotated[Principal, Depends(require_permission(ACCOUNTING_POST))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    from app.modules.accounting.services import create_journal_entry as _create_journal_entry

    # Validar Partidas Dobradas (Total Debitos == Total Creditos)
    lines = payload.lines or payload.items or []
    total_debit = sum(item.debit for item in lines)
    total_credit = sum(item.credit for item in lines)

    if total_debit != total_credit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Lançamento Desequilibrado: Débitos ({total_debit}) != Créditos ({total_credit})",
        )

    # Validar se as contas existem e pertencem ao tenant
    for item_data in lines:
        acc = await session.get(Account, item_data.account_id)
        if not acc or acc.tenant_id != principal.tenant_id:
            raise HTTPException(
                status_code=400, detail=f"Conta {item_data.account_id} não encontrada."
            )

    entry = await _create_journal_entry(
        session,
        principal.tenant_id,
        payload,
        actor_id=principal.user_id,
        source_type="ManualEntry",
    )
    await session.commit()

    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.items).selectinload(JournalItem.account))
        .where(JournalEntry.id == entry.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.get("/journal-entries", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    principal: Annotated[Principal, Depends(require_permission(ACCOUNTING_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    journal_type: str | None = None,
):
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.items).selectinload(JournalItem.account))
        .where(JournalEntry.tenant_id == principal.tenant_id)
    )

    if journal_type:
        stmt = stmt.where(JournalEntry.journal_type == journal_type)

    stmt = stmt.order_by(JournalEntry.date.desc(), JournalEntry.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/profit-and-loss", response_model=ProfitAndLossResponse)
async def get_profit_and_loss(
    principal: Annotated[Principal, Depends(require_permission(ACCOUNTING_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    month: int | None = None,
    year: int | None = None,
    vehicle_id: UUID | None = None,
):
    """
    Demonstração de Resultados (DRE): Classe 7 vs Classe 6.
    Suporta filtros por Mês, Ano e por Viatura!
    """
    stmt = (
        select(
            Account.id,
            Account.code,
            Account.name,
            func.sum(JournalItem.debit).label("total_debit"),
            func.sum(JournalItem.credit).label("total_credit"),
        )
        .join(JournalItem, JournalItem.account_id == Account.id)
        .join(JournalEntry, JournalItem.journal_entry_id == JournalEntry.id)
        .where(Account.tenant_id == principal.tenant_id)
        .where(JournalEntry.status == "posted")
    )

    # Filtros Dinâmicos
    if month:
        # Note: postgres extract month
        stmt = stmt.where(func.extract("month", JournalEntry.date) == month)
    if year:
        stmt = stmt.where(func.extract("year", JournalEntry.date) == year)
    if vehicle_id:
        stmt = stmt.where(JournalItem.vehicle_id == vehicle_id)

    stmt = stmt.group_by(Account.id).order_by(Account.code.asc())

    result = await session.execute(stmt)
    rows = result.all()

    total_revenue = Decimal("0.00")
    total_expense = Decimal("0.00")
    lines = []

    for row in rows:
        bal = Decimal("0.00")
        if row.code.startswith("7"):
            # Receita: Creditos aumentam, Debitos diminuem
            bal = (row.total_credit or 0) - (row.total_debit or 0)
            total_revenue += bal
            lines.append(
                TrialBalanceLine(
                    account_id=row.id,
                    code=row.code,
                    name=row.name,
                    debit_total=row.total_debit or 0,
                    credit_total=row.total_credit or 0,
                    balance=bal,
                )
            )
        elif row.code.startswith("6"):
            # Despesa: Debitos aumentam, Creditos diminuem
            bal = (row.total_debit or 0) - (row.total_credit or 0)
            total_expense += bal
            lines.append(
                TrialBalanceLine(
                    account_id=row.id,
                    code=row.code,
                    name=row.name,
                    debit_total=row.total_debit or 0,
                    credit_total=row.total_credit or 0,
                    balance=bal,
                )
            )

    ebitda = total_revenue - total_expense

    return ProfitAndLossResponse(
        total_revenue=total_revenue, total_expense=total_expense, ebitda=ebitda, lines=lines
    )


@router.get("/trial-balance", response_model=list[TrialBalanceLine])
async def get_trial_balance(
    principal: Annotated[Principal, Depends(require_permission(ACCOUNTING_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    """
    Balancete de Verificação (Trial Balance).
    Mostra os saldos de todas as contas PGC-NIRF do Tenant.
    """
    stmt = (
        select(
            Account.id,
            Account.code,
            Account.name,
            func.sum(JournalItem.debit).label("total_debit"),
            func.sum(JournalItem.credit).label("total_credit"),
        )
        .outerjoin(JournalItem, JournalItem.account_id == Account.id)
        .where(Account.tenant_id == principal.tenant_id)
        .group_by(Account.id)
        .order_by(Account.code.asc())
    )

    result = await session.execute(stmt)
    rows = result.all()

    lines = []
    for row in rows:
        td = row.total_debit or Decimal("0.00")
        tc = row.total_credit or Decimal("0.00")
        # Para contas do Ativo e Gastos (1,2,3,6), Saldo Devedor é Positivo
        # Para Passivo, Capital e Rendimentos (4,5,7), Saldo Credor é Positivo
        # Balanço base:
        if row.code.startswith(("1", "2", "3", "6")):
            balance = td - tc
        else:
            balance = tc - td

        lines.append(
            TrialBalanceLine(
                account_id=row.id,
                code=row.code,
                name=row.name,
                debit_total=td,
                credit_total=tc,
                balance=balance,
            )
        )

    return lines
