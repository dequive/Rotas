from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.modules.inventory.schemas import (
    ItemCreate,
    StockMovementIn,
    StockMovementOut,
)
from app.modules.inventory.service import (
    create_item,
    create_warehouse,
    register_stock_in,
    register_stock_out,
)


@pytest.mark.asyncio
async def test_stock_movements_preserve_weighted_average_and_identity(db, tenant_id):
    warehouse = await create_warehouse(db, tenant_id, "Armazém Central", "Maputo")
    item = await create_item(
        db,
        tenant_id,
        ItemCreate(
            sku=f"PART-{uuid4().hex[:8]}",
            name="Filtro de óleo",
        ),
    )

    first = await register_stock_in(
        db,
        tenant_id,
        StockMovementIn(
            item_id=item.id,
            warehouse_id=warehouse.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("100"),
        ),
    )
    second = await register_stock_in(
        db,
        tenant_id,
        StockMovementIn(
            item_id=item.id,
            warehouse_id=warehouse.id,
            quantity=Decimal("10"),
            unit_cost=Decimal("200"),
        ),
    )
    issued = await register_stock_out(
        db,
        tenant_id,
        StockMovementOut(
            item_id=item.id,
            warehouse_id=warehouse.id,
            quantity=Decimal("5"),
        ),
    )
    await db.refresh(item)

    assert first.id is not None
    assert second.id is not None
    assert issued.id is not None
    assert item.current_stock == Decimal("15")
    assert item.average_unit_cost == Decimal("150")
    assert issued.unit_cost == Decimal("150")
    assert issued.total_value == Decimal("750")
    assert issued.created_at is not None


@pytest.mark.asyncio
async def test_stock_out_rejects_insufficient_quantity(db, tenant_id):
    warehouse = await create_warehouse(db, tenant_id, "Armazém Secundário")
    item = await create_item(
        db,
        tenant_id,
        ItemCreate(name=f"Peça {uuid4().hex[:8]}"),
    )

    with pytest.raises(HTTPException) as captured:
        await register_stock_out(
            db,
            tenant_id,
            StockMovementOut(
                item_id=item.id,
                warehouse_id=warehouse.id,
                quantity=Decimal("1"),
            ),
        )

    assert captured.value.status_code == 400
    assert captured.value.detail == "Insufficient stock"
