"""Analytics service — fleet KPI queries for RPT-01, RPT-02, and ANA-01."""

import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.cargo.models import DeliveryProof
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


# ── ANA-01: Extended dashboard KPI functions ──────────────────────────────────


async def get_route_profitability(
    db: AsyncSession,
    tenant_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> list[dict]:
    """ANA-01: Cost per route, ordered by avg_cost DESC. Only closed trips in period."""
    rows = (
        await db.execute(
            select(
                Trip.origin,
                Trip.destination,
                func.count(Trip.id).label("trip_count"),
                func.coalesce(func.avg(Trip.total_transport_cost), 0).label("avg_cost"),
            )
            .where(
                Trip.tenant_id == tenant_id,
                Trip.status == "closed",
                Trip.closed_at >= period_start,
                Trip.closed_at <= period_end,
            )
            .group_by(Trip.origin, Trip.destination)
            .order_by(func.avg(Trip.total_transport_cost).desc())
            .limit(10)
        )
    ).all()
    return [
        {
            "origin": r.origin,
            "destination": r.destination,
            "trip_count": r.trip_count,
            "avg_cost": float(r.avg_cost),
        }
        for r in rows
    ]


async def get_contract_margins(
    db: AsyncSession,
    tenant_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> list[dict]:
    """ANA-01: Gross margin per billing document. JOIN billing_items → trips on trip_id.

    Step 1: sum billing_items.amount per billing_document (revenue).
    Step 2: sum trips.total_transport_cost for those trips (cost).
    Composed in Python for clarity. Returns up to 20 rows.
    """
    # Revenue per billing_document_id
    rev_rows = (
        await db.execute(
            select(
                BillingItem.billing_document_id,
                func.sum(BillingItem.amount).label("total_revenue"),
            )
            .where(
                BillingItem.tenant_id == tenant_id,
                BillingItem.delivered_at >= period_start,
                BillingItem.delivered_at <= period_end,
            )
            .group_by(BillingItem.billing_document_id)
            .limit(20)
        )
    ).all()

    if not rev_rows:
        return []

    doc_ids = [r.billing_document_id for r in rev_rows]

    # Cost per billing_document_id (via billing_items → trips join)
    cost_rows = (
        await db.execute(
            select(
                BillingItem.billing_document_id,
                func.coalesce(func.sum(Trip.total_transport_cost), 0).label("total_cost"),
            )
            .join(Trip, BillingItem.trip_id == Trip.id)
            .where(
                BillingItem.billing_document_id.in_(doc_ids),
                BillingItem.tenant_id == tenant_id,
            )
            .group_by(BillingItem.billing_document_id)
        )
    ).all()

    cost_by_doc = {str(r.billing_document_id): float(r.total_cost) for r in cost_rows}

    # Fetch invoice numbers for the documents
    inv_rows = (
        await db.execute(
            select(BillingDocument.id, BillingDocument.invoice_number).where(
                BillingDocument.id.in_(doc_ids)
            )
        )
    ).all()
    invoice_by_doc = {str(r.id): r.invoice_number for r in inv_rows}

    result = []
    for r in rev_rows:
        doc_id = str(r.billing_document_id)
        total_revenue = float(r.total_revenue)
        total_cost = cost_by_doc.get(doc_id, 0.0)
        result.append(
            {
                "billing_document_id": doc_id,
                "invoice_number": invoice_by_doc.get(doc_id),
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "gross_margin": total_revenue - total_cost,
            }
        )
    return result


async def get_delivery_nps(
    db: AsyncSession,
    tenant_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> float:
    """ANA-01: Percentage of intact delivery proofs in period. Returns 0.0 if no proofs."""
    row = (
        await db.execute(
            select(
                func.sum(cast(DeliveryProof.cargo_condition == "intact", Integer)).label(
                    "intact_count"
                ),
                func.count(DeliveryProof.id).label("total"),
            ).where(
                DeliveryProof.tenant_id == tenant_id,
                DeliveryProof.delivered_at >= period_start,
                DeliveryProof.delivered_at <= period_end,
            )
        )
    ).one()

    total = row.total or 0
    if total == 0:
        return 0.0
    intact = row.intact_count or 0
    return round(intact * 100.0 / total, 2)


async def get_top_drivers_by_score(
    db: AsyncSession,
    tenant_id: UUID,
    period_start: datetime,
    period_end: datetime,
) -> list[dict]:
    """ANA-01: Top 5 drivers by trip_count DESC. Only closed trips in period."""
    rows = (
        await db.execute(
            select(
                Trip.driver_id,
                Driver.full_name.label("driver_name"),
                func.count(Trip.id).label("trip_count"),
                func.coalesce(func.sum(Trip.km_end - Trip.km_start), 0).label("total_km"),
            )
            .join(Driver, Trip.driver_id == Driver.id, isouter=True)
            .where(
                Trip.tenant_id == tenant_id,
                Trip.status == "closed",
                Trip.closed_at >= period_start,
                Trip.closed_at <= period_end,
            )
            .group_by(Trip.driver_id, Driver.full_name)
            .order_by(func.count(Trip.id).desc())
            .limit(5)
        )
    ).all()
    return [
        {
            "driver_id": str(r.driver_id),
            "driver_name": r.driver_name,
            "trip_count": r.trip_count,
            "total_km": float(r.total_km or 0),
        }
        for r in rows
    ]


async def get_analytics_dashboard(
    db: AsyncSession,
    tenant_id: UUID,
    period_start: datetime,
    period_end: datetime,
    redis=None,
) -> dict:
    """ANA-01: Compose all KPI blocks into a single dashboard payload with Redis cache (TTL 300s)."""
    cache_key = (
        f"analytics:dashboard:{tenant_id}:{period_start.isoformat()}:{period_end.isoformat()}"
    )
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            return json.loads(cached)

    base = await get_fleet_kpis(db, tenant_id, period_start, period_end)
    route_profitability = await get_route_profitability(db, tenant_id, period_start, period_end)
    contract_margins = await get_contract_margins(db, tenant_id, period_start, period_end)
    delivery_nps = await get_delivery_nps(db, tenant_id, period_start, period_end)
    top_drivers = await get_top_drivers_by_score(db, tenant_id, period_start, period_end)

    result = {
        **base,
        "route_profitability": route_profitability,
        "contract_margins": contract_margins,
        "delivery_nps": delivery_nps,
        "top_drivers": top_drivers,
    }

    if redis is not None:
        await redis.setex(cache_key, 300, json.dumps(result, default=str))

    return result
