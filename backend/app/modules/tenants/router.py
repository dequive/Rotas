from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.permissions import ADMIN_ROLES, DASHBOARD_ROLES, require_roles
from app.core.deps import get_session
from app.modules.tenants import schemas, service

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me")
async def get_my_tenant(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_current_tenant(db, principal.tenant_id)


@router.patch("/me")
async def patch_my_tenant(
    payload: schemas.TenantPatch,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.patch_current_tenant(
        db,
        principal.tenant_id,
        payload,
        actor_id=principal.user_id,
    )


@router.get("/me/driver-despacho-table")
async def get_my_driver_despacho_table(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.get_driver_despacho_table(db, principal.tenant_id)


@router.put("/me/driver-despacho-table")
async def put_my_driver_despacho_table(
    payload: schemas.DriverDespachoTableUpdate,
    principal: Annotated[Principal, Depends(require_roles(*ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.put_driver_despacho_table(
        db,
        principal.tenant_id,
        payload,
        actor_id=principal.user_id,
    )
