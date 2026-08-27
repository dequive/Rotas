from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.cache import invalidate_tenant_caches
from app.core.deps import get_session
from app.core.rbac import BILLING_READ, BILLING_WRITE, require_permission
from app.modules.clients import schemas, service

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[schemas.ClientResponse])
async def list_clients(
    principal: Annotated[Principal, Depends(require_permission(BILLING_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return await service.list_clients(db, principal.tenant_id, limit=limit, offset=offset)


@router.post("", status_code=201, response_model=schemas.ClientResponse)
async def create_client(
    request: Request,
    payload: schemas.ClientCreate,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.create_client(db, principal.tenant_id, payload)
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{client_id}", response_model=schemas.ClientResponse)
async def get_client(
    client_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(BILLING_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_client_with_balance(db, client_id, principal.tenant_id)


@router.patch("/{client_id}", response_model=schemas.ClientResponse)
async def patch_client(
    request: Request,
    client_id: UUID,
    payload: schemas.ClientPatch,
    principal: Annotated[Principal, Depends(require_permission(BILLING_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    res = await service.patch_client(db, client_id, principal.tenant_id, payload)
    await invalidate_tenant_caches(getattr(request.app.state, "redis", None), principal.tenant_id)
    return res


@router.get("/{client_id}/statement", response_model=schemas.ClientStatementOut)
async def get_client_statement(
    client_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(BILLING_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
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
