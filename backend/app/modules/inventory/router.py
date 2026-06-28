from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.rbac import require_permission
from app.modules.inventory import schemas, service
from app.modules.inventory.models import Item, StockMovement, Warehouse

# Consider adding granular permissions later like INVENTORY_READ, INVENTORY_WRITE
router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.post("/warehouses", response_model=schemas.WarehouseResponse)
async def create_warehouse(
    payload: schemas.WarehouseCreate,
    principal: Annotated[Principal, Depends(require_permission("OPERATIONS_ADMIN"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_warehouse(db, principal.tenant_id, payload.name, payload.location)

@router.get("/warehouses", response_model=list[schemas.WarehouseResponse])
async def list_warehouses(
    principal: Annotated[Principal, Depends(require_permission("OPERATIONS_ADMIN"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    stmt = select(Warehouse).where(Warehouse.tenant_id == principal.tenant_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/items", response_model=schemas.ItemResponse)
async def create_item(
    payload: schemas.ItemCreate,
    principal: Annotated[Principal, Depends(require_permission("OPERATIONS_ADMIN"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_item(db, principal.tenant_id, payload)


@router.get("/items", response_model=list[schemas.ItemResponse])
async def list_items(
    principal: Annotated[Principal, Depends(require_permission("OPERATIONS_ADMIN"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    stmt = select(Item).where(Item.tenant_id == principal.tenant_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/movements/in", response_model=schemas.StockMovementResponse)
async def register_stock_in(
    payload: schemas.StockMovementIn,
    principal: Annotated[Principal, Depends(require_permission("OPERATIONS_ADMIN"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.register_stock_in(db, principal.tenant_id, payload, principal.user_id)


@router.post("/movements/out", response_model=schemas.StockMovementResponse)
async def register_stock_out(
    payload: schemas.StockMovementOut,
    principal: Annotated[Principal, Depends(require_permission("OPERATIONS_ADMIN"))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.register_stock_out(db, principal.tenant_id, payload, principal.user_id)
