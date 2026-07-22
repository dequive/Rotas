from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.modules import MODULE_OFICINA, require_module
from app.core.rbac import WORKSHOP_READ, WORKSHOP_WRITE, require_permission
from app.modules.workshop import quote_schemas as schemas
from app.modules.workshop import quote_service as service

router = APIRouter(prefix="/workshop/quotes", tags=["workshop-quotes"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def create_quote(
    payload: schemas.QuoteCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/quotes — Criar orçamento de oficina (MODULE_OFICINA)."""
    return await service.create_quote(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get(
    "",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def list_quotes(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """GET /api/v1/workshop/quotes — Listar orçamentos de oficina (MODULE_OFICINA)."""
    return await service.list_quotes(
        db,
        principal.tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{quote_id}",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def get_quote_detail(
    quote_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """GET /api/v1/workshop/quotes/{id} — Detalhes do orçamento com itens (MODULE_OFICINA)."""
    return await service.get_quote_detail(db, principal.tenant_id, quote_id)


@router.post(
    "/{quote_id}/accept",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def accept_quote(
    quote_id: UUID,
    payload: schemas.QuoteAcceptRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/quotes/{id}/accept — Aceitar orçamento (converte em OS ou anexa a OS existente se for suplementar).
    Garante FOR UPDATE lock no orcamento para prevenir duplo clique ou race conditions.
    """
    return await service.accept_quote(
        db, principal.tenant_id, quote_id,
        acceptance_channel=payload.acceptance_channel,
        accepted_by_person_name=payload.accepted_by_person_name,
        actor_id=principal.user_id,
    )


@router.post(
    "/{quote_id}/reject",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def reject_quote(
    quote_id: UUID,
    payload: schemas.QuoteRejectRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/quotes/{id}/reject — Rejeitar orçamento com motivo (MODULE_OFICINA)."""
    return await service.reject_quote(
        db, principal.tenant_id, quote_id, reason=payload.reason, actor_id=principal.user_id
    )
