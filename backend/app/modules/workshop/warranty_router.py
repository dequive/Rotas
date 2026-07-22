from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.modules import MODULE_OFICINA, require_module
from app.core.rbac import WORKSHOP_READ, WORKSHOP_WRITE, require_permission
from app.modules.workshop import warranty_schemas as schemas
from app.modules.workshop import warranty_service as service

router = APIRouter(prefix="/workshop/warranties", tags=["workshop-warranties"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def create_warranty(
    payload: schemas.WarrantyCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/warranties — Emitir garantia de serviço/peça (MODULE_OFICINA)."""
    return await service.create_warranty(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get(
    "",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def list_warranties(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    vehicle_id: UUID | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """GET /api/v1/workshop/warranties — Listar garantias de oficina (MODULE_OFICINA)."""
    return await service.list_warranties(
        db,
        principal.tenant_id,
        vehicle_id=vehicle_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{warranty_id}/claim",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def claim_warranty(
    warranty_id: UUID,
    payload: schemas.WarrantyClaimRequest,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/warranties/{id}/claim — Acionar garantia com validação de km/prazo (MODULE_OFICINA)."""
    return await service.claim_warranty(
        db, principal.tenant_id, warranty_id, payload, actor_id=principal.user_id
    )
