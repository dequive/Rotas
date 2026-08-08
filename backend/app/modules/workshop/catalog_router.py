from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.deps import get_session
from app.core.modules import MODULE_OFICINA, require_module
from app.core.rbac import WORKSHOP_READ, WORKSHOP_WRITE, require_permission
from app.modules.workshop import catalog_schemas as schemas
from app.modules.workshop import catalog_service as service

router = APIRouter(prefix="/workshop/catalog", tags=["workshop-catalog"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def create_catalog_item(
    payload: schemas.CatalogItemCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/catalog — Criar item no catálogo de serviços (MODULE_OFICINA)."""
    return await service.create_catalog_item(
        db, principal.tenant_id, payload, actor_id=principal.user_id
    )


@router.get(
    "",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def list_catalog_items(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    category: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """GET /api/v1/workshop/catalog — Listar itens do catálogo (MODULE_OFICINA)."""
    return await service.list_catalog_items(
        db,
        principal.tenant_id,
        category=category,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )


@router.patch(
    "/{item_id}",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def update_catalog_item(
    item_id: UUID,
    payload: schemas.CatalogItemUpdate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """PATCH /api/v1/workshop/catalog/{id} — Atualizar item do catálogo (MODULE_OFICINA)."""
    return await service.update_catalog_item(
        db, principal.tenant_id, item_id, payload, actor_id=principal.user_id
    )
