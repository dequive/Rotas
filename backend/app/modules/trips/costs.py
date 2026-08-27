from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from app.modules.trips.models import Trip, TripCost
from app.modules.trips.revenue import auto_calculate_revenue


def _decimal(value: float | Decimal | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def serialize_trip_cost(item: TripCost) -> dict:
    return {
        "id": item.id,
        "trip_id": item.trip_id,
        "cost_type": item.cost_type,
        "description": item.description,
        "amount": item.amount,
        "currency": item.currency,
        "paid_by": item.paid_by,
        "payment_method": item.payment_method,
        "receipt_file_id": item.receipt_file_id,
        "request_reference": item.request_reference,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "entry_type": item.entry_type,
        "corrects_id": item.corrects_id,
        "correction_reason": item.correction_reason,
        "driver_id": item.driver_id,
        "driver_visibility": item.driver_visibility,
        "recorded_by_type": item.recorded_by_type,
        "incurred_at": item.incurred_at,
        "created_at": item.created_at,
    }


async def record_trip_cost(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    trip_id: UUID,
    cost_type: str,
    amount: float | Decimal,
    request_reference: str,
    incurred_at: datetime,
    actor_id: UUID | None,
    description: str | None = None,
    currency: str = "MZN",
    paid_by: str = "company",
    payment_method: str | None = None,
    receipt_file_id: UUID | None = None,
    source_type: str = "manual",
    source_id: UUID | None = None,
    entry_type: str = "original",
    corrects_id: UUID | None = None,
    correction_reason: str | None = None,
    driver_id: UUID | None = None,
    driver_visibility: str | None = None,
    recorded_by_type: str | None = None,
) -> TripCost:
    value = _decimal(amount)
    if entry_type == "original" and value < 0:
        raise ApiError("invalid_trip_cost", "Trip cost cannot be negative.", status_code=422)
    trip = await db.get(Trip, trip_id)
    if not trip or trip.tenant_id != tenant_id:
        raise ApiError("trip_not_found", "Trip not found.", status_code=404)
    journal_driver_id = driver_id if driver_id is not None else trip.driver_id
    visibility = driver_visibility or ("visible" if paid_by == "driver" else "hidden")
    actor_type = recorded_by_type or ("manager" if actor_id else "system")
    existing = await db.scalar(
        select(TripCost).where(
            TripCost.tenant_id == tenant_id,
            TripCost.request_reference == request_reference,
        )
    )
    if existing:
        if (
            existing.trip_id != trip_id
            or existing.cost_type != cost_type
            or _decimal(existing.amount) != value
            or existing.source_type != source_type
            or existing.source_id != source_id
            or existing.entry_type != entry_type
            or existing.corrects_id != corrects_id
        ):
            raise ApiError(
                "trip_cost_request_reference_reused",
                "Trip cost request reference was reused with a different payload.",
                status_code=409,
            )
        return existing
    item = TripCost(
        tenant_id=tenant_id,
        trip_id=trip_id,
        cost_type=cost_type,
        description=description,
        amount=value,
        currency=currency,
        paid_by=paid_by,
        payment_method=payment_method,
        receipt_file_id=receipt_file_id,
        request_reference=request_reference,
        source_type=source_type,
        source_id=source_id,
        created_by=actor_id,
        entry_type=entry_type,
        corrects_id=corrects_id,
        correction_reason=correction_reason,
        driver_id=journal_driver_id,
        driver_visibility=visibility,
        recorded_by_type=actor_type,
        incurred_at=incurred_at,
    )
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action=f"trip_cost.{entry_type}.recorded",
        entity_type="trip_cost",
        entity_id=item.id,
        new_values={
            "trip_cost_id": str(item.id),
            "cost_type": cost_type,
            "amount": str(value),
            "request_reference": request_reference,
            "corrects_id": str(corrects_id) if corrects_id else None,
            "driver_id": str(journal_driver_id) if journal_driver_id else None,
            "driver_visibility": visibility,
            "recorded_by_type": actor_type,
        },
    )
    await reconcile_trip_costs(db, tenant_id, trip)
    return item


async def correct_trip_cost(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    trip_id: UUID,
    cost_id: UUID,
    correction_type: str,
    adjustment_amount: Decimal | None,
    reason: str,
    request_reference: str,
    incurred_at: datetime,
    actor_id: UUID | None,
) -> TripCost:
    existing = await db.scalar(
        select(TripCost).where(
            TripCost.tenant_id == tenant_id,
            TripCost.request_reference == request_reference,
        )
    )
    if existing:
        expected_amount = _decimal(adjustment_amount) if adjustment_amount is not None else None
        if (
            existing.trip_id != trip_id
            or existing.corrects_id != cost_id
            or existing.entry_type != correction_type
            or existing.correction_reason != reason
            or (expected_amount is not None and _decimal(existing.amount) != expected_amount)
        ):
            raise ApiError(
                "trip_cost_request_reference_reused",
                "Trip cost request reference was reused with a different payload.",
                status_code=409,
            )
        return existing

    original = await db.scalar(
        select(TripCost)
        .where(
            TripCost.tenant_id == tenant_id,
            TripCost.trip_id == trip_id,
            TripCost.id == cost_id,
        )
        .with_for_update()
    )
    if not original or original.entry_type != "original":
        raise ApiError("trip_cost_not_found", "Original trip cost not found.", status_code=404)

    entries = (
        await db.scalars(
            select(TripCost).where(
                TripCost.tenant_id == tenant_id,
                TripCost.corrects_id == original.id,
            )
        )
    ).all()
    if any(entry.entry_type == "reversal" for entry in entries):
        raise ApiError(
            "trip_cost_already_reversed",
            "Trip cost is already reversed and cannot receive more corrections.",
            status_code=409,
        )
    balance = _decimal(original.amount) + sum(
        (_decimal(entry.amount) for entry in entries),
        Decimal("0.00"),
    )
    if correction_type == "reversal":
        if balance <= 0:
            raise ApiError(
                "trip_cost_not_reversible",
                "Trip cost has no positive balance to reverse.",
                status_code=409,
            )
        value = -balance
    else:
        value = _decimal(adjustment_amount)
        if balance + value < 0:
            raise ApiError(
                "trip_cost_negative_balance",
                "Adjustment cannot make the trip cost balance negative.",
                status_code=422,
            )

    return await record_trip_cost(
        db,
        tenant_id,
        trip_id=trip_id,
        cost_type=original.cost_type,
        description=original.description,
        amount=value,
        currency=original.currency,
        paid_by=original.paid_by,
        payment_method=original.payment_method,
        receipt_file_id=original.receipt_file_id,
        request_reference=request_reference,
        source_type="trip_cost_correction",
        source_id=original.id,
        actor_id=actor_id,
        entry_type=correction_type,
        corrects_id=original.id,
        correction_reason=reason,
        driver_id=original.driver_id,
        driver_visibility=original.driver_visibility,
        recorded_by_type="manager" if actor_id else "system",
        incurred_at=incurred_at,
    )


async def reconcile_trip_costs(db: AsyncSession, tenant_id: UUID, trip: Trip) -> Trip:
    expense_total = _decimal(
        await db.scalar(
            select(func.coalesce(func.sum(TripCost.amount), 0)).where(
                TripCost.tenant_id == tenant_id,
                TripCost.trip_id == trip.id,
            )
        )
    )
    revenue = await auto_calculate_revenue(db, tenant_id, trip)
    fuel_total = _decimal(trip.total_fuel_cost)
    trip.total_expense_cost = expense_total
    trip.total_transport_cost = fuel_total + expense_total
    trip.actual_revenue = revenue
    trip.actual_margin = revenue - _decimal(trip.total_transport_cost)
    trip.costs_reconciled_at = datetime.now(UTC)
    return trip
