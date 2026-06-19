from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.drivers.models import Driver
from app.modules.fuel.models import (
    FuelMovement,
    FuelPurchase,
    FuelReceipt,
    FuelStockCount,
    FuelTank,
    VehicleRefuel,
)
from app.modules.fuel.operations_schemas import (
    FuelPurchaseCreate,
    FuelReceiptCreate,
    FuelStockCountCreate,
    FuelTankCreate,
    VehicleRefuelCreate,
)
from app.modules.operational_exceptions.service import ensure_exception
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def serialize_tank(tank: FuelTank) -> dict:
    return {
        "id": tank.id,
        "tenant_id": tank.tenant_id,
        "code": tank.code,
        "name": tank.name,
        "fuel_type": tank.fuel_type,
        "capacity_liters": tank.capacity_liters,
        "minimum_stock_liters": tank.minimum_stock_liters,
        "current_stock_liters": tank.current_stock_liters,
        "average_unit_cost": tank.average_unit_cost,
        "location": tank.location,
        "status": tank.status,
        "created_at": tank.created_at,
        "updated_at": tank.updated_at,
    }


def serialize_purchase(purchase: FuelPurchase) -> dict:
    return {
        "id": purchase.id,
        "tenant_id": purchase.tenant_id,
        "supplier_name": purchase.supplier_name,
        "supplier_third_party_id": purchase.supplier_third_party_id,
        "purchase_reference": purchase.purchase_reference,
        "fuel_type": purchase.fuel_type,
        "ordered_liters": purchase.ordered_liters,
        "unit_price": purchase.unit_price,
        "total_cost": purchase.total_cost,
        "status": purchase.status,
        "ordered_at": purchase.ordered_at,
        "approved_by": purchase.approved_by,
        "approved_at": purchase.approved_at,
        "notes": purchase.notes,
        "created_at": purchase.created_at,
    }


def serialize_movement(movement: FuelMovement) -> dict:
    return {
        "id": movement.id,
        "tenant_id": movement.tenant_id,
        "tank_id": movement.tank_id,
        "movement_type": movement.movement_type,
        "direction": movement.direction,
        "liters": movement.liters,
        "balance_after_liters": movement.balance_after_liters,
        "unit_cost": movement.unit_cost,
        "total_cost": movement.total_cost,
        "source_type": movement.source_type,
        "source_id": movement.source_id,
        "occurred_at": movement.occurred_at,
        "recorded_by": movement.recorded_by,
        "notes": movement.notes,
        "created_at": movement.created_at,
    }


class FuelMovementService:
    """Single writer for tank stock.

    Callers describe movements; this service owns balance mutation.
    """

    @staticmethod
    async def record(
        db: AsyncSession,
        tenant_id: UUID,
        *,
        tank_id: UUID,
        movement_type: str,
        direction: str,
        liters: float | Decimal,
        source_type: str,
        source_id: UUID,
        occurred_at: datetime,
        actor_id: UUID | None,
        unit_cost: float | Decimal | None = None,
        notes: str | None = None,
    ) -> FuelMovement:
        quantity = _decimal(liters)
        if quantity <= 0:
            raise ApiError(
                "invalid_fuel_quantity",
                "Fuel movement liters must be greater than zero.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if direction not in {"in", "out"}:
            raise ApiError(
                "invalid_fuel_direction",
                "Fuel movement direction must be in or out.",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        tank = await db.scalar(
            select(FuelTank)
            .where(FuelTank.id == tank_id, FuelTank.tenant_id == tenant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not tank or tank.status != "active":
            raise ApiError("fuel_tank_not_found", "Active fuel tank not found.", status_code=404)

        previous_balance = _decimal(tank.current_stock_liters)
        new_balance = (
            previous_balance + quantity if direction == "in" else previous_balance - quantity
        )
        if new_balance < 0:
            raise ApiError(
                "insufficient_fuel_stock",
                "Fuel tank does not have enough stock.",
                status_code=status.HTTP_409_CONFLICT,
                details={
                    "tank_id": str(tank.id),
                    "available_liters": str(previous_balance),
                    "requested_liters": str(quantity),
                },
            )
        if new_balance > _decimal(tank.capacity_liters):
            raise ApiError(
                "fuel_tank_capacity_exceeded",
                "Fuel receipt would exceed tank capacity.",
                status_code=status.HTTP_409_CONFLICT,
            )

        previous_average_cost = _decimal(tank.average_unit_cost)
        movement_unit_cost = (
            _decimal(unit_cost)
            if unit_cost is not None
            else previous_average_cost
            if direction == "out"
            else None
        )
        movement = FuelMovement(
            tenant_id=tenant_id,
            tank_id=tank.id,
            movement_type=movement_type,
            direction=direction,
            liters=quantity,
            balance_after_liters=new_balance,
            unit_cost=movement_unit_cost,
            total_cost=movement_unit_cost * quantity if movement_unit_cost is not None else None,
            source_type=source_type,
            source_id=source_id,
            occurred_at=occurred_at,
            recorded_by=actor_id,
            notes=notes,
        )
        tank.current_stock_liters = new_balance
        if direction == "in" and movement_unit_cost is not None and new_balance > 0:
            tank.average_unit_cost = (
                (previous_balance * previous_average_cost) + (quantity * movement_unit_cost)
            ) / new_balance
        db.add(movement)
        await db.flush()
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            action="fuel_movement.recorded",
            entity_type="fuel_tank",
            entity_id=tank.id,
            old_values={"current_stock_liters": str(previous_balance)},
            new_values={
                "movement_id": str(movement.id),
                "movement_type": movement_type,
                "direction": direction,
                "liters": str(quantity),
                "current_stock_liters": str(new_balance),
            },
        )
        if new_balance <= _decimal(tank.minimum_stock_liters):
            await ensure_exception(
                db,
                tenant_id,
                entity_type="fuel_tank",
                entity_id=tank.id,
                exception_type="fuel_low_stock",
                severity="high",
                title=f"Stock baixo no tanque {tank.code}",
                message="O stock teórico atingiu ou ficou abaixo do mínimo configurado.",
                actor_id=actor_id,
                context={
                    "current_stock_liters": str(new_balance),
                    "minimum_stock_liters": str(tank.minimum_stock_liters),
                },
                source_type="fuel_movement",
            )
        return movement


async def create_tank(
    db: AsyncSession,
    tenant_id: UUID,
    payload: FuelTankCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    capacity = _decimal(payload.capacity_liters)
    minimum = _decimal(payload.minimum_stock_liters)
    if capacity <= 0 or minimum < 0 or minimum > capacity:
        raise ApiError(
            "invalid_fuel_tank_capacity",
            "Tank capacity and minimum stock are invalid.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    existing = await db.scalar(
        select(FuelTank.id).where(FuelTank.tenant_id == tenant_id, FuelTank.code == payload.code)
    )
    if existing:
        raise ApiError("fuel_tank_code_exists", "Fuel tank code already exists.", status_code=409)

    tank = FuelTank(tenant_id=tenant_id, **payload.model_dump())
    db.add(tank)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="fuel_tank.created",
        entity_type="fuel_tank",
        entity_id=tank.id,
        new_values={"code": tank.code, "capacity_liters": str(capacity)},
    )
    await db.commit()
    await db.refresh(tank)
    return serialize_tank(tank)


async def list_tanks(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    result = await db.execute(
        select(FuelTank).where(FuelTank.tenant_id == tenant_id).order_by(FuelTank.code)
    )
    return [serialize_tank(tank) for tank in result.scalars()]


async def create_purchase(
    db: AsyncSession,
    tenant_id: UUID,
    payload: FuelPurchaseCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    liters = _decimal(payload.ordered_liters)
    unit_price = _decimal(payload.unit_price)
    if liters <= 0 or unit_price < 0:
        raise ApiError(
            "invalid_fuel_purchase",
            "Purchase liters must be positive and unit price cannot be negative.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    existing = await db.scalar(
        select(FuelPurchase.id).where(
            FuelPurchase.tenant_id == tenant_id,
            FuelPurchase.purchase_reference == payload.purchase_reference,
        )
    )
    if existing:
        raise ApiError(
            "fuel_purchase_reference_exists",
            "Fuel purchase reference already exists.",
            status_code=409,
        )
    purchase = FuelPurchase(
        tenant_id=tenant_id,
        **payload.model_dump(),
        total_cost=liters * unit_price,
    )
    db.add(purchase)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="fuel_purchase.created",
        entity_type="fuel_purchase",
        entity_id=purchase.id,
        new_values={"reference": purchase.purchase_reference, "ordered_liters": str(liters)},
    )
    await db.commit()
    await db.refresh(purchase)
    return serialize_purchase(purchase)


async def approve_purchase(
    db: AsyncSession,
    tenant_id: UUID,
    purchase_id: UUID,
    *,
    actor_id: UUID | None,
) -> dict:
    purchase = await _require_purchase(db, tenant_id, purchase_id)
    if purchase.status == "approved":
        return serialize_purchase(purchase)
    if purchase.status != "pending":
        raise ApiError(
            "invalid_fuel_purchase_status",
            "Purchase cannot be approved.",
            status_code=409,
        )
    purchase.status = "approved"
    purchase.approved_by = actor_id
    purchase.approved_at = datetime.now(UTC)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="fuel_purchase.approved",
        entity_type="fuel_purchase",
        entity_id=purchase.id,
        old_values={"status": "pending"},
        new_values={"status": purchase.status},
    )
    await db.commit()
    await db.refresh(purchase)
    return serialize_purchase(purchase)


async def create_verified_receipt(
    db: AsyncSession,
    tenant_id: UUID,
    payload: FuelReceiptCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    purchase = await _require_purchase(db, tenant_id, payload.purchase_id, for_update=True)
    if payload.delivery_note_number:
        duplicate_delivery_note = await db.scalar(
            select(FuelReceipt.id).where(
                FuelReceipt.tenant_id == tenant_id,
                FuelReceipt.purchase_id == purchase.id,
                FuelReceipt.delivery_note_number == payload.delivery_note_number,
            )
        )
        if duplicate_delivery_note:
            raise ApiError(
                "fuel_receipt_delivery_note_exists",
                "Fuel receipt delivery note already exists for this purchase.",
                status_code=409,
            )
    if purchase.status != "approved":
        raise ApiError(
            "fuel_purchase_not_approved",
            "Fuel purchase must be approved before receipt.",
            status_code=409,
        )
    tank = await _require_tank(db, tenant_id, payload.tank_id)
    if tank.fuel_type != purchase.fuel_type:
        raise ApiError(
            "fuel_type_mismatch",
            "Tank and purchase fuel types differ.",
            status_code=409,
        )
    received_before = await db.scalar(
        select(func.coalesce(func.sum(FuelReceipt.received_liters), 0)).where(
            FuelReceipt.tenant_id == tenant_id,
            FuelReceipt.purchase_id == purchase.id,
            FuelReceipt.status == "verified",
        )
    )
    received_after = _decimal(received_before or 0) + _decimal(payload.received_liters)
    if received_after > _decimal(purchase.ordered_liters):
        raise ApiError(
            "fuel_receipt_exceeds_purchase",
            "Verified fuel receipts cannot exceed purchased liters.",
            status_code=409,
        )

    receipt = FuelReceipt(tenant_id=tenant_id, verified_by=actor_id, **payload.model_dump())
    db.add(receipt)
    await db.flush()
    movement = await FuelMovementService.record(
        db,
        tenant_id,
        tank_id=tank.id,
        movement_type="purchase_receipt",
        direction="in",
        liters=payload.received_liters,
        source_type="fuel_receipt",
        source_id=receipt.id,
        occurred_at=payload.received_at,
        actor_id=actor_id,
        unit_cost=purchase.unit_price,
        notes=payload.notes,
    )
    receipt.movement_id = movement.id
    if received_after == _decimal(purchase.ordered_liters):
        purchase.status = "received"
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="fuel_receipt.verified",
        entity_type="fuel_receipt",
        entity_id=receipt.id,
        new_values={
            "movement_id": str(movement.id),
            "received_liters": str(payload.received_liters),
        },
    )
    await db.commit()
    await db.refresh(receipt)
    return {
        "id": receipt.id,
        "purchase_id": receipt.purchase_id,
        "tank_id": receipt.tank_id,
        "received_liters": receipt.received_liters,
        "status": receipt.status,
        "movement_id": receipt.movement_id,
        "received_at": receipt.received_at,
    }


async def create_vehicle_refuel(
    db: AsyncSession,
    tenant_id: UUID,
    payload: VehicleRefuelCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    tank = await _require_tank(db, tenant_id, payload.tank_id)
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if (
        not vehicle
        or vehicle.tenant_id != tenant_id
        or vehicle.status not in {"active", "maintenance"}
    ):
        raise ApiError("vehicle_not_found", "Vehicle not found or inactive.", status_code=404)
    driver = await db.get(Driver, payload.driver_id)
    if not driver or driver.tenant_id != tenant_id or driver.status != "active":
        raise ApiError("driver_not_found", "Driver not found or inactive.", status_code=404)
    if payload.trip_id:
        trip = await db.get(Trip, payload.trip_id)
        if not trip or trip.tenant_id != tenant_id:
            raise ApiError("trip_not_found", "Trip not found.", status_code=404)
    else:
        trip = None
    if payload.odometer_reading < vehicle.current_km:
        raise ApiError("odometer_regression", "Refuel odometer cannot regress.", status_code=409)

    refuel = VehicleRefuel(tenant_id=tenant_id, **payload.model_dump())
    db.add(refuel)
    await db.flush()
    movement = await FuelMovementService.record(
        db,
        tenant_id,
        tank_id=tank.id,
        movement_type="vehicle_refuel",
        direction="out",
        liters=payload.liters,
        source_type="vehicle_refuel",
        source_id=refuel.id,
        occurred_at=payload.refueled_at,
        actor_id=actor_id,
        notes=payload.notes,
    )
    refuel.movement_id = movement.id
    refuel.unit_cost = movement.unit_cost
    refuel.total_cost = movement.total_cost
    if trip and refuel.total_cost is not None:
        trip.total_fuel_cost = _decimal(trip.total_fuel_cost) + _decimal(refuel.total_cost)
    vehicle.current_km = max(vehicle.current_km, payload.odometer_reading)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="vehicle_refuel.created",
        entity_type="vehicle_refuel",
        entity_id=refuel.id,
        new_values={"movement_id": str(movement.id), "liters": str(payload.liters)},
    )
    if not trip:
        await ensure_exception(
            db,
            tenant_id,
            entity_type="vehicle_refuel",
            entity_id=refuel.id,
            exception_type="vehicle_refuel_without_trip",
            severity="medium",
            title="Abastecimento sem viagem associada",
            message=(
                "O abastecimento interno deve ser revisto e associado "
                "a uma operação quando aplicável."
            ),
            actor_id=actor_id,
            context={"vehicle_id": str(vehicle.id), "liters": str(payload.liters)},
            source_type="vehicle_refuel",
            source_id=refuel.id,
        )
    await db.commit()
    await db.refresh(refuel)
    return {
        "id": refuel.id,
        "tank_id": refuel.tank_id,
        "vehicle_id": refuel.vehicle_id,
        "driver_id": refuel.driver_id,
        "trip_id": refuel.trip_id,
        "liters": refuel.liters,
        "odometer_reading": refuel.odometer_reading,
        "movement_id": refuel.movement_id,
        "refueled_at": refuel.refueled_at,
    }


async def create_stock_count(
    db: AsyncSession,
    tenant_id: UUID,
    payload: FuelStockCountCreate,
    *,
    actor_id: UUID | None,
) -> dict:
    tank = await _require_tank(db, tenant_id, payload.tank_id)
    measured = _decimal(payload.measured_liters)
    theoretical = _decimal(tank.current_stock_liters)
    if measured < 0 or measured > _decimal(tank.capacity_liters):
        raise ApiError(
            "invalid_stock_count",
            "Measured stock is outside tank capacity.",
            status_code=422,
        )
    count = FuelStockCount(
        tenant_id=tenant_id,
        theoretical_liters=theoretical,
        variance_liters=measured - theoretical,
        adjustment_status="not_required" if measured == theoretical else "pending",
        counted_by=actor_id,
        **payload.model_dump(),
    )
    db.add(count)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="fuel_stock_count.created",
        entity_type="fuel_tank",
        entity_id=tank.id,
        new_values={
            "stock_count_id": str(count.id),
            "theoretical_liters": str(theoretical),
            "measured_liters": str(measured),
            "variance_liters": str(count.variance_liters),
        },
    )
    tolerance = max(Decimal("20.00"), theoretical * Decimal("0.01"))
    if abs(_decimal(count.variance_liters)) > tolerance:
        await ensure_exception(
            db,
            tenant_id,
            entity_type="fuel_tank",
            entity_id=tank.id,
            exception_type="fuel_stock_variance",
            severity="high",
            title=f"Divergência de stock no tanque {tank.code}",
            message="A contagem física diverge do saldo teórico acima da tolerância.",
            actor_id=actor_id,
            context={
                "stock_count_id": str(count.id),
                "variance_liters": str(count.variance_liters),
                "tolerance_liters": str(tolerance),
            },
            source_type="fuel_stock_count",
            source_id=count.id,
        )
    await db.commit()
    await db.refresh(count)
    return _serialize_stock_count(count)


async def approve_stock_adjustment(
    db: AsyncSession,
    tenant_id: UUID,
    stock_count_id: UUID,
    *,
    actor_id: UUID | None,
    notes: str | None,
) -> dict:
    count = await db.scalar(
        select(FuelStockCount)
        .where(FuelStockCount.id == stock_count_id, FuelStockCount.tenant_id == tenant_id)
        .with_for_update()
    )
    if not count:
        raise ApiError("fuel_stock_count_not_found", "Fuel stock count not found.", status_code=404)
    if count.adjustment_status == "approved":
        return _serialize_stock_count(count)
    if count.adjustment_status != "pending":
        raise ApiError(
            "fuel_stock_adjustment_not_required",
            "Fuel stock count does not require an adjustment.",
            status_code=409,
        )
    if actor_id is not None and actor_id == count.counted_by:
        raise ApiError(
            "fuel_stock_adjustment_role_conflict",
            "Stock adjustment must be approved by a different user.",
            status_code=409,
        )

    variance = _decimal(count.variance_liters)
    movement = await FuelMovementService.record(
        db,
        tenant_id,
        tank_id=count.tank_id,
        movement_type="stock_adjustment",
        direction="in" if variance > 0 else "out",
        liters=abs(variance),
        source_type="fuel_stock_count",
        source_id=count.id,
        occurred_at=datetime.now(UTC),
        actor_id=actor_id,
        notes=notes or count.notes,
    )
    count.adjustment_status = "approved"
    count.adjustment_movement_id = movement.id
    count.adjustment_approved_by = actor_id
    count.adjustment_approved_at = datetime.now(UTC)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="fuel_stock_adjustment.approved",
        entity_type="fuel_stock_count",
        entity_id=count.id,
        old_values={"adjustment_status": "pending"},
        new_values={
            "adjustment_status": count.adjustment_status,
            "movement_id": str(movement.id),
            "variance_liters": str(variance),
        },
    )
    await db.commit()
    await db.refresh(count)
    return _serialize_stock_count(count)


def _serialize_stock_count(count: FuelStockCount) -> dict:
    return {
        "id": count.id,
        "tank_id": count.tank_id,
        "theoretical_liters": count.theoretical_liters,
        "measured_liters": count.measured_liters,
        "variance_liters": count.variance_liters,
        "adjustment_status": count.adjustment_status,
        "adjustment_movement_id": count.adjustment_movement_id,
        "adjustment_approved_by": count.adjustment_approved_by,
        "adjustment_approved_at": count.adjustment_approved_at,
        "counted_at": count.counted_at,
    }


async def list_movements(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    tank_id: UUID | None = None,
    limit: int = 100,
) -> list[dict]:
    query = select(FuelMovement).where(FuelMovement.tenant_id == tenant_id)
    if tank_id:
        query = query.where(FuelMovement.tank_id == tank_id)
    result = await db.execute(query.order_by(FuelMovement.occurred_at.desc()).limit(limit))
    return [serialize_movement(movement) for movement in result.scalars()]


async def get_fuel_control_board(db: AsyncSession, tenant_id: UUID) -> dict:
    tanks = await list_tanks(db, tenant_id)
    purchases_pending = int(
        (
            await db.scalar(
                select(func.count(FuelPurchase.id)).where(
                    FuelPurchase.tenant_id == tenant_id, FuelPurchase.status == "pending"
                )
            )
        )
        or 0
    )
    low_stock_tanks = [
        tank
        for tank in tanks
        if _decimal(tank["current_stock_liters"]) <= _decimal(tank["minimum_stock_liters"])
    ]
    stock_adjustments_pending = int(
        (
            await db.scalar(
                select(func.count(FuelStockCount.id)).where(
                    FuelStockCount.tenant_id == tenant_id,
                    FuelStockCount.adjustment_status == "pending",
                )
            )
        )
        or 0
    )
    return {
        "summary": {
            "tanks": len(tanks),
            "purchases_pending": purchases_pending,
            "low_stock_tanks": len(low_stock_tanks),
            "stock_adjustments_pending": stock_adjustments_pending,
            "total_stock_liters": sum(_decimal(tank["current_stock_liters"]) for tank in tanks),
        },
        "tanks": tanks,
        "queues": {"low_stock_tanks": low_stock_tanks},
    }


async def _require_tank(db: AsyncSession, tenant_id: UUID, tank_id: UUID) -> FuelTank:
    tank = await db.get(FuelTank, tank_id)
    if not tank or tank.tenant_id != tenant_id or tank.status != "active":
        raise ApiError("fuel_tank_not_found", "Active fuel tank not found.", status_code=404)
    return tank


async def _require_purchase(
    db: AsyncSession,
    tenant_id: UUID,
    purchase_id: UUID,
    *,
    for_update: bool = False,
) -> FuelPurchase:
    query = select(FuelPurchase).where(
        FuelPurchase.id == purchase_id,
        FuelPurchase.tenant_id == tenant_id,
    )
    if for_update:
        query = query.with_for_update()
    purchase = await db.scalar(query)
    if not purchase or purchase.tenant_id != tenant_id:
        raise ApiError("fuel_purchase_not_found", "Fuel purchase not found.", status_code=404)
    return purchase
