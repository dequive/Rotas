from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.billing.models import BillingDocument
from app.modules.clients.models import Client
from app.modules.clients.schemas import ClientCreate, ClientPatch


def serialize_client(client: Client, outstanding_balance: Decimal | None = None) -> dict:
    return {
        "id": client.id,
        "tenant_id": client.tenant_id,
        "trading_name": client.trading_name,
        "legal_name": client.legal_name,
        "nuit": client.nuit,
        "address": client.address,
        "city": client.city,
        "phone": client.phone,
        "email": client.email,
        "payment_terms_days": client.payment_terms_days,
        "credit_limit": client.credit_limit,
        "is_active": client.is_active,
        "outstanding_balance": outstanding_balance,
        # Phase 5 Plan 02: outstanding_balance is now live — client_id FK on billing_documents
        # added via migration e5f6a7b8c9d0. outstanding_balance_estimate removed in Plan 02.
        "outstanding_balance_estimate": False,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
    }


async def _get_outstanding_balance(db: AsyncSession, client_id: UUID, tenant_id: UUID) -> Decimal:
    """Outstanding balance: gross issued/overdue invoice totals minus confirmed allocations.

    Updated in Phase 6 to subtract PaymentAllocation.amount_applied for confirmed payments.
    Includes both 'issued' and 'overdue' documents — both represent outstanding receivables.
    """
    from app.modules.billing.models import ClientPayment, PaymentAllocation  # avoid circular import

    gross_result = await db.execute(
        select(func.coalesce(func.sum(BillingDocument.total_amount), 0)).where(
            BillingDocument.client_id == client_id,
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status.in_(("issued", "overdue")),
        )
    )
    gross = Decimal(str(gross_result.scalar_one()))

    paid_result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0))
        .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
        .join(BillingDocument, BillingDocument.id == PaymentAllocation.billing_document_id)
        .where(
            ClientPayment.client_id == client_id,
            ClientPayment.tenant_id == tenant_id,
            ClientPayment.status == "confirmed",
            BillingDocument.status.in_(("issued", "overdue")),
        )
    )
    paid = Decimal(str(paid_result.scalar_one()))

    return (gross - paid).quantize(Decimal("0.01"))


async def list_clients(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    result = await db.execute(
        select(Client)
        .where(Client.tenant_id == tenant_id)
        .order_by(Client.trading_name)
        .limit(limit)
        .offset(offset)
    )
    clients = list(result.scalars())
    # Outstanding balance not included in list response (perf) — use detail endpoint
    return [serialize_client(c) for c in clients]


async def get_client_with_balance(db: AsyncSession, client_id: UUID, tenant_id: UUID) -> dict:
    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError(
            "client_not_found",
            "Cliente não encontrado.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    balance = await _get_outstanding_balance(db, client_id, tenant_id)
    return serialize_client(client, outstanding_balance=balance)


async def create_client(db: AsyncSession, tenant_id: UUID, payload: ClientCreate) -> dict:
    client = Client(tenant_id=tenant_id, **payload.model_dump())
    db.add(client)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ApiError(
            "nuit_already_exists",
            "NUIT já existe neste tenant.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    await db.commit()
    await db.refresh(client)
    return serialize_client(client)


async def patch_client(
    db: AsyncSession, client_id: UUID, tenant_id: UUID, payload: ClientPatch
) -> dict:
    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError(
            "client_not_found",
            "Cliente não encontrado.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    await db.commit()
    await db.refresh(client)
    return serialize_client(client)


# ── Phase 6: Client Statement (PAY-03) ───────────────────────────────────────


async def get_client_statement(
    db: AsyncSession,
    client_id: UUID,
    tenant_id: UUID,
    *,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> dict:
    """Synchronous client statement — balance computed from DB, not cache. (PAY-03)

    Returns client + billing documents with per-document amount_paid and outstanding_balance
    + all payments + summary totals. Data is always consistent within the same DB session.
    """
    from app.modules.billing.models import ClientPayment, PaymentAllocation  # avoid circular import

    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError("client_not_found", "Client not found", status_code=404)

    # Fetch billing documents for this client
    doc_query = select(BillingDocument).where(
        BillingDocument.client_id == client_id,
        BillingDocument.tenant_id == tenant_id,
    )
    if period_start:
        doc_query = doc_query.where(BillingDocument.billing_period_start >= period_start)
    if period_end:
        doc_query = doc_query.where(BillingDocument.billing_period_end <= period_end)
    doc_result = await db.execute(doc_query.order_by(BillingDocument.created_at.desc()))
    docs = doc_result.scalars().all()

    # For each document, compute amount_paid from confirmed allocations
    documents = []
    total_invoiced = Decimal("0.00")
    total_paid_on_docs = Decimal("0.00")
    for doc in docs:
        alloc_result = await db.execute(
            select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0))
            .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
            .where(
                PaymentAllocation.billing_document_id == doc.id,
                ClientPayment.status == "confirmed",
            )
        )
        amount_paid = Decimal(str(alloc_result.scalar_one())).quantize(Decimal("0.01"))
        outstanding = (doc.total_amount - amount_paid).quantize(Decimal("0.01"))
        total_invoiced += doc.total_amount
        total_paid_on_docs += amount_paid
        documents.append(
            {
                "id": doc.id,
                "invoice_number": getattr(doc, "invoice_number", None),
                "billing_period_start": doc.billing_period_start,
                "billing_period_end": doc.billing_period_end,
                "total_amount": doc.total_amount,
                "amount_paid": amount_paid,
                "outstanding_balance": outstanding,
                "due_date": getattr(doc, "due_date", None),
                "status": doc.status,
                "issued_at": getattr(doc, "issued_at", None),
            }
        )

    # Fetch payments for this client
    pay_result = await db.execute(
        select(ClientPayment)
        .where(
            ClientPayment.client_id == client_id,
            ClientPayment.tenant_id == tenant_id,
        )
        .order_by(ClientPayment.value_date.desc())
    )
    payments = pay_result.scalars().all()

    # Compute advance_balance: sum of unallocated confirmed payments
    advance_balance = Decimal("0.00")
    payments_out = []
    for p in payments:
        alloc_sum_result = await db.execute(
            select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0)).where(
                PaymentAllocation.payment_id == p.id
            )
        )
        allocated = Decimal(str(alloc_sum_result.scalar_one())).quantize(Decimal("0.01"))
        unallocated = (p.amount - allocated).quantize(Decimal("0.01"))
        if p.status == "confirmed" and p.billing_document_id is None:
            advance_balance += unallocated
        payments_out.append(
            {
                "id": p.id,
                "amount": p.amount,
                "value_date": p.value_date,
                "payment_method": p.payment_method,
                "reference": p.reference,
                "status": p.status,
                "allocated": allocated,
                "unallocated": unallocated,
            }
        )

    total_outstanding = (total_invoiced - total_paid_on_docs).quantize(Decimal("0.01"))
    return {
        "client": serialize_client(client),
        "documents": documents,
        "payments": payments_out,
        "summary": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid_on_docs,
            "total_outstanding": total_outstanding,
            "advance_balance": advance_balance,
        },
    }
