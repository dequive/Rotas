import json
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alerts.models import Alert
from app.modules.availability.service import (
    driver_compliance_warnings,
    vehicle_compliance_warnings,
)
from app.modules.cargo.models import DeliveryProof
from app.modules.checklists.models import Checklist
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.models import OperationalException
from app.modules.operations.models import OperationalWaiver
from app.modules.tenants.models import Tenant
from app.modules.trip_orders.models import TripOrder
from app.modules.trips.models import DispatchClearance, Trip, TripCost, TripIncident
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.models import (
    MaintenanceSchedule,
    SparePartInventory,
    ToolCheckout,
    WorkOrder,
)

ACTIVE_WORK_ORDER_STATUSES = ("approved", "in_progress", "quality_check")
DEFAULT_DRIVER_DESPACHO_MIN_KM = 100

CT_KPI_TTL = 60  # seconds — CT-02
CT_ALERT_TTL = 30  # seconds — CT-02 (reserved for alert-specific caching)


async def get_ct_cached(
    db: AsyncSession,
    tenant_id: UUID,
    redis: Redis | None = None,
    *,
    target_date: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Cache-aside wrapper for get_control_tower (CT-02).

    Falls back to a direct DB call when redis is None (unavailable).
    Uses SET NX EX stampede lock to prevent duplicate recalculation
    under concurrent requests for the same tenant.
    """
    if redis is None:
        return await get_control_tower(
            db, tenant_id, target_date=target_date, page=page, page_size=page_size
        )

    date_key = target_date.isoformat() if target_date else "default"
    key = (
        f"tenant:{tenant_id}:control-tower:date={date_key}:"
        f"page={page}:page_size={page_size}"
    )
    lock_key = f"{key}:lock"

    # Cache hit — return without touching the DB
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)

    # Acquire stampede lock: atomic SET NX EX (prevents duplicate recalculation)
    acquired = await redis.set(lock_key, "1", nx=True, ex=10)
    if acquired:
        try:
            result = await get_control_tower(
                db, tenant_id, target_date=target_date, page=page, page_size=page_size
            )
            await redis.setex(key, CT_KPI_TTL, json.dumps(result, default=str))
            return result
        finally:
            await redis.delete(lock_key)
    else:
        # Another worker holds the lock — fall back to direct DB call (no cache write)
        return await get_control_tower(
            db, tenant_id, target_date=target_date, page=page, page_size=page_size
        )


def day_bounds(target_date: date | None) -> tuple[datetime, datetime]:
    selected = target_date or datetime.now(UTC).date()
    start = datetime.combine(selected, time.min, tzinfo=UTC)
    return start, start + timedelta(days=1)


async def get_control_tower(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    target_date: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    start, end = day_bounds(target_date)
    vehicle_document_expiry_queue = await _vehicle_document_expiry_queue(db, tenant_id)
    driver_document_expiry_queue = await _driver_document_expiry_queue(db, tenant_id)

    # Query 1: Trip-based aggregation counts (replaces ~8 individual _count() calls)
    trip_row = (
        await db.execute(
            select(
                func.count(Trip.id)
                .filter(Trip.status.in_(("dispatched", "in_progress", "delayed", "incident")))
                .label("trips_in_execution"),
                func.count(Trip.id)
                .filter(Trip.billing_status == "billable")
                .label("billing_ready"),
                func.count(Trip.id)
                .filter(
                    Trip.status == "closed",
                    Trip.costs_reconciled_at.is_(None),
                )
                .label("closed_unreconciled"),
                func.count(Trip.id)
                .filter(
                    Trip.created_at >= start,
                    Trip.created_at < end,
                )
                .label("trips_created_today"),
            ).where(Trip.tenant_id == tenant_id)
        )
    ).one()

    # Query 2: Dispatch clearance counts
    dispatch_row = (
        await db.execute(
            select(
                func.count(DispatchClearance.id)
                .filter(DispatchClearance.clearance_status == "pending")
                .label("dispatch_pending"),
                func.count(DispatchClearance.id)
                .filter(DispatchClearance.clearance_status == "blocked")
                .label("dispatch_blocked"),
            ).where(DispatchClearance.tenant_id == tenant_id)
        )
    ).one()

    # Query 3: Trip incident + delivery proof + billing counts
    incident_delivery_row = (
        await db.execute(
            select(
                func.count(TripIncident.id)
                .filter(TripIncident.status.in_(("open", "investigating")))
                .label("incidents_open"),
            ).where(TripIncident.tenant_id == tenant_id)
        )
    ).one()

    delivery_row = (
        await db.execute(
            select(
                func.count(DeliveryProof.id)
                .filter(DeliveryProof.status == "pending")
                .label("delivery_proofs_pending_validation"),
            ).where(DeliveryProof.tenant_id == tenant_id)
        )
    ).one()

    # Query 4: Other entity counts (TripOrder, Alert, OperationalException, OperationalWaiver,
    #           WorkOrder, SparePartInventory, ToolCheckout, MaintenanceSchedule, Vehicle, Driver)
    trip_order_row = (
        await db.execute(
            select(
                func.count(TripOrder.id)
                .filter(TripOrder.status.in_(("draft", "confirmed", "planning", "assigned")))
                .label("trip_orders_open"),
            ).where(TripOrder.tenant_id == tenant_id)
        )
    ).one()

    misc_row = (
        await db.execute(
            select(
                func.count(OperationalWaiver.id)
                .filter(OperationalWaiver.status == "active")
                .label("active_waivers"),
                func.count(OperationalException.id)
                .filter(OperationalException.status.in_(("open", "acknowledged")))
                .label("operational_exceptions_open"),
                func.count(Alert.id)
                .filter(Alert.status.in_(("pending", "sent", "read")))
                .label("alerts_active"),
            )
            .select_from(OperationalWaiver)
            .join(
                OperationalException,
                OperationalException.tenant_id == tenant_id,
                isouter=True,
            )
            .join(Alert, Alert.tenant_id == tenant_id, isouter=True)
            .where(OperationalWaiver.tenant_id == tenant_id)
            .group_by()
        )
    ).one_or_none()

    # Fallback: fetch individually if the cross-join approach fails (different table cardinalities)
    if misc_row is None:
        active_waivers = await _scalar_count(
            db,
            select(func.count(OperationalWaiver.id)).where(
                OperationalWaiver.tenant_id == tenant_id,
                OperationalWaiver.status == "active",
            ),
        )
        operational_exceptions_open = await _scalar_count(
            db,
            select(func.count(OperationalException.id)).where(
                OperationalException.tenant_id == tenant_id,
                OperationalException.status.in_(("open", "acknowledged")),
            ),
        )
        alerts_active = await _scalar_count(
            db,
            select(func.count(Alert.id)).where(
                Alert.tenant_id == tenant_id,
                Alert.status.in_(("pending", "sent", "read")),
            ),
        )
    else:
        active_waivers = misc_row.active_waivers
        operational_exceptions_open = misc_row.operational_exceptions_open
        alerts_active = misc_row.alerts_active

    # Query 5: Workshop/fleet counts
    workshop_row = (
        await db.execute(
            select(
                func.count(WorkOrder.id)
                .filter(WorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES))
                .label("work_orders_active"),
            ).where(WorkOrder.tenant_id == tenant_id)
        )
    ).one()

    fleet_row = (
        await db.execute(
            select(
                func.count(Vehicle.id).filter(Vehicle.status == "active").label("vehicles_active"),
                func.count(Driver.id).filter(Driver.status == "active").label("drivers_active"),
            )
            .select_from(Vehicle)
            .join(Driver, Driver.tenant_id == tenant_id, isouter=True)
            .where(Vehicle.tenant_id == tenant_id)
            .group_by()
        )
    ).one_or_none()

    if fleet_row is None:
        vehicles_active = await _scalar_count(
            db,
            select(func.count(Vehicle.id)).where(
                Vehicle.tenant_id == tenant_id, Vehicle.status == "active"
            ),
        )
        drivers_active = await _scalar_count(
            db,
            select(func.count(Driver.id)).where(
                Driver.tenant_id == tenant_id, Driver.status == "active"
            ),
        )
    else:
        vehicles_active = fleet_row.vehicles_active
        drivers_active = fleet_row.drivers_active

    # Query 6: Spare parts / tools / maintenance (workshop extras)
    # Uses independent scalar subqueries to avoid Cartesian-product errors from cross-joins.
    spare_parts_low_stock = await _scalar_count(
        db,
        select(func.count(SparePartInventory.id)).where(
            SparePartInventory.tenant_id == tenant_id,
            SparePartInventory.status == "active",
            SparePartInventory.current_quantity <= SparePartInventory.minimum_quantity,
        ),
    )
    tool_checkouts_overdue = await _scalar_count(
        db,
        select(func.count(ToolCheckout.id)).where(
            ToolCheckout.tenant_id == tenant_id,
            ToolCheckout.status == "checked_out",
            ToolCheckout.due_at.is_not(None),
            ToolCheckout.due_at < datetime.now(UTC),
        ),
    )
    maintenance_overdue = await _scalar_count(
        db,
        select(func.count(MaintenanceSchedule.id)).where(
            MaintenanceSchedule.tenant_id == tenant_id,
            MaintenanceSchedule.status == "overdue",
        ),
    )

    financial = await _financial_summary(db, tenant_id)

    summary = {
        "trip_orders_open": trip_order_row.trip_orders_open,
        "dispatch_pending": dispatch_row.dispatch_pending,
        "dispatch_blocked": dispatch_row.dispatch_blocked,
        "trips_in_execution": trip_row.trips_in_execution,
        "incidents_open": incident_delivery_row.incidents_open,
        "delivery_proofs_pending_validation": delivery_row.delivery_proofs_pending_validation,
        "billing_ready": trip_row.billing_ready,
        "active_waivers": active_waivers,
        "operational_exceptions_open": operational_exceptions_open,
        "alerts_active": alerts_active,
        "work_orders_active": workshop_row.work_orders_active,
        "spare_parts_low_stock": spare_parts_low_stock,
        "tool_checkouts_overdue": tool_checkouts_overdue,
        "maintenance_overdue": maintenance_overdue,
        "vehicles_active": vehicles_active,
        "drivers_active": drivers_active,
        "trips_created_today": trip_row.trips_created_today,
        "vehicle_documents_expiring": len(vehicle_document_expiry_queue),
        "driver_documents_expiring": len(driver_document_expiry_queue),
        **financial,
    }

    return {
        "date": start.date().isoformat(),
        "summary": summary,
        "queues": {
            "pending_dispatch": await _pending_dispatch_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "blocked_dispatch": await _blocked_dispatch_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "open_incidents": await _open_incidents_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "delayed_trips": await _delayed_trips_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "pending_delivery_validation": await _pending_delivery_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "operational_exceptions": await _operational_exception_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "alerts": await _alerts_queue(db, tenant_id, page=page, page_size=page_size),
            "active_work_orders": await _active_work_orders_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "negative_margin_trips": await _negative_margin_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "driver_despacho_pending": await _driver_despacho_pending_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "failed_checklists": await _failed_checklists_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "disputed_delivery_proofs": await _disputed_delivery_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "operational_close_candidates": await _operational_close_queue(
                db, tenant_id, page=page, page_size=page_size
            ),
            "vehicle_documents_expiring": vehicle_document_expiry_queue,
            "driver_documents_expiring": driver_document_expiry_queue,
        },
    }


async def _scalar_count(db: AsyncSession, query) -> int:
    """Single-column scalar count — used only as fallback for cross-join edge cases."""
    return int((await db.scalar(query)) or 0)


def _as_float(value) -> float:
    return float(value or 0)


async def _financial_summary(db: AsyncSession, tenant_id: UUID) -> dict:
    reconciled_count, cost_total, revenue_total, margin_total = (
        await db.execute(
            select(
                func.count(Trip.id),
                func.coalesce(func.sum(Trip.total_transport_cost), 0),
                func.coalesce(func.sum(Trip.actual_revenue), 0),
                func.coalesce(func.sum(Trip.actual_margin), 0),
            ).where(
                Trip.tenant_id == tenant_id,
                Trip.costs_reconciled_at.is_not(None),
            )
        )
    ).one()
    negative_margin_count = await _scalar_count(
        db,
        select(func.count(Trip.id)).where(
            Trip.tenant_id == tenant_id,
            Trip.costs_reconciled_at.is_not(None),
            Trip.actual_margin < 0,
        ),
    )
    unreconciled_closed_count = await _scalar_count(
        db,
        select(func.count(Trip.id)).where(
            Trip.tenant_id == tenant_id,
            Trip.status == "closed",
            Trip.costs_reconciled_at.is_(None),
        ),
    )
    return {
        "costs_reconciled_trips": int(reconciled_count or 0),
        "transport_cost_total": _as_float(cost_total),
        "contract_revenue_total": _as_float(revenue_total),
        "margin_total": _as_float(margin_total),
        "negative_margin_trips": negative_margin_count,
        "closed_trips_unreconciled": unreconciled_closed_count,
    }


async def _pending_dispatch_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(DispatchClearance, Trip)
        .join(Trip, Trip.id == DispatchClearance.trip_id)
        .where(
            DispatchClearance.tenant_id == tenant_id,
            DispatchClearance.clearance_status.in_(("pending", "approved")),
            Trip.status == "dispatch_pending",
        )
        .order_by(DispatchClearance.updated_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "clearance_id": clearance.id,
            "trip_id": trip.id,
            "origin": trip.origin,
            "destination": trip.destination,
            "clearance_status": clearance.clearance_status,
            "updated_at": clearance.updated_at,
        }
        for clearance, trip in rows
    ]


async def _blocked_dispatch_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(DispatchClearance, Trip)
        .join(Trip, Trip.id == DispatchClearance.trip_id)
        .where(
            DispatchClearance.tenant_id == tenant_id,
            DispatchClearance.clearance_status == "blocked",
        )
        .order_by(DispatchClearance.updated_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "clearance_id": clearance.id,
            "trip_id": trip.id,
            "origin": trip.origin,
            "destination": trip.destination,
            "blocked_reason": clearance.blocked_reason,
            "updated_at": clearance.updated_at,
        }
        for clearance, trip in rows
    ]


async def _open_incidents_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(TripIncident, Trip)
        .join(Trip, Trip.id == TripIncident.trip_id)
        .where(
            TripIncident.tenant_id == tenant_id,
            TripIncident.status.in_(("open", "investigating")),
        )
        .order_by(TripIncident.occurred_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "incident_id": incident.id,
            "trip_id": trip.id,
            "origin": trip.origin,
            "destination": trip.destination,
            "incident_type": incident.incident_type,
            "severity": incident.severity,
            "description": incident.description,
            "occurred_at": incident.occurred_at,
        }
        for incident, trip in rows
    ]


async def _delayed_trips_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    current_time = datetime.now(UTC)
    rows = await db.execute(
        select(Trip, Vehicle, Driver)
        .join(Vehicle, Vehicle.id == Trip.vehicle_id, isouter=True)
        .join(Driver, Driver.id == Trip.driver_id, isouter=True)
        .where(
            Trip.tenant_id == tenant_id,
            Trip.status.in_(("dispatched", "in_progress", "delayed")),
            Trip.planned_arrival.is_not(None),
            Trip.actual_arrival.is_(None),
            Trip.planned_arrival < current_time,
        )
        .order_by(Trip.planned_arrival.asc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "trip_id": trip.id,
            "origin": trip.origin,
            "destination": trip.destination,
            "status": trip.status,
            "vehicle_plate": vehicle.plate if vehicle else None,
            "driver_name": driver.full_name if driver else None,
            "planned_arrival": trip.planned_arrival,
            "delay_minutes": int((current_time - trip.planned_arrival).total_seconds() // 60),
        }
        for trip, vehicle, driver in rows
    ]


async def _pending_delivery_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(DeliveryProof, Trip)
        .join(Trip, Trip.id == DeliveryProof.trip_id)
        .where(
            DeliveryProof.tenant_id == tenant_id,
            DeliveryProof.status == "pending",
        )
        .order_by(DeliveryProof.delivered_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "delivery_proof_id": proof.id,
            "trip_id": trip.id,
            "origin": trip.origin,
            "destination": trip.destination,
            "document_number": proof.document_number,
            "delivered_at": proof.delivered_at,
        }
        for proof, trip in rows
    ]


async def _operational_exception_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(OperationalException)
        .where(
            OperationalException.tenant_id == tenant_id,
            OperationalException.status.in_(("open", "acknowledged")),
        )
        .order_by(OperationalException.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "exception_id": item.id,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "exception_type": item.exception_type,
            "severity": item.severity,
            "status": item.status,
            "title": item.title,
            "message": item.message,
            "created_at": item.created_at,
        }
        for item in rows.scalars()
    ]


async def _active_work_orders_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(WorkOrder, Vehicle)
        .join(Vehicle, Vehicle.id == WorkOrder.vehicle_id)
        .where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.status.in_(ACTIVE_WORK_ORDER_STATUSES),
        )
        .order_by(WorkOrder.updated_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "work_order_id": item.id,
            "work_order_number": item.work_order_number,
            "vehicle_id": vehicle.id,
            "vehicle_plate": vehicle.plate,
            "status": item.status,
            "planned_work": item.planned_work,
            "updated_at": item.updated_at,
        }
        for item, vehicle in rows
    ]


async def _alerts_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Alert)
        .where(
            Alert.tenant_id == tenant_id,
            Alert.status.in_(("pending", "sent", "read")),
        )
        .order_by(Alert.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "alert_id": item.id,
            "alert_type": item.alert_type,
            "priority": item.priority,
            "entity_type": item.entity_type,
            "entity_id": item.entity_id,
            "title": item.title,
            "message": item.message,
            "status": item.status,
            "created_at": item.created_at,
        }
        for item in rows.scalars()
    ]


async def _negative_margin_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Trip, Vehicle, Driver)
        .join(Vehicle, Vehicle.id == Trip.vehicle_id, isouter=True)
        .join(Driver, Driver.id == Trip.driver_id, isouter=True)
        .where(
            Trip.tenant_id == tenant_id,
            Trip.costs_reconciled_at.is_not(None),
            Trip.actual_margin < 0,
        )
        .order_by(Trip.actual_margin.asc(), Trip.costs_reconciled_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "trip_id": trip.id,
            "vehicle_plate": vehicle.plate if vehicle else None,
            "driver_name": driver.full_name if driver else None,
            "origin": trip.origin,
            "destination": trip.destination,
            "transport_cost": _as_float(trip.total_transport_cost),
            "revenue": _as_float(trip.actual_revenue),
            "margin": _as_float(trip.actual_margin),
            "costs_reconciled_at": trip.costs_reconciled_at,
        }
        for trip, vehicle, driver in rows
    ]


async def _driver_despacho_pending_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    min_distance_km = await _driver_despacho_min_distance(db, tenant_id)
    # Fetch extra rows to account for distance filtering; cap at page_size after filter
    fetch_limit = page_size * 3
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Trip, Vehicle, Driver, TripOrder)
        .join(Vehicle, Vehicle.id == Trip.vehicle_id, isouter=True)
        .join(Driver, Driver.id == Trip.driver_id, isouter=True)
        .join(TripOrder, TripOrder.id == Trip.trip_order_id, isouter=True)
        .join(
            TripCost,
            (TripCost.trip_id == Trip.id)
            & (TripCost.tenant_id == tenant_id)
            & (TripCost.cost_type == "driver_despacho"),
            isouter=True,
        )
        .where(
            Trip.tenant_id == tenant_id,
            TripCost.id.is_(None),
            Trip.status.in_(
                (
                    "planned",
                    "dispatched",
                    "in_progress",
                    "delayed",
                    "incident",
                    "delivered",
                    "closed",
                )
            ),
        )
        .order_by(Trip.created_at.desc())
        .limit(fetch_limit)
        .offset(offset)
    )
    candidates = []
    for trip, vehicle, driver, order in rows:
        distance_km = _trip_distance_for_despacho(trip, order)
        if distance_km is None or distance_km < min_distance_km:
            continue
        candidates.append(
            {
                "trip_id": trip.id,
                "origin": trip.origin,
                "destination": trip.destination,
                "status": trip.status,
                "vehicle_plate": vehicle.plate if vehicle else None,
                "driver_name": driver.full_name if driver else None,
                "distance_km": distance_km,
                "min_long_course_km": min_distance_km,
                "created_at": trip.created_at,
            }
        )
        if len(candidates) >= page_size:
            break
    return candidates


async def _driver_despacho_min_distance(db: AsyncSession, tenant_id: UUID) -> float:
    tenant = await db.get(Tenant, tenant_id)
    policy = tenant.compliance_policy if tenant and tenant.compliance_policy else {}
    allowance_policy = policy.get("driver_travel_allowance_policy")
    if not isinstance(allowance_policy, dict):
        return DEFAULT_DRIVER_DESPACHO_MIN_KM
    value = allowance_policy.get("min_long_course_km", DEFAULT_DRIVER_DESPACHO_MIN_KM)
    try:
        return float(value)
    except (TypeError, ValueError):
        return DEFAULT_DRIVER_DESPACHO_MIN_KM


def _trip_distance_for_despacho(trip: Trip, order: TripOrder | None) -> float | None:
    if order and order.estimated_distance_km is not None:
        return _as_float(order.estimated_distance_km)
    if trip.km_start is not None and trip.km_end is not None and trip.km_end >= trip.km_start:
        return float(trip.km_end - trip.km_start)
    return None


async def _failed_checklists_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(Checklist, Vehicle, Driver)
        .join(Vehicle, Vehicle.id == Checklist.vehicle_id, isouter=True)
        .join(Driver, Driver.id == Checklist.driver_id, isouter=True)
        .where(Checklist.tenant_id == tenant_id, Checklist.status == "failed")
        .order_by(Checklist.completed_at.desc(), Checklist.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "checklist_id": checklist.id,
            "vehicle_id": checklist.vehicle_id,
            "vehicle_plate": vehicle.plate if vehicle else None,
            "driver_id": checklist.driver_id,
            "driver_name": driver.full_name if driver else None,
            "type": checklist.type,
            "completed_at": checklist.completed_at,
        }
        for checklist, vehicle, driver in rows
    ]


async def _disputed_delivery_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(DeliveryProof, Trip)
        .join(Trip, Trip.id == DeliveryProof.trip_id)
        .where(DeliveryProof.tenant_id == tenant_id, DeliveryProof.status == "disputed")
        .order_by(DeliveryProof.updated_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    return [
        {
            "delivery_proof_id": proof.id,
            "trip_id": trip.id,
            "origin": trip.origin,
            "destination": trip.destination,
            "document_number": proof.document_number,
            "delivered_at": proof.delivered_at,
            "billing_status": trip.billing_status,
        }
        for proof, trip in rows
    ]


async def _operational_close_queue(
    db: AsyncSession, tenant_id: UUID, *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = (
        await db.execute(
            select(Trip, Vehicle, Driver)
            .join(Vehicle, Vehicle.id == Trip.vehicle_id, isouter=True)
            .join(Driver, Driver.id == Trip.driver_id, isouter=True)
            .where(
                Trip.tenant_id == tenant_id,
                Trip.status.in_(("arrived", "delivered", "incident")),
            )
            .order_by(Trip.updated_at.desc(), Trip.created_at.desc())
            .limit(page_size)
            .offset(offset)
        )
    ).all()

    if not rows:
        return []

    trip_ids = [trip.id for trip, _, _ in rows]

    # Batch load delivery proofs — single IN query instead of N per-row queries
    proofs_by_trip: dict = {}
    proof_rows = (
        (
            await db.execute(
                select(DeliveryProof)
                .where(
                    DeliveryProof.tenant_id == tenant_id,
                    DeliveryProof.trip_id.in_(trip_ids),
                )
                .order_by(DeliveryProof.delivered_at.desc(), DeliveryProof.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    for proof in proof_rows:
        if proof.trip_id not in proofs_by_trip:
            proofs_by_trip[proof.trip_id] = proof

    # Batch load blocking incidents — single IN query
    incidents_by_trip: dict = {}
    incident_rows = (
        await db.execute(
            select(TripIncident.id, TripIncident.trip_id).where(
                TripIncident.tenant_id == tenant_id,
                TripIncident.trip_id.in_(trip_ids),
                TripIncident.status.in_(("open", "investigating")),
                TripIncident.severity.in_(("high", "critical")),
            )
        )
    ).all()
    for inc_id, trip_id in incident_rows:
        incidents_by_trip[trip_id] = inc_id

    # Assemble result — O(N) dict lookups, no additional DB calls
    result = []
    for trip, vehicle, driver in rows:
        proof = proofs_by_trip.get(trip.id)
        blocking_incident_id = incidents_by_trip.get(trip.id)
        if blocking_incident_id:
            readiness = "blocked_incident"
        elif proof and proof.status == "validated":
            readiness = "ready"
        else:
            readiness = "needs_validated_pod_or_waiver"

        result.append(
            {
                "trip_id": trip.id,
                "origin": trip.origin,
                "destination": trip.destination,
                "status": trip.status,
                "vehicle_plate": vehicle.plate if vehicle else None,
                "driver_name": driver.full_name if driver else None,
                "latest_delivery_proof_id": proof.id if proof else None,
                "latest_delivery_proof_status": proof.status if proof else None,
                "latest_delivery_proof_number": proof.document_number if proof else None,
                "has_blocking_incident": bool(blocking_incident_id),
                "readiness": readiness,
                "updated_at": trip.updated_at,
            }
        )
    return result


async def _vehicle_document_expiry_queue(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    tenant = await db.get(Tenant, tenant_id)
    policy = tenant.compliance_policy if tenant and tenant.compliance_policy else {}
    result = await db.execute(
        select(Vehicle).where(Vehicle.tenant_id == tenant_id, Vehicle.status == "active")
    )
    rows = []
    for vehicle in result.scalars():
        for warning in vehicle_compliance_warnings(vehicle, policy=policy):
            rows.append(
                {
                    "vehicle_id": vehicle.id,
                    "vehicle_plate": vehicle.plate,
                    **warning,
                }
            )
    return sorted(rows, key=lambda item: item["days_until_expiry"])[:10]


async def _driver_document_expiry_queue(db: AsyncSession, tenant_id: UUID) -> list[dict]:
    tenant = await db.get(Tenant, tenant_id)
    policy = tenant.compliance_policy if tenant and tenant.compliance_policy else {}
    result = await db.execute(
        select(Driver).where(Driver.tenant_id == tenant_id, Driver.status == "active")
    )
    rows = []
    for driver in result.scalars():
        for warning in driver_compliance_warnings(driver, policy=policy):
            rows.append(
                {
                    "driver_id": driver.id,
                    "driver_name": driver.full_name,
                    **warning,
                }
            )
    return sorted(rows, key=lambda item: item["days_until_expiry"])[:10]
