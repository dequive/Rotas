import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.modules.accounting.models import Account, JournalEntry, JournalItem
from app.modules.payables.models import SupplierInvoice
from app.modules.accounting.schemas import ManualEntryCreate

async def create_journal_entry(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    payload: ManualEntryCreate,
    actor_id: uuid.UUID | None = None
) -> JournalEntry:
    """Função universal para injetar lançamentos a partir de hooks internos."""
    # 1. Validação de Partidas Dobradas
    total_debit = sum(item.debit for item in payload.items)
    total_credit = sum(item.credit for item in payload.items)
    if total_debit != total_credit:
        raise HTTPException(
            status_code=400,
            detail=f"Lançamento Desequilibrado: Débitos ({total_debit}) != Créditos ({total_credit})"
        )
        
    # 2. Criar Cabeçalho
    entry = JournalEntry(
        tenant_id=tenant_id,
        journal_type=payload.journal_type,
        date=payload.date,
        reference=payload.reference,
        description=payload.description,
        status="posted",
        source_document_type="InternalHook"
    )
    session.add(entry)
    await session.flush()
    
    # 3. Criar Itens
    for item_data in payload.items:
        j_item = JournalItem(
            tenant_id=tenant_id,
            journal_entry_id=entry.id,
            account_id=item_data.account_id,
            debit=item_data.debit,
            credit=item_data.credit,
            third_party_id=item_data.third_party_id,
            vehicle_id=item_data.vehicle_id,
            trip_id=item_data.trip_id
        )
        session.add(j_item)
        
    return entry

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
    # 62 - Gastos (assumindo a genérica de fornecimentos)
    result_expense = await session.execute(
        select(Account).where(Account.tenant_id == invoice.tenant_id, Account.code == "62")
    )
    expense_account = result_expense.scalars().first()
    
    # 42 - Fornecedores
    result_payable = await session.execute(
        select(Account).where(Account.tenant_id == invoice.tenant_id, Account.code == "42")
    )
    payable_account = result_payable.scalars().first()

    if not expense_account or not payable_account:
        raise HTTPException(status_code=500, detail="Chart of Accounts is missing required PGC-NIRF accounts (62 or 42).")

    # 3. Criar o Cabeçalho do Lançamento no Diário
    journal_entry = JournalEntry(
        tenant_id=invoice.tenant_id,
        date=invoice.issued_at, # O custo reconhece-se na data de emissão da fatura (Acrual basis)
        reference=invoice.invoice_number or f"Fatura de Fornecedor: {invoice.id}",
        description=invoice.description or "Reconhecimento de Custo com Fornecedor",
        source_document_type="SupplierInvoice",
        source_document_id=invoice.id,
        status="posted"
    )
    session.add(journal_entry)
    await session.flush() # Gerar o journal_entry.id

    # 4. Criar as Partidas (Debits e Credits)
    # Débito em Despesa (Aumenta o Gasto)
    debit_item = JournalItem(
        tenant_id=invoice.tenant_id,
        journal_entry_id=journal_entry.id,
        account_id=expense_account.id,
        debit=invoice.amount,
        credit=Decimal(0),
        # Tags de Custeio ABC (Activity Based Costing) herdadas da Fatura!
        third_party_id=invoice.third_party_id,
        vehicle_id=invoice.vehicle_id,
        trip_id=invoice.trip_id,
        work_order_id=invoice.work_order_id
    )

    # Crédito em Fornecedores (Aumenta a Dívida)
    credit_item = JournalItem(
        tenant_id=invoice.tenant_id,
        journal_entry_id=journal_entry.id,
        account_id=payable_account.id,
        debit=Decimal(0),
        credit=invoice.amount,
        third_party_id=invoice.third_party_id # Na conta do fornecedor, sabemos sempre a quem devemos.
        # Não enviamos vehicle_id para o Passivo, porque a dívida é com o Fornecedor, não com a viatura.
    )

    session.add_all([debit_item, credit_item])

    # 5. Validação de Partida Dobrada (Safety Net Arquitetural)
    if debit_item.debit + credit_item.debit != debit_item.credit + credit_item.credit:
        raise HTTPException(status_code=500, detail="Accounting imbalance detected. Transaction aborted.")

    await session.commit()
    return journal_entry
