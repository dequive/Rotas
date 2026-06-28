from datetime import UTC, datetime
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.availability.service import require_vehicle_and_driver_available
from app.modules.contracts.models import Contract
from app.modules.trip_orders.models import TripOrder
from app.modules.trip_orders.schemas import (
    TripOrderAssignRequest,
    TripOrderCancelRequest,
    TripOrderConfirmRequest,
    TripOrderCreate,
)
from app.modules.trips.models import Trip
from app.modules.trips.service import serialize_trip
from app.modules.vehicles.models import Vehicle

ALLOWED_CREATE_VALUES = {
    "priority": {"low", "normal", "high", "urgent"},
    "source": {"manual", "contract_schedule", "client_request"},
    "cargo_risk_level": {"low", "normal", "high", "critical"},
}


def now_utc() -> datetime:
    return datetime.now(UTC)


def serialize_trip_order(order: TripOrder) -> dict:
    return {
        "id": order.id,
        "tenant_id": order.tenant_id,
        "contract_id": order.contract_id,
        "client_id": order.client_id,
        "customer_reference": order.customer_reference,
        "origin": order.origin,
        "destination": order.destination,
        "cargo_type": order.cargo_type,
        "cargo_description": order.cargo_description,
        "estimated_weight": order.estimated_weight,
        "estimated_volume": order.estimated_volume,
        "cargo_value": order.cargo_value,
        "cargo_risk_level": order.cargo_risk_level,
        "requested_pickup_date": order.requested_pickup_date,
        "requested_delivery_date": order.requested_delivery_date,
        "sla_pickup_deadline": order.sla_pickup_deadline,
        "sla_delivery_deadline": order.sla_delivery_deadline,
        "assigned_vehicle_id": order.assigned_vehicle_id,
        "assigned_driver_id": order.assigned_driver_id,
        "assigned_at": order.assigned_at,
        "assigned_by": order.assigned_by,
        "status": order.status,
        "priority": order.priority,
        "estimated_distance_km": order.estimated_distance_km,
        "estimated_fuel_cost": order.estimated_fuel_cost,
        "estimated_toll_cost": order.estimated_toll_cost,
        "estimated_revenue": order.estimated_revenue,
        "source": order.source,
        "load_permit_id": order.load_permit_id,
        "requires_load_permit": order.requires_load_permit,
        "requires_police_clearance": order.requires_police_clearance,
        "requires_customs_clearance": order.requires_customs_clearance,
        "operational_notes": order.operational_notes,
        "commercial_notes": order.commercial_notes,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


async def _require_order(db: AsyncSession, tenant_id: UUID, order_id: UUID) -> TripOrder:
    order = await db.get(TripOrder, order_id)
    if not order or order.tenant_id != tenant_id:
        raise ApiError(
            "trip_order_not_found",
            "Trip order not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return order


def _validate_enum(field: str, value: str) -> None:
    allowed = ALLOWED_CREATE_VALUES[field]
    if value not in allowed:
        raise ApiError(
            "invalid_trip_order_value",
            f"Invalid value for {field}.",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details={"field": field, "allowed": sorted(allowed), "value": value},
        )


async def list_trip_orders(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(TripOrder).where(TripOrder.tenant_id == tenant_id)
    if status_filter:
        query = query.where(TripOrder.status == status_filter)
    if vehicle_id:
        query = query.where(TripOrder.assigned_vehicle_id == vehicle_id)
    if driver_id:
        query = query.where(TripOrder.assigned_driver_id == driver_id)

    result = await db.execute(
        query.order_by(TripOrder.created_at.desc()).limit(limit).offset(offset)
    )
    return [serialize_trip_order(order) for order in result.scalars()]


async def create_trip_order(
    db: AsyncSession,
    tenant_id: UUID,
    payload: TripOrderCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    _validate_enum("priority", payload.priority)
    _validate_enum("source", payload.source)
    _validate_enum("cargo_risk_level", payload.cargo_risk_level)

    if payload.contract_id:
        contract = await db.get(Contract, payload.contract_id)
        if not contract or contract.tenant_id != tenant_id:
            raise ApiError("contract_not_found", "Contract not found.", status_code=404)

    order = TripOrder(tenant_id=tenant_id, **payload.model_dump())
    db.add(order)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip_order.created",
        entity_type="trip_order",
        entity_id=order.id,
        new_values={
            "status": order.status,
            "origin": order.origin,
            "destination": order.destination,
        },
    )
    await db.commit()
    await db.refresh(order)
    return serialize_trip_order(order)


async def get_trip_order(db: AsyncSession, tenant_id: UUID, order_id: UUID) -> dict:
    order = await _require_order(db, tenant_id, order_id)
    return serialize_trip_order(order)


async def confirm_trip_order(
    db: AsyncSession,
    tenant_id: UUID,
    order_id: UUID,
    payload: TripOrderConfirmRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    order = await _require_order(db, tenant_id, order_id)
    if order.status == "confirmed":
        return serialize_trip_order(order)
    if order.status != "draft":
        raise ApiError(
            "invalid_trip_order_status",
            "Only draft trip orders can be confirmed.",
            status_code=409,
            details={"status": order.status},
        )
    old_values = {"status": order.status}
    order.status = "confirmed"
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip_order.confirmed",
        entity_type="trip_order",
        entity_id=order.id,
        old_values=old_values,
        new_values={"status": order.status, "reason": payload.reason},
    )
    await db.commit()
    await db.refresh(order)
    return serialize_trip_order(order)


async def assign_trip_order(
    db: AsyncSession,
    tenant_id: UUID,
    order_id: UUID,
    payload: TripOrderAssignRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    result = await db.execute(
        select(TripOrder)
        .where(TripOrder.id == order_id, TripOrder.tenant_id == tenant_id)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if not order:
        raise ApiError("trip_order_not_found", "Trip order not found.", status_code=404)
    if order.status not in {"confirmed", "planning"}:
        raise ApiError(
            "invalid_trip_order_status",
            "Only confirmed or planning trip orders can be assigned.",
            status_code=409,
            details={"status": order.status},
        )

    await require_vehicle_and_driver_available(
        db,
        tenant_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
    )

    # LOAD-01: Payload weight guard on assignment
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if (
        vehicle is not None
        and vehicle.max_payload_kg is not None
        and order.estimated_weight is not None
        and order.estimated_weight > vehicle.max_payload_kg
        and not payload.payload_override_reason
    ):
        excess = float(order.estimated_weight - vehicle.max_payload_kg)
        raise ApiError(
            "payload_exceeded",
            f"Cargo weight exceeds vehicle max payload capacity by {excess:.2f} kg.",
            status_code=409,
            details={
                "cargo_weight_kg": float(order.estimated_weight),
                "max_payload_kg": float(vehicle.max_payload_kg),
                "excess_kg": excess,
            },
        )

    old_values = {
        "status": order.status,
        "assigned_vehicle_id": (
            str(order.assigned_vehicle_id) if order.assigned_vehicle_id else None
        ),
        "assigned_driver_id": str(order.assigned_driver_id) if order.assigned_driver_id else None,
    }
    order.status = "assigned"
    order.assigned_vehicle_id = payload.vehicle_id
    order.assigned_driver_id = payload.driver_id
    order.assigned_by = actor_id
    order.assigned_at = now_utc()

    trip = Trip(
        tenant_id=tenant_id,
        trip_order_id=order.id,
        contract_id=order.contract_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        origin=order.origin,
        origin_location=None,
        destination=order.destination,
        destination_location=None,
        cargo_type=order.cargo_type,
        cargo_class=None,
        cargo_weight=order.estimated_weight,
        cargo_volume=order.estimated_volume,
        load_state=None,
        requires_load_permit=order.requires_load_permit,
        requires_cargo_manifest=False,
        planned_departure=order.sla_pickup_deadline,
        planned_arrival=order.sla_delivery_deadline,
        status="planned",
        billing_status="pending_delivery_proof",
        payload_override_reason=payload.payload_override_reason,
    )
    if order.contract_id:
        contract = await db.get(Contract, order.contract_id)
        trip.contract_reference = contract.contract_reference if contract else None

    db.add(trip)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ApiError(
            "assignment_conflict",
            "Vehicle or driver already has an active trip.",
            status_code=409,
        ) from exc

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip_order.assigned",
        entity_type="trip_order",
        entity_id=order.id,
        old_values=old_values,
        new_values={
            "status": order.status,
            "assigned_vehicle_id": str(order.assigned_vehicle_id),
            "assigned_driver_id": str(order.assigned_driver_id),
            "trip_id": str(trip.id),
            "reason": payload.reason,
        },
    )
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip.created_from_order",
        entity_type="trip",
        entity_id=trip.id,
        new_values={"trip_order_id": str(order.id), "status": trip.status},
    )
    await db.commit()
    await db.refresh(order)
    await db.refresh(trip)
    return {"trip_order": serialize_trip_order(order), "trip": serialize_trip(trip)}


async def cancel_trip_order(
    db: AsyncSession,
    tenant_id: UUID,
    order_id: UUID,
    payload: TripOrderCancelRequest,
    *,
    actor_id: UUID | None = None,
) -> dict:
    order = await _require_order(db, tenant_id, order_id)
    if order.status == "cancelled":
        return serialize_trip_order(order)
    if order.status in {"assigned", "dispatched", "in_execution", "delivered", "closed"}:
        raise ApiError(
            "invalid_trip_order_status",
            "Assigned or active trip orders cannot be cancelled here.",
            status_code=409,
            details={"status": order.status},
        )
    old_values = {"status": order.status}
    order.status = "cancelled"
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip_order.cancelled",
        entity_type="trip_order",
        entity_id=order.id,
        old_values=old_values,
        new_values={"status": order.status, "reason": payload.reason},
    )
    await db.commit()
    await db.refresh(order)
    return serialize_trip_order(order)


# ── SM-04: DispatchClearance reject ──────────────────────────────────────────


async def reject_dispatch_clearance(
    db: AsyncSession,
    *,
    order_id: UUID,
    tenant_id: UUID,
    user_id: UUID,
    rejection_reason: str,
) -> TripOrder:
    """SM-04: Reject dispatch clearance — sets status to 'rejected' with reason and timestamp."""
    order = await db.get(TripOrder, order_id)
    if not order or order.tenant_id != tenant_id:
        raise ApiError("trip_order_not_found", "Trip order not found.", status_code=404)

    old_status = order.status
    order.status = "rejected"
    order.rejection_reason = rejection_reason
    order.rejected_at = now_utc()
    order.rejected_by = user_id
    db.add(order)

    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="trip_order.clearance_rejected",
        entity_type="trip_order",
        entity_id=order.id,
        old_values={"status": old_status},
        new_values={"status": "rejected", "rejection_reason": rejection_reason},
    )
    return order
