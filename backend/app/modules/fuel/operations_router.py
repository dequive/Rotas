from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.rbac import FUEL_APPROVE, FUEL_READ, FUEL_WRITE, require_permission
from app.modules.fuel import operations
from app.modules.fuel.operations_schemas import (
    FuelPurchaseCreate,
    FuelReceiptCreate,
    FuelStockAdjustmentApprove,
    FuelStockCountCreate,
    FuelTankCreate,
    VehicleRefuelCreate,
)

router = APIRouter(prefix="/fuel-operations", tags=["fuel-operations"])


@router.get("/board")
async def get_fuel_control_board(
    principal: Annotated[Principal, Depends(require_permission(FUEL_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.get_fuel_control_board(db, principal.tenant_id)


@router.get("/tanks")
async def list_tanks(
    principal: Annotated[Principal, Depends(require_permission(FUEL_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.list_tanks(db, principal.tenant_id)


@router.post("/tanks")
async def create_tank(
    payload: FuelTankCreate,
    principal: Annotated[Principal, Depends(require_permission(FUEL_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="fuel_operations.tank.create",
        entity_type="fuel_tank",
        payload=payload,
        handler=lambda: operations.create_tank(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/purchases")
async def create_purchase(
    payload: FuelPurchaseCreate,
    principal: Annotated[Principal, Depends(require_permission(FUEL_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="fuel_operations.purchase.create",
        entity_type="fuel_purchase",
        payload=payload,
        handler=lambda: operations.create_purchase(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/purchases/{purchase_id}/approve")
async def approve_purchase(
    purchase_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(FUEL_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.approve_purchase(
        db, principal.tenant_id, purchase_id, actor_id=principal.user_id
    )


@router.post("/receipts")
async def create_verified_receipt(
    payload: FuelReceiptCreate,
    principal: Annotated[Principal, Depends(require_permission(FUEL_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="fuel_operations.receipt.create",
        entity_type="fuel_receipt",
        payload=payload,
        handler=lambda: operations.create_verified_receipt(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/vehicle-refuels")
async def create_vehicle_refuel(
    payload: VehicleRefuelCreate,
    principal: Annotated[Principal, Depends(require_permission(FUEL_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="fuel_operations.vehicle_refuel.create",
        entity_type="vehicle_refuel",
        payload=payload,
        handler=lambda: operations.create_vehicle_refuel(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/stock-counts")
async def create_stock_count(
    payload: FuelStockCountCreate,
    principal: Annotated[Principal, Depends(require_permission(FUEL_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="fuel_operations.stock_count.create",
        entity_type="fuel_stock_count",
        payload=payload,
        handler=lambda: operations.create_stock_count(
            db, principal.tenant_id, payload, actor_id=principal.user_id
        ),
    )


@router.post("/stock-counts/{stock_count_id}/approve-adjustment")
async def approve_stock_adjustment(
    stock_count_id: UUID,
    payload: FuelStockAdjustmentApprove,
    principal: Annotated[Principal, Depends(require_permission(FUEL_APPROVE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await operations.approve_stock_adjustment(
        db,
        principal.tenant_id,
        stock_count_id,
        actor_id=principal.user_id,
        notes=payload.notes,
    )


@router.get("/movements")
async def list_movements(
    principal: Annotated[Principal, Depends(require_permission(FUEL_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
    tank_id: UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
):
    return await operations.list_movements(db, principal.tenant_id, tank_id=tank_id, limit=limit)
