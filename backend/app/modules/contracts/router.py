from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.idempotency import execute_http_idempotent
from app.core.permissions import DASHBOARD_ROLES, WRITE_ROLES, require_roles
from app.core.deps import get_session
from app.modules.contracts import schemas, service

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/")
async def list_contracts(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    client_name: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return await service.list_contracts(
        db,
        principal.tenant_id,
        client_name=client_name,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.post("/")
async def create_contract(
    payload: schemas.ContractCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="contracts.create",
        entity_type="contract",
        payload=payload,
        handler=lambda: service.create_contract(
            db,
            principal.tenant_id,
            payload,
            actor_id=principal.user_id,
        ),
    )


@router.get("/{contract_id}")
async def get_contract(
    contract_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_contract(db, principal.tenant_id, contract_id)


@router.patch("/{contract_id}")
async def patch_contract(
    contract_id: UUID,
    payload: schemas.ContractPatch,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_contract(
        db,
        principal.tenant_id,
        contract_id,
        payload,
        actor_id=principal.user_id,
    )
