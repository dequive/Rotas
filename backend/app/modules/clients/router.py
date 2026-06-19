from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_principal
from app.core.deps import get_session
from app.modules.clients import schemas, service

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("")
async def list_clients(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
):
    return await service.list_clients(db, principal.tenant_id, limit=limit, offset=offset)


@router.post("", status_code=201)
async def create_client(
    payload: schemas.ClientCreate,
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
):
    return await service.create_client(db, principal.tenant_id, payload)


@router.get("/{client_id}")
async def get_client(
    client_id: UUID,
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
):
    return await service.get_client_with_balance(db, client_id, principal.tenant_id)


@router.patch("/{client_id}")
async def patch_client(
    client_id: UUID,
    payload: schemas.ClientPatch,
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
):
    return await service.patch_client(db, client_id, principal.tenant_id, payload)


@router.get("/{client_id}/statement")
async def get_client_statement(
    client_id: UUID,
    principal=Depends(get_current_principal),
    db: AsyncSession = Depends(get_session),
    period_start: datetime | None = None,
    period_end: datetime | None = None,
):
    """Return a full client statement with invoices, payments, and balance summary.

    Balance is computed synchronously from DB — no cache (PAY-03 requirement).
    Optional period_start / period_end filter by billing_period_start / billing_period_end.
    """
    return await service.get_client_statement(
        db,
        client_id,
        principal.tenant_id,
        period_start=period_start,
        period_end=period_end,
    )
