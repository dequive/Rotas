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
