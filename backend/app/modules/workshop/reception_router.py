from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.deps import get_session
from app.core.modules import MODULE_OFICINA, require_module
from app.core.rbac import WORKSHOP_READ, WORKSHOP_WRITE, require_permission
from app.modules.workshop import reception_schemas as schemas
from app.modules.workshop import reception_service as service

router = APIRouter(prefix="/workshop/receptions", tags=["workshop-receptions"])


def _require_tenant_id(principal: Principal) -> UUID:
    if principal.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context required for workshop operations.",
        )
    return principal.tenant_id


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def create_reception(
    payload: schemas.ReceptionCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/receptions — Check-in de viatura na oficina (MODULE_OFICINA)."""
    tenant_id = _require_tenant_id(principal)
    return await service.create_reception(
        db, tenant_id, payload, actor_id=principal.user_id
    )


@router.get(
    "",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def list_receptions(
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    status: str | None = None,
    vehicle_id: UUID | None = None,
    client_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """GET /api/v1/workshop/receptions — Listar check-ins da oficina (MODULE_OFICINA)."""
    tenant_id = _require_tenant_id(principal)
    return await service.list_receptions(
        db,
        tenant_id,
        status_filter=status,
        vehicle_id=vehicle_id,
        client_id=client_id,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{reception_id}",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def get_reception_detail(
    reception_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """GET /api/v1/workshop/receptions/{id} — Detalhe do check-in com fotos (MODULE_OFICINA)."""
    tenant_id = _require_tenant_id(principal)
    return await service.get_reception_detail(db, tenant_id, reception_id)


@router.post(
    "/{reception_id}/photos",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def add_reception_photo(
    reception_id: UUID,
    payload: schemas.ReceptionPhotoCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/receptions/{id}/photos — Adicionar foto append-only (MODULE_OFICINA)."""
    tenant_id = _require_tenant_id(principal)
    return await service.add_reception_photo(
        db, tenant_id, reception_id, payload, actor_id=principal.user_id
    )


@router.patch(
    "/{reception_id}/status",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def update_reception_status(
    reception_id: UUID,
    payload: schemas.ReceptionStatusUpdate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """PATCH /api/v1/workshop/receptions/{id}/status — Atualizar estado (MODULE_OFICINA)."""
    tenant_id = _require_tenant_id(principal)
    return await service.update_reception_status(
        db, tenant_id, reception_id, payload.status, actor_id=principal.user_id
    )


@router.post(
    "/{reception_id}/release",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def release_vehicle(
    reception_id: UUID,
    payload: schemas.VehicleReleaseCreate,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """POST /api/v1/workshop/receptions/{id}/release — Registar entrega da viatura ao cliente (MODULE_OFICINA)."""
    tenant_id = _require_tenant_id(principal)
    return await service.release_vehicle(
        db, tenant_id, reception_id, payload, actor_id=principal.user_id
    )


@router.get(
    "/vehicles/{vehicle_id}/history",
    dependencies=[Depends(require_module(MODULE_OFICINA))],
)
async def get_vehicle_intervention_history(
    vehicle_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(WORKSHOP_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    """Return the vehicle's aggregated workshop intervention history."""
    tenant_id = _require_tenant_id(principal)
    return await service.get_vehicle_intervention_history(db, tenant_id, vehicle_id)
