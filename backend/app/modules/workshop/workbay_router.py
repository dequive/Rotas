from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.modules import MODULE_OFICINA, require_module
from app.core.rbac import WORKSHOP_READ, WORKSHOP_WRITE, require_permission
from app.modules.workshop import workbay_schemas as schemas
from app.modules.workshop import workbay_service as service

router = APIRouter(prefix="/workshop/bays", tags=["workshop-bays"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def create_work_bay(
    payload: schemas.WorkBayCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/bays — Criar baía/estação de trabalho na oficina (MODULE_OFICINA)."""
    return await service.create_work_bay(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get(
    "",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def list_work_bays(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    is_active: bool | None = None,
) -> list[dict]:
    """GET /api/v1/workshop/bays — Listar baías de trabalho da oficina (MODULE_OFICINA)."""
    return await service.list_work_bays(db, principal.tenant_id, is_active=is_active)


@router.patch(
    "/{bay_id}",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def update_work_bay(
    bay_id: UUID,
    payload: schemas.WorkBayUpdate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """PATCH /api/v1/workshop/bays/{id} — Atualizar baía de trabalho (MODULE_OFICINA)."""
    return await service.update_work_bay(
        db, principal.tenant_id, bay_id, payload, actor_id=principal.user_id
    )
