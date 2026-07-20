import uuid
from decimal import Decimal
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.modules.accounting.models import Account, JournalEntry, JournalItem
from app.modules.payables.models import SupplierInvoice
from app.modules.accounting.schemas import JournalEntryCreate

async def create_journal_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    payload: JournalEntryCreate,
    actor_id: Optional[uuid.UUID] = None,
    source_type: Optional[str] = None,
    source_id: Optional[uuid.UUID] = None,
) -> JournalEntry:
    """Função universal para injetar lançamentos a partir de hooks internos.

    Aceita payloads nomeados ``JournalEntryCreate`` (canonical) ou
    ``ManualEntryCreate`` (legacy alias). Both encodings normalizam para a
    lista de ``JournalItemCreate`` em ``payload.lines``.
    """
    raw_lines: list[Any] = list(payload.lines or payload.items or [])

    # 1. Validação de Partidas Dobradas
    if len(raw_lines) < 2:
        raise ValueError("O lançamento deve ter pelo menos duas linhas (Débito e Crédito)")

    total_debit = sum(_decimal_or_zero(getattr(item, "debit", 0)) for item in raw_lines)
    total_credit = sum(_decimal_or_zero(getattr(item, "credit", 0)) for item in raw_lines)

    if total_debit != total_credit:
        raise ValueError(f"Lançamento Desequilibrado: Débitos ({total_debit}) != Créditos ({total_credit})")

    if total_debit <= Decimal("0.00"):
        raise ValueError("Lançamentos de valor zero não são permitidos.")

    # 2. Criar Cabeçalho
    entry = JournalEntry(
        tenant_id=tenant_id,
        journal_type=payload.journal_type,
        date=payload.date,
        reference=payload.reference,
        description=payload.description,
        status="posted",
        source_document_type=source_type or "InternalHook",
        source_document_id=source_id,
    )
    session.add(entry)
    await session.flush()

    # 3. Criar Itens
    for item_data in raw_lines:
        j_item = JournalItem(
            tenant_id=tenant_id,
            journal_entry_id=entry.id,
            account_id=_resolve_account_uuid(item_data, tenant_id, session),
            debit=_decimal_or_zero(getattr(item_data, "debit", 0)),
            credit=_decimal_or_zero(getattr(item_data, "credit", 0)),
            third_party_id=getattr(item_data, "third_party_id", None),
            vehicle_id=getattr(item_data, "vehicle_id", None),
            trip_id=getattr(item_data, "trip_id", None),
            description=getattr(item_data, "description", None),
        )
        session.add(j_item)

    return entry


def _decimal_or_zero(value: Any) -> Decimal:
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _resolve_account_uuid(item_data: Any, tenant_id: uuid.UUID, session: AsyncSession) -> uuid.UUID:
    """Resolve account_id either directly from the payload or by PGC-NIRF code.

    Workshop currently passes ``account_number`` instead of ``account_id``.
    Payables already pre-resolves the UUID. Resolve lazily to keep both
    call sites compatible without a new migration here.
    """
    account_id = getattr(item_data, "account_id", None)
    if account_id is not None:
        return account_id

    code = getattr(item_data, "account_number", None) or getattr(item_data, "code", None)
    if not code:
        raise ValueError("JournalItem without account_id or account_number")

    from sqlalchemy import select  # local to avoid leaking at import time

    result = session.execute(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    )
    account = result.scalars().first()
    if not account:
        raise ValueError(f"PGC-NIRF account '{code}' not found for tenant {tenant_id}")
    result.close()
    return account.id


async def post_supplier_invoice(session: AsyncSession, invoice_id: uuid.UUID) -> JournalEntry:
    """
    Traduz a aprovação de uma SupplierInvoice num lançamento contabilístico de Partidas Dobradas.
    Regra ERP: 
      - DÉBITO: Conta de Gastos (62 - Fornecimentos e Serviços de Terceiros)
      - CRÉDITO: Conta de Passivo (42 - Fornecedores)
    """
    # 1. Carregar a Fatura Original
    invoice = await session.get(SupplierInvoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != "approved":
        # Apenas para simplificar a demo. O real teria validações de estado complexas.
        pass

    # 2. Localizar as contas base do PGC-NIRF do Tenant
    result_expense = await session.execute(
        select(Account).where(Account.tenant_id == invoice.tenant_id, Account.code == "62")
    )
    expense_account = result_expense.scalars().first()

    result_payable = await session.execute(
        select(Account).where(Account.tenant_id == invoice.tenant_id, Account.code == "42")
    )
    payable_account = result_payable.scalars().first()

    if not expense_account or not payable_account:
        raise HTTPException(status_code=500, detail="Chart of Accounts is missing required PGC-NIRF accounts (62 or 42).")

    # 3. Criar o Lançamento através da Porta de Segurança (create_journal_entry)
    from app.modules.accounting.schemas import JournalEntryCreate, JournalItemCreate

    entry_payload = JournalEntryCreate(
        journal_type="COM",
        date=invoice.issued_at,
        reference=invoice.invoice_number or f"Fatura de Fornecedor: {invoice.id}",
        description=invoice.description or "Reconhecimento de Custo com Fornecedor",
        items=[
            JournalItemCreate(
                account_id=expense_account.id,
                debit=invoice.amount,
                credit=Decimal("0.00"),
                third_party_id=invoice.third_party_id,
                vehicle_id=invoice.vehicle_id,
                trip_id=invoice.trip_id,
            ),
            JournalItemCreate(
                account_id=payable_account.id,
                debit=Decimal("0.00"),
                credit=invoice.amount,
                third_party_id=invoice.third_party_id
            )
        ]
    )

    try:
        journal_entry = await create_journal_entry(session, invoice.tenant_id, entry_payload)
        await session.commit()
        return journal_entry
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Erro Contabilístico: {str(e)}")
