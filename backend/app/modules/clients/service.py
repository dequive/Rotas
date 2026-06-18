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


async def _get_outstanding_balance(
    db: AsyncSession, client_id: UUID, tenant_id: UUID
) -> Decimal:
    """Sum total_amount of issued billing documents for this client.

    Uses BillingDocument.client_id FK added in Plan 02 migration (b).
    Only 'issued' status documents count as outstanding — draft/paid/voided are excluded.
    """
    result = await db.execute(
        select(func.coalesce(func.sum(BillingDocument.total_amount), 0)).where(
            BillingDocument.client_id == client_id,
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status == "issued",
        )
    )
    return Decimal(str(result.scalar_one()))


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


async def get_client_with_balance(
    db: AsyncSession, client_id: UUID, tenant_id: UUID
) -> dict:
    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError(
            "client_not_found",
            "Cliente não encontrado.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    balance = await _get_outstanding_balance(db, client_id, tenant_id)
    return serialize_client(client, outstanding_balance=balance)


async def create_client(
    db: AsyncSession, tenant_id: UUID, payload: ClientCreate
) -> dict:
    client = Client(tenant_id=tenant_id, **payload.model_dump())
    db.add(client)
    try:
        await db.flush()
    except IntegrityError:
        raise ApiError(
            "nuit_already_exists",
            "NUIT já existe neste tenant.",
            status_code=status.HTTP_409_CONFLICT,
        )
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
