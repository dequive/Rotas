"""Analytics service — fleet KPI queries for RPT-01, RPT-02, and ANA-01."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelLog
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle


async def get_fleet_kpis(
    db: AsyncSession,
    tenant_id: UUID,
    period_start: datetime,
    period_end: datetime,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
) -> dict:
    """RPT-01: Fleet KPI aggregations. All queries filtered by tenant_id."""

    # Base filter for trips in period (closed trips only)
    trip_filters = [
        Trip.tenant_id == tenant_id,
        Trip.closed_at >= period_start,
        Trip.closed_at <= period_end,
        Trip.status == "closed",
    ]
    if vehicle_id:
        trip_filters.append(Trip.vehicle_id == vehicle_id)
    if driver_id:
        trip_filters.append(Trip.driver_id == driver_id)

    # Query 1: Cost-per-km per vehicle
    # distance_km = km_end - km_start (no dedicated distance_km column)
    vehicle_kpi_rows = (
        await db.execute(
            select(
                Trip.vehicle_id,
                func.count(Trip.id).label("trip_count"),
                func.coalesce(func.sum(Trip.km_end - Trip.km_start), 0).label("total_km"),
                func.coalesce(func.sum(Trip.total_transport_cost), 0).label("total_cost"),
            )
            .where(*trip_filters)
            .group_by(Trip.vehicle_id)
        )
    ).all()

    # Compute cost_per_km per vehicle
    cost_per_km = []
    for row in vehicle_kpi_rows:
        km = float(row.total_km or 0)
        cost = float(row.total_cost or 0)
        cost_per_km.append(
            {
                "vehicle_id": str(row.vehicle_id),
                "total_km": km,
                "total_cost": cost,
                "cost_per_km": round(cost / km, 2) if km > 0 else None,
            }
        )

    # Query 2: Fleet utilization = active trips / total active vehicles
    active_trips = (
        await db.scalar(
            select(func.count(Trip.id)).where(
                Trip.tenant_id == tenant_id,
                Trip.status.in_(("dispatched", "in_progress", "delayed", "incident")),
            )
        )
    ) or 0
    total_vehicles = (
        await db.scalar(
            select(func.count(Vehicle.id)).where(
                Vehicle.tenant_id == tenant_id, Vehicle.status == "active"
            )
        )
    ) or 1  # avoid division by zero
    fleet_utilization = round((active_trips / total_vehicles) * 100, 1)

    # Query 3: L/100km — fuel consumption over the requested period
    # FuelLog.fuel_date is the correct field for date filtering
    fuel_filters = [
        FuelLog.tenant_id == tenant_id,
        FuelLog.fuel_date >= period_start,
        FuelLog.fuel_date <= period_end,
    ]
    if vehicle_id:
        fuel_filters.append(FuelLog.vehicle_id == vehicle_id)

    fuel_row = (
        await db.execute(
            select(
                func.coalesce(func.sum(FuelLog.liters), 0).label("total_liters"),
            ).where(*fuel_filters)
        )
    ).one()

    # Total km from closed trips in same period
    period_km_row = (
        await db.execute(
            select(func.coalesce(func.sum(Trip.km_end - Trip.km_start), 0).label("total_km")).where(
                *trip_filters
            )
        )
    ).one()

    total_liters = float(fuel_row.total_liters or 0)
    total_km_period = float(period_km_row.total_km or 0)
    l_per_100km = round((total_liters / total_km_period) * 100, 2) if total_km_period > 0 else None

    # Query 4: Driver summary
    driver_rows = (
        await db.execute(
            select(
                Trip.driver_id,
                func.count(Trip.id).label("trip_count"),
                func.coalesce(func.sum(Trip.km_end - Trip.km_start), 0).label("total_km"),
                func.coalesce(func.sum(Trip.total_transport_cost), 0).label("total_cost"),
            )
            .where(*trip_filters)
            .group_by(Trip.driver_id)
            .limit(50)
        )
    ).all()

    driver_summary = [
        {
            "driver_id": str(row.driver_id),
            "trip_count": row.trip_count,
            "total_km": float(row.total_km or 0),
            "total_cost": float(row.total_cost or 0),
        }
        for row in driver_rows
    ]

    # Query 5: Total completed trips in period
    trips_completed = (await db.scalar(select(func.count(Trip.id)).where(*trip_filters))) or 0

    return {
        "cost_per_km": cost_per_km,
        "fleet_utilization": fleet_utilization,
        "l_per_100km": l_per_100km,
        "trips_completed": trips_completed,
        "driver_summary": driver_summary,
    }


def _severity(days_remaining: int) -> str:
    """Classify document expiry severity by days remaining."""
    if days_remaining <= 7:
        return "critical"
    if days_remaining <= 15:
        return "urgent"
    return "warning"


async def get_document_expiry_alerts(
    db: AsyncSession,
    tenant_id: UUID,
    horizon_days: int = 30,
) -> list[dict]:
    """RPT-02: Vehicles and drivers with compliance documents expiring within horizon_days.
    All queries filtered by tenant_id.
    """
    from app.modules.availability.service import (
        driver_compliance_warnings,
        vehicle_compliance_warnings,
    )

    today = datetime.now(UTC).date()
    alerts: list[dict] = []

    # Vehicles — filter by tenant_id (multitenant safety)
    vehicles = (
        (
            await db.execute(
                select(Vehicle)
                .where(Vehicle.tenant_id == tenant_id, Vehicle.status == "active")
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    for vehicle in vehicles:
        # vehicle_compliance_warnings is sync — no await
        warnings = vehicle_compliance_warnings(vehicle)
        for w in warnings:
            # availability service returns: valid_until (isoformat str), days_until_expiry
            valid_until_str = w.get("valid_until")
            if valid_until_str is None:
                continue
            from datetime import date

            if isinstance(valid_until_str, str):
                exp_date = date.fromisoformat(valid_until_str)
            elif isinstance(valid_until_str, date):
                exp_date = valid_until_str
            else:
                continue
            days_remaining = (exp_date - today).days
            if days_remaining <= horizon_days:
                alerts.append(
                    {
                        "entity_type": "vehicle",
                        "entity_id": str(vehicle.id),
                        "entity_name": vehicle.plate,
                        "document_type": w.get("document_type"),
                        "expires_at": exp_date.isoformat(),
                        "days_remaining": days_remaining,
                        "severity": _severity(days_remaining),
                    }
                )

    # Drivers — filter by tenant_id (multitenant safety)
    drivers = (
        (
            await db.execute(
                select(Driver)
                .where(Driver.tenant_id == tenant_id, Driver.status == "active")
                .limit(200)
            )
        )
        .scalars()
        .all()
    )

    for driver in drivers:
        # driver_compliance_warnings is sync — no await
        warnings = driver_compliance_warnings(driver)
        for w in warnings:
            valid_until_str = w.get("valid_until")
            if valid_until_str is None:
                continue
            from datetime import date

            if isinstance(valid_until_str, str):
                exp_date = date.fromisoformat(valid_until_str)
            elif isinstance(valid_until_str, date):
                exp_date = valid_until_str
            else:
                continue
            days_remaining = (exp_date - today).days
            if days_remaining <= horizon_days:
                alerts.append(
                    {
                        "entity_type": "driver",
                        "entity_id": str(driver.id),
                        "entity_name": driver.full_name,
                        "document_type": w.get("document_type"),
                        "expires_at": exp_date.isoformat(),
                        "days_remaining": days_remaining,
                        "severity": _severity(days_remaining),
                    }
                )

    # Sort by days_remaining ascending (most urgent first)
    alerts.sort(key=lambda a: a["days_remaining"])
    return alerts
