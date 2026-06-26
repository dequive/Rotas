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
        "incurred_at": item.incurred_at,
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
) -> TripCost:
    value = _decimal(amount)
    if value < 0:
        raise ApiError("invalid_trip_cost", "Trip cost cannot be negative.", status_code=422)
    trip = await db.get(Trip, trip_id)
    if not trip or trip.tenant_id != tenant_id:
        raise ApiError("trip_not_found", "Trip not found.", status_code=404)
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
        incurred_at=incurred_at,
    )
    db.add(item)
    await db.flush()
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="trip_cost.recorded",
        entity_type="trip",
        entity_id=trip_id,
        new_values={
            "trip_cost_id": str(item.id),
            "cost_type": cost_type,
            "amount": str(value),
            "request_reference": request_reference,
        },
    )
    await reconcile_trip_costs(db, tenant_id, trip)
    return item


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
