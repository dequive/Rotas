from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

BILLING_PENDING_DELIVERY = "pending_delivery_proof"
BILLING_PENDING_VALIDATION = "pending_delivery_validation"
BILLING_UNCONTRACTED = "uncontracted"
BILLING_BILLABLE = "billable"
VALIDATED_DELIVERY_STATUSES = frozenset({"validated", "verified"})


@dataclass(frozen=True)
class BillableTripCandidate:
    trip_id: UUID
    client_name: str
    contract_id: UUID | None
    contract_reference: str | None
    loaded_at: datetime | None
    delivered_at: datetime | None
    amount: float
    delivery_proof_id: UUID | None = None
    delivery_proof_status: str | None = None


def normalize_period_bounds(
    period_start: datetime,
    period_end: datetime,
) -> tuple[datetime, datetime]:
    if period_start.tzinfo is None:
        period_start = period_start.replace(tzinfo=UTC)
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=UTC)

    if period_end <= period_start:
        raise ValueError("period_end must be after period_start")

    return period_start, period_end


def billing_status_for_delivery(delivered_at: datetime | None) -> str:
    if delivered_at is None:
        return BILLING_PENDING_DELIVERY
    return BILLING_BILLABLE


def billing_status_for_candidate(candidate: BillableTripCandidate) -> str:
    if candidate.delivered_at is None or candidate.delivery_proof_id is None:
        return BILLING_PENDING_DELIVERY

    if candidate.delivery_proof_status not in VALIDATED_DELIVERY_STATUSES:
        return BILLING_PENDING_VALIDATION

    if candidate.contract_id is None:
        return BILLING_UNCONTRACTED

    return BILLING_BILLABLE


def can_create_billing_item(candidate: BillableTripCandidate) -> bool:
    return billing_status_for_candidate(candidate) == BILLING_BILLABLE


def belongs_to_billing_period(
    candidate: BillableTripCandidate,
    period_start: datetime,
    period_end: datetime,
) -> bool:
    if not can_create_billing_item(candidate):
        return False

    period_start, period_end = normalize_period_bounds(period_start, period_end)

    delivered_at = candidate.delivered_at
    if delivered_at.tzinfo is None:
        delivered_at = delivered_at.replace(tzinfo=UTC)

    return period_start <= delivered_at < period_end
