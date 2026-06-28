from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.inventory.models import Item, ItemCategory, StockMovement, Warehouse
from app.modules.inventory.schemas import ItemCreate, StockMovementIn, StockMovementOut


async def create_warehouse(db: AsyncSession, tenant_id: UUID, name: str, location: Optional[str] = None) -> Warehouse:
    wh = Warehouse(tenant_id=tenant_id, name=name, location=location)
    db.add(wh)
    await db.commit()
    await db.refresh(wh)
    return wh

async def create_item(db: AsyncSession, tenant_id: UUID, payload: ItemCreate) -> Item:
    item = Item(
        tenant_id=tenant_id,
        category_id=payload.category_id,
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        unit_of_measure=payload.unit_of_measure,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

async def register_stock_in(db: AsyncSession, tenant_id: UUID, payload: StockMovementIn, actor_id: Optional[UUID] = None) -> StockMovement:
    item = await db.get(Item, payload.item_id)
    if not item or item.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Item not found")

    warehouse = await db.get(Warehouse, payload.warehouse_id)
    if not warehouse or warehouse.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # Calculate Weighted Average Cost
    current_qty = item.current_stock
    current_avg_cost = item.average_unit_cost
    incoming_qty = payload.quantity
    incoming_cost = payload.unit_cost

    new_total_value = (current_qty * current_avg_cost) + (incoming_qty * incoming_cost)
    new_total_qty = current_qty + incoming_qty
    new_avg_cost = new_total_value / new_total_qty if new_total_qty > 0 else Decimal("0.00")

    # Create Movement
    movement = StockMovement(
        tenant_id=tenant_id,
        item_id=item.id,
        warehouse_id=warehouse.id,
        movement_type="IN",
        quantity=incoming_qty,
        unit_cost=incoming_cost,
        total_value=incoming_qty * incoming_cost,
        reference_doc=payload.reference_doc,
        notes=payload.notes,
        created_by=actor_id
    )
    db.add(movement)

    # Update Item
    item.current_stock = new_total_qty
    item.average_unit_cost = new_avg_cost

    await db.commit()
    await db.refresh(movement)
    return movement


async def register_stock_out(db: AsyncSession, tenant_id: UUID, payload: StockMovementOut, actor_id: Optional[UUID] = None) -> StockMovement:
    item = await db.get(Item, payload.item_id)
    if not item or item.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.current_stock < payload.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    warehouse = await db.get(Warehouse, payload.warehouse_id)
    if not warehouse or warehouse.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Warehouse not found")

    # In OUT movements, the unit cost is the current Average Unit Cost
    out_cost = item.average_unit_cost
    out_total_value = payload.quantity * out_cost

    movement = StockMovement(
        tenant_id=tenant_id,
        item_id=item.id,
        warehouse_id=warehouse.id,
        movement_type="OUT",
        quantity=payload.quantity,
        unit_cost=out_cost,
        total_value=out_total_value,
        reference_doc=payload.reference_doc,
        notes=payload.notes,
        created_by=actor_id
    )
    db.add(movement)

    # Update Item
    item.current_stock -= payload.quantity

    await db.commit()
    await db.refresh(movement)
    return movement
