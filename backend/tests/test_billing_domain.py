from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.billing.domain import (
    BILLING_BILLABLE,
    BILLING_PENDING_DELIVERY,
    BILLING_PENDING_VALIDATION,
    BILLING_UNCONTRACTED,
    BillableTripCandidate,
    belongs_to_billing_period,
    billing_status_for_candidate,
    billing_status_for_delivery,
    can_create_billing_item,
)


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_billing_period_uses_delivery_date_not_loading_date() -> None:
    candidate = BillableTripCandidate(
        trip_id=uuid4(),
        client_name="Cliente Contrato",
        contract_id=uuid4(),
        contract_reference="CTR-2026-001",
        loaded_at=dt("2026-05-30T10:00:00"),
        delivered_at=dt("2026-06-02T15:30:00"),
        amount=25000,
        delivery_proof_id=uuid4(),
        delivery_proof_status="validated",
    )

    may_start = dt("2026-05-01T00:00:00")
    june_start = dt("2026-06-01T00:00:00")
    july_start = dt("2026-07-01T00:00:00")

    assert belongs_to_billing_period(candidate, may_start, june_start) is False
    assert belongs_to_billing_period(candidate, june_start, july_start) is True


def test_trip_without_delivery_proof_is_not_billable() -> None:
    candidate = BillableTripCandidate(
        trip_id=uuid4(),
        client_name="Cliente Contrato",
        contract_id=uuid4(),
        contract_reference="CTR-2026-001",
        loaded_at=dt("2026-05-30T10:00:00"),
        delivered_at=None,
        amount=25000,
    )

    assert billing_status_for_delivery(candidate.delivered_at) == BILLING_PENDING_DELIVERY
    assert belongs_to_billing_period(
        candidate,
        dt("2026-05-01T00:00:00"),
        dt("2026-06-01T00:00:00"),
    ) is False


def test_trip_with_delivery_proof_is_billable() -> None:
    assert billing_status_for_delivery(dt("2026-06-02T15:30:00")) == BILLING_BILLABLE


def test_billing_item_requires_validated_delivery_proof_and_contract() -> None:
    base = {
        "trip_id": uuid4(),
        "client_name": "Cliente Contrato",
        "contract_reference": "CTR-2026-001",
        "loaded_at": dt("2026-06-01T10:00:00"),
        "delivered_at": dt("2026-06-02T15:30:00"),
        "amount": 25000,
    }

    pending = BillableTripCandidate(
        **base,
        contract_id=uuid4(),
        delivery_proof_id=uuid4(),
        delivery_proof_status="pending",
    )
    assert billing_status_for_candidate(pending) == BILLING_PENDING_VALIDATION
    assert can_create_billing_item(pending) is False

    uncontracted = BillableTripCandidate(
        **base,
        contract_id=None,
        delivery_proof_id=uuid4(),
        delivery_proof_status="validated",
    )
    assert billing_status_for_candidate(uncontracted) == BILLING_UNCONTRACTED
    assert can_create_billing_item(uncontracted) is False

    billable = BillableTripCandidate(
        **base,
        contract_id=uuid4(),
        delivery_proof_id=uuid4(),
        delivery_proof_status="validated",
    )
    assert billing_status_for_candidate(billable) == BILLING_BILLABLE
    assert can_create_billing_item(billable) is True


def test_invalid_billing_period_is_rejected() -> None:
    candidate = BillableTripCandidate(
        trip_id=uuid4(),
        client_name="Cliente Contrato",
        contract_id=uuid4(),
        contract_reference=None,
        loaded_at=None,
        delivered_at=dt("2026-06-02T15:30:00"),
        amount=1,
        delivery_proof_id=uuid4(),
        delivery_proof_status="validated",
    )

    with pytest.raises(ValueError, match="period_end"):
        belongs_to_billing_period(
            candidate,
            dt("2026-06-01T00:00:00"),
            dt("2026-06-01T00:00:00"),
        )
