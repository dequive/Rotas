import logging
from datetime import UTC, datetime
from uuid import UUID

from arq.connections import RedisSettings, create_pool
from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelLog
from app.modules.fuel.schemas import FuelLogCreate, FuelLogPatch, VerifyFuelLogRequest
from app.modules.vehicles.models import Vehicle

logger = logging.getLogger(__name__)

ANOMALY_FACTOR = 1.2


def serialize_fuel_log(log: FuelLog) -> dict:
    return {
        "id": log.id,
        "tenant_id": log.tenant_id,
        "vehicle_id": log.vehicle_id,
        "driver_id": log.driver_id,
        "fuel_date": log.fuel_date,
        "station_name": log.station_name,
        "station_location": log.station_location,
        "fuel_type": log.fuel_type,
        "liters": log.liters,
        "price_per_liter": log.price_per_liter,
        "total_cost": log.total_cost,
        "km_at_refuel": log.km_at_refuel,
        "km_since_last": log.km_since_last,
        "consumption_l_per_100km": log.consumption_l_per_100km,
        "receipt_file_id": log.receipt_file_id,
        "odometer_file_id": log.odometer_file_id,
        "payment_method": log.payment_method,
        "payment_reference": log.payment_reference,
        "is_verified": log.is_verified,
        "verified_by_user_id": log.verified_by_user_id,
        "verified_at": log.verified_at,
        "flagged": log.flagged,
        "client_captured_at": log.client_captured_at,
        "server_received_at": log.server_received_at,
        "created_at": log.created_at,
    }


async def _require_fuel_log(db: AsyncSession, tenant_id: UUID, fuel_log_id: UUID) -> FuelLog:
    log = await db.get(FuelLog, fuel_log_id)
    if not log or log.tenant_id != tenant_id:
        raise ApiError("fuel_log_not_found", "Fuel log not found.", status_code=404)
    return log


async def _previous_fuel_log(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
    fuel_date: datetime,
    km_at_refuel: int,
) -> FuelLog | None:
    return await db.scalar(
        select(FuelLog)
        .where(
            FuelLog.tenant_id == tenant_id,
            FuelLog.vehicle_id == vehicle_id,
            FuelLog.fuel_date < fuel_date,
            FuelLog.km_at_refuel < km_at_refuel,
        )
        .order_by(FuelLog.fuel_date.desc(), FuelLog.created_at.desc())
    )


async def _historical_consumption_average(
    db: AsyncSession,
    tenant_id: UUID,
    vehicle_id: UUID,
) -> float | None:
    value = await db.scalar(
        select(func.avg(FuelLog.consumption_l_per_100km)).where(
            FuelLog.tenant_id == tenant_id,
            FuelLog.vehicle_id == vehicle_id,
            FuelLog.consumption_l_per_100km.is_not(None),
        )
    )
    return float(value) if value is not None else None


def _calculate_consumption(liters: float, km_since_last: int | None) -> float | None:
    if not km_since_last or km_since_last <= 0:
        return None
    return round((liters / km_since_last) * 100, 2)


def _is_anomaly(
    consumption: float | None,
    historical_average: float | None,
    vehicle_target: float | None,
) -> bool:
    if consumption is None:
        return False
    if historical_average and consumption > historical_average * ANOMALY_FACTOR:
        return True
    if vehicle_target and consumption > vehicle_target * ANOMALY_FACTOR:
        return True
    return False


async def list_fuel_logs(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(FuelLog).where(FuelLog.tenant_id == tenant_id)
    if vehicle_id:
        query = query.where(FuelLog.vehicle_id == vehicle_id)
    if driver_id:
        query = query.where(FuelLog.driver_id == driver_id)
    if date_from:
        query = query.where(FuelLog.fuel_date >= date_from)
    if date_to:
        query = query.where(FuelLog.fuel_date < date_to)

    result = await db.execute(query.order_by(FuelLog.fuel_date.desc()).limit(limit).offset(offset))
    return [serialize_fuel_log(log) for log in result.scalars()]


async def create_fuel_log(
    db: AsyncSession,
    tenant_id: UUID,
    payload: FuelLogCreate,
    *,
    actor_id: UUID | None = None,
    driver_actor_id: UUID | None = None,
) -> dict:
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

    if payload.liters <= 0:
        raise ApiError(
            "invalid_fuel_liters",
            "Fuel liters must be greater than zero.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if payload.total_cost < 0:
        raise ApiError(
            "invalid_fuel_cost",
            "Fuel total cost cannot be negative.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if payload.km_at_refuel < vehicle.current_km:
        raise ApiError(
            "odometer_regression",
            "Fuel odometer cannot be lower than current vehicle km.",
            status_code=status.HTTP_409_CONFLICT,
            details={"current_km": vehicle.current_km, "km_at_refuel": payload.km_at_refuel},
        )

    previous = await _previous_fuel_log(
        db,
        tenant_id,
        payload.vehicle_id,
        payload.fuel_date,
        payload.km_at_refuel,
    )
    km_since_last = (
        payload.km_at_refuel - previous.km_at_refuel
        if previous and payload.km_at_refuel > previous.km_at_refuel
        else None
    )
    consumption = _calculate_consumption(payload.liters, km_since_last)
    historical_average = await _historical_consumption_average(db, tenant_id, payload.vehicle_id)
    flagged = _is_anomaly(
        consumption,
        historical_average,
        float(vehicle.avg_consumption_target) if vehicle.avg_consumption_target else None,
    )

    log = FuelLog(
        tenant_id=tenant_id,
        **payload.model_dump(),
        km_since_last=km_since_last,
        consumption_l_per_100km=consumption,
        flagged=flagged,
    )
    old_vehicle_values = {"current_km": vehicle.current_km}
    vehicle.current_km = max(vehicle.current_km, payload.km_at_refuel)

    db.add(log)
    await db.flush()
    await db.refresh(log)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        driver_id=driver_actor_id,
        action="fuel_log.created",
        entity_type="fuel_log",
        entity_id=log.id,
        new_values=serialize_fuel_log(log),
    )
    if old_vehicle_values["current_km"] != vehicle.current_km:
        await record_audit_log(
            db,
            tenant_id=tenant_id,
            user_id=actor_id,
            driver_id=driver_actor_id,
            action="vehicle.odometer_updated_from_fuel",
            entity_type="vehicle",
            entity_id=vehicle.id,
            old_values=old_vehicle_values,
            new_values={"current_km": vehicle.current_km, "fuel_log_id": log.id},
        )
        # D-01: enqueue immediate maintenance check when odometer advances
        try:
            _settings = get_settings()
            _redis = await create_pool(
                RedisSettings(host=_settings.redis_host, port=_settings.redis_port)
            )
            await _redis.enqueue_job(
                "check_vehicle_maintenance",
                vehicle_id=str(vehicle.id),
                tenant_id=str(tenant_id),
                current_km=vehicle.current_km,
            )
            await _redis.aclose()
        except Exception:
            logger.warning(
                "ARQ unavailable — maintenance trigger skipped for vehicle %s", vehicle.id
            )
    await db.commit()
    await db.refresh(log)
    return serialize_fuel_log(log)


async def get_fuel_stats(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    vehicle_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict:
    query = select(
        func.count(FuelLog.id),
        func.coalesce(func.sum(FuelLog.liters), 0),
        func.coalesce(func.sum(FuelLog.total_cost), 0),
        func.avg(FuelLog.consumption_l_per_100km),
        func.coalesce(func.sum(FuelLog.km_since_last), 0),
    ).where(FuelLog.tenant_id == tenant_id)
    if vehicle_id:
        query = query.where(FuelLog.vehicle_id == vehicle_id)
    if date_from:
        query = query.where(FuelLog.fuel_date >= date_from)
    if date_to:
        query = query.where(FuelLog.fuel_date < date_to)

    count, liters, total_cost, avg_consumption, total_km = (await db.execute(query)).one()
    cost_per_km = float(total_cost) / int(total_km) if total_km else None
    return {
        "count": count,
        "total_liters": liters,
        "total_cost": total_cost,
        "avg_consumption_l_per_100km": avg_consumption,
        "total_km": total_km,
        "cost_per_km": cost_per_km,
    }


async def list_anomalies(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    result = await db.execute(
        select(FuelLog)
        .where(FuelLog.tenant_id == tenant_id, FuelLog.flagged.is_(True))
        .order_by(FuelLog.fuel_date.desc())
        .limit(limit)
        .offset(offset)
    )
    return [serialize_fuel_log(log) for log in result.scalars()]


async def verify_fuel_log(
    db: AsyncSession,
    tenant_id: UUID,
    fuel_log_id: UUID,
    payload: VerifyFuelLogRequest,
    user_id: UUID | None = None,
) -> dict:
    log = await _require_fuel_log(db, tenant_id, fuel_log_id)
    if log.is_verified == payload.is_verified and (
        payload.flagged is None or log.flagged == payload.flagged
    ):
        return serialize_fuel_log(log)
    old_values = serialize_fuel_log(log)
    log.is_verified = payload.is_verified
    log.verified_by_user_id = user_id
    log.verified_at = datetime.now(UTC)
    if payload.flagged is not None:
        log.flagged = payload.flagged

    await db.flush()
    await db.refresh(log)
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="fuel_log.verified",
        entity_type="fuel_log",
        entity_id=log.id,
        old_values=old_values,
        new_values=serialize_fuel_log(log),
    )
    await db.commit()
    await db.refresh(log)
    return serialize_fuel_log(log)


async def patch_fuel_log(
    db: AsyncSession,
    tenant_id: UUID,
    fuel_log_id: UUID,
    patch: FuelLogPatch,
) -> dict:
    log = await _require_fuel_log(db, tenant_id, fuel_log_id)
    for field, value in patch.model_dump(exclude_none=True).items():
        setattr(log, field, value)
    await db.commit()
    await db.refresh(log)
    return serialize_fuel_log(log)
