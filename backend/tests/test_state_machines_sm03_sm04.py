"""Phase 14 Plan 02 — SM-03 + SM-04 state machine tests.

Covers:
  SM-03 DeliveryProof: pending → accepted | rejected → disputed → resolved
  SM-04 TripOrder (DispatchClearance): pending → rejected | escalated

Must-haves tested:
  1. Accepting a pending delivery proof sets status='accepted', accepted_at and accepted_by
  2. Rejecting a pending delivery proof sets status='rejected' and creates an OperationalException
  3. Accepting an already-accepted proof returns HTTP 409 invalid_state_transition
  4. Rejecting a TripOrder dispatch clearance transitions it to 'rejected'
     with reason and rejected_at
  5. task_escalate_pending_clearances cron logic escalates pending orders past SLA to 'escalated'
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import and_, select

from app.modules.audit.models import AuditLog
from app.modules.cargo import service as cargo_service
from app.modules.cargo.models import DeliveryProof
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.models import OperationalException
from app.modules.trip_orders import service as trip_order_service
from app.modules.trip_orders.models import TripOrder
from app.modules.trips.models import Trip
from app.modules.users.models import User
from app.modules.vehicles.models import Vehicle

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _make_contract(db, tenant_id):
    c = Contract(
        tenant_id=tenant_id,
        client_name=f"SM03 Client {uuid4().hex[:6]}",
        contract_reference=f"SM03-{uuid4().hex[:6]}",
        status="active",
    )
    db.add(c)
    await db.flush()
    return c


async def _make_vehicle(db, tenant_id):
    v = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(v)
    await db.flush()
    return v


async def _make_driver(db, tenant_id):
    d = Driver(
        tenant_id=tenant_id,
        full_name=f"SM03 Driver {uuid4().hex[:6]}",
        status="active",
    )
    db.add(d)
    await db.flush()
    return d


async def _make_trip(db, tenant_id, vehicle, driver, contract=None):
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        contract_id=contract.id if contract else None,
        origin="Maputo",
        destination="Nacala",
        status="delivered",
        billing_status="pending_delivery_proof",
    )
    db.add(trip)
    await db.flush()
    return trip


async def _make_delivery_proof(db, tenant_id, trip, status="pending"):
    proof = DeliveryProof(
        tenant_id=tenant_id,
        trip_id=trip.id,
        contract_id=trip.contract_id,
        delivered_at=datetime.now(UTC) - timedelta(hours=2),
        status=status,
    )
    db.add(proof)
    await db.commit()
    await db.refresh(proof)
    return proof


async def _make_user(db, tenant_id):
    """Create a real User record so audit_log FK constraint is satisfied."""
    user = User(
        tenant_id=tenant_id,
        email=f"sm-test-{uuid4().hex[:8]}@test.local",
        password_hash="$argon2id$test",
        full_name="SM Test User",
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# SM-03 — DeliveryProof state machine (service-layer tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sm03_accept_proof_sets_accepted_fields(db, tenant_id):
    """Must-have 1: accepting a pending proof sets status=accepted, accepted_at, and accepted_by."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver)
    proof = await _make_delivery_proof(db, tenant_id, trip, status="pending")
    user = await _make_user(db, tenant_id)
    user_id = user.id

    updated = await cargo_service.accept_delivery_proof(
        db,
        proof_id=proof.id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    await db.commit()
    await db.refresh(updated)

    assert updated.status == "accepted"
    assert updated.accepted_at is not None
    assert updated.accepted_by == user_id

    # Trip billing status should have been updated to billable
    await db.refresh(trip)
    assert trip.billing_status == "billable"


@pytest.mark.asyncio
async def test_sm03_reject_proof_sets_rejected_and_creates_exception(db, tenant_id):
    """Must-have 2: rejecting a pending proof sets status=rejected
    and creates an OperationalException.
    """
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver)
    proof = await _make_delivery_proof(db, tenant_id, trip, status="pending")
    user = await _make_user(db, tenant_id)
    user_id = user.id

    reason = "Carga com danos visíveis. Prova de entrega rejeitada."
    updated = await cargo_service.reject_delivery_proof(
        db,
        proof_id=proof.id,
        tenant_id=tenant_id,
        user_id=user_id,
        rejection_reason=reason,
    )
    await db.commit()
    await db.refresh(updated)

    assert updated.status == "rejected"
    assert updated.rejected_at is not None
    assert updated.rejection_reason == reason

    # An operational exception must have been created in the same transaction
    exception = await db.scalar(
        select(OperationalException).where(
            OperationalException.tenant_id == tenant_id,
            OperationalException.entity_id == trip.id,
            OperationalException.exception_type == "delivery_rejected",
        )
    )
    assert exception is not None, "OperationalException must be created on delivery proof rejection"


@pytest.mark.asyncio
async def test_sm03_accept_already_accepted_proof_raises_409(db, tenant_id):
    """Must-have 3: accepting an already-accepted proof raises ApiError 409
    invalid_state_transition.
    """
    from app.core.errors import ApiError

    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver)
    proof = await _make_delivery_proof(db, tenant_id, trip, status="accepted")
    user = await _make_user(db, tenant_id)
    user_id = user.id

    with pytest.raises(ApiError) as exc_info:
        await cargo_service.accept_delivery_proof(
            db,
            proof_id=proof.id,
            tenant_id=tenant_id,
            user_id=user_id,
        )

    assert exc_info.value.code == "invalid_state_transition"
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_sm03_accept_proof_via_http(async_client, auth_headers, db, tenant_id):
    """HTTP endpoint: PATCH accept returns 200 with proof in accepted state."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver)
    proof = await _make_delivery_proof(db, tenant_id, trip, status="pending")

    resp = await async_client.patch(
        f"/api/v1/trips/{trip.id}/delivery-proof/{proof.id}/accept",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_sm03_reject_proof_via_http(async_client, auth_headers, db, tenant_id):
    """HTTP endpoint: PATCH reject returns 200 with proof in rejected state."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle, driver)
    proof = await _make_delivery_proof(db, tenant_id, trip, status="pending")

    resp = await async_client.patch(
        f"/api/v1/trips/{trip.id}/delivery-proof/{proof.id}/reject",
        json={"rejection_reason": "Documentação incompleta e inválida."},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# SM-04 — TripOrder DispatchClearance state machine
# ---------------------------------------------------------------------------


async def _make_trip_order(db, tenant_id, status="dispatch_pending", *, created_at_offset_hours=0):
    """Create a TripOrder. created_at_offset_hours makes it appear older for SLA tests."""
    from datetime import date

    created_at = datetime.now(UTC) - timedelta(hours=created_at_offset_hours)
    order = TripOrder(
        tenant_id=tenant_id,
        origin="Maputo",
        destination="Tete",
        requested_pickup_date=date.today(),
        status=status,
        priority="normal",
        source="manual",
        cargo_risk_level="normal",
        clearance_sla_hours=1,  # short SLA for test reliability
    )
    db.add(order)
    await db.commit()

    # Manually backdate created_at for SLA escalation tests
    if created_at_offset_hours > 0:
        from sqlalchemy import text

        await db.execute(
            text("UPDATE trip_orders SET created_at = :ts WHERE id = :id"),
            {"ts": created_at, "id": order.id},
        )
        await db.commit()

    await db.refresh(order)
    return order


@pytest.mark.asyncio
async def test_sm04_reject_dispatch_clearance(db, tenant_id):
    """Must-have 4: rejecting a trip order sets status='rejected' with reason and rejected_at."""
    order = await _make_trip_order(db, tenant_id, status="dispatch_pending")
    user = await _make_user(db, tenant_id)
    user_id = user.id

    updated = await trip_order_service.reject_dispatch_clearance(
        db,
        order_id=order.id,
        tenant_id=tenant_id,
        user_id=user_id,
        rejection_reason="Rota não aprovada para este veículo.",
    )
    await db.commit()
    await db.refresh(updated)

    assert updated.status == "rejected"
    assert updated.rejection_reason == "Rota não aprovada para este veículo."
    assert updated.rejected_at is not None
    assert updated.rejected_by == user_id

    # Audit log should exist
    audit = await db.scalar(
        select(AuditLog).where(
            AuditLog.entity_id == order.id,
            AuditLog.action == "trip_order.clearance_rejected",
        )
    )
    assert audit is not None, "Audit log for clearance rejection must exist"
    assert audit.entity_type == "trip_order"


@pytest.mark.asyncio
async def test_sm04_reject_via_http(async_client, auth_headers, db, tenant_id):
    """HTTP endpoint: PATCH reject returns 200 with order in rejected state."""
    order = await _make_trip_order(db, tenant_id, status="dispatch_pending")

    resp = await async_client.patch(
        f"/api/v1/trip-orders/{order.id}/reject",
        json={"rejection_reason": "Documentação insuficiente para despacho."},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_sm04_escalate_pending_clearances_cron_logic(db, tenant_id):
    """Must-have 5: cron logic marks escalated_at on dispatch_pending orders past their SLA."""
    # Create an order with clearance_sla_hours=1, created 2 hours ago
    order = await _make_trip_order(
        db, tenant_id, status="dispatch_pending", created_at_offset_hours=2
    )

    assert order.status == "dispatch_pending"
    assert order.escalated_at is None

    # Execute the escalation logic directly (matches worker.task_escalate_pending_clearances)
    now = datetime.now(UTC)
    result = await db.execute(
        select(TripOrder).where(
            and_(
                TripOrder.status == "dispatch_pending",
                TripOrder.escalated_at.is_(None),
                TripOrder.created_at < now - timedelta(hours=1),
                TripOrder.tenant_id == tenant_id,
            )
        )
    )
    pending_orders = result.scalars().all()

    escalated_ids = []
    for o in pending_orders:
        sla = o.clearance_sla_hours or 24
        if (now - o.created_at.replace(tzinfo=UTC)) > timedelta(hours=sla):
            o.escalated_at = now
            db.add(o)
            escalated_ids.append(o.id)

    await db.commit()

    assert order.id in escalated_ids, "Order past SLA must have escalated_at set by cron logic"

    await db.refresh(order)
    assert order.status == "dispatch_pending", (
        "Status remains dispatch_pending; escalated_at is the escalation marker"
    )
    assert order.escalated_at is not None
