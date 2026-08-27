import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError

from app.core.tokens import create_access_token
from app.modules.drivers.models import Driver
from app.modules.trips.models import Trip, TripCost
from app.modules.vehicles.models import Vehicle


@pytest.fixture
async def trip_cost_context(db, tenant_id, test_user):
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Motorista do diário",
        phone="840000099",
        status="active",
    )
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"CST-{uuid4().hex[:5]}",
        status="active",
    )
    db.add_all([driver, vehicle])
    await db.flush()
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Xai-Xai",
        status="in_progress",
        actual_revenue=2000,
    )
    db.add(trip)
    await db.commit()

    token, _ = create_access_token(
        tenant_id=tenant_id,
        user_id=test_user.id,
        scope="dashboard",
        role="admin",
    )
    return {
        "driver": driver,
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": str(tenant_id),
        },
        "trip": trip,
        "user": test_user,
    }


@pytest.mark.asyncio
async def test_driver_paid_cost_snapshots_actor_owner_and_visibility(
    async_client, db, trip_cost_context
):
    response = await async_client.post(
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs",
        headers=trip_cost_context["headers"],
        json={
            "cost_type": "toll",
            "description": "Portagem paga pelo motorista",
            "amount": 1000,
            "currency": "MZN",
            "paid_by": "driver",
            "payment_method": "cash",
            "request_reference": f"driver-cost:{uuid4()}",
            "incurred_at": "2026-08-24T08:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["entry_type"] == "original"
    assert body["driver_id"] == str(trip_cost_context["driver"].id)
    assert body["driver_visibility"] == "visible"
    assert body["recorded_by_type"] == "manager"
    assert body["corrects_id"] is None
    assert body["correction_reason"] is None

    stored = await db.get(TripCost, body["id"])
    assert stored is not None
    assert stored.created_by == trip_cost_context["user"].id


@pytest.mark.asyncio
async def test_adjustment_creates_signed_entry_without_rewriting_original(
    async_client, db, tenant_id, trip_cost_context
):
    original_response = await async_client.post(
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs",
        headers=trip_cost_context["headers"],
        json={
            "cost_type": "toll",
            "amount": 1000,
            "paid_by": "driver",
            "request_reference": f"driver-cost:{uuid4()}",
            "incurred_at": "2026-08-24T08:00:00Z",
        },
    )
    original = original_response.json()
    idempotency_key = f"trip-cost-adjustment:{uuid4()}"
    correction_payload = {
        "correction_type": "adjustment",
        "adjustment_amount": -250,
        "reason": "Valor da portagem registado acima do comprovativo",
        "request_reference": f"driver-cost-adjustment:{uuid4()}",
        "incurred_at": "2026-08-24T09:00:00Z",
    }

    adjustment_response = await async_client.post(
        (
            f"/api/v1/trips/{trip_cost_context['trip'].id}/costs/"
            f"{original['id']}/corrections"
        ),
        headers={**trip_cost_context["headers"], "Idempotency-Key": idempotency_key},
        json=correction_payload,
    )
    replay_response = await async_client.post(
        (
            f"/api/v1/trips/{trip_cost_context['trip'].id}/costs/"
            f"{original['id']}/corrections"
        ),
        headers={**trip_cost_context["headers"], "Idempotency-Key": idempotency_key},
        json=correction_payload,
    )

    assert adjustment_response.status_code == 201, adjustment_response.text
    assert replay_response.status_code == 201, replay_response.text
    adjustment = adjustment_response.json()
    assert replay_response.json()["id"] == adjustment["id"]
    assert adjustment["entry_type"] == "adjustment"
    assert adjustment["corrects_id"] == original["id"]
    assert adjustment["amount"] == "-250.00"
    assert adjustment["correction_reason"] == correction_payload["reason"]
    assert adjustment["driver_visibility"] == "visible"

    stored_original = await db.get(TripCost, original["id"])
    assert stored_original is not None
    assert stored_original.amount == 1000
    assert await db.scalar(
        select(func.count(TripCost.id)).where(
            TripCost.tenant_id == tenant_id,
            TripCost.trip_id == trip_cost_context["trip"].id,
        )
    ) == 2
    await db.refresh(trip_cost_context["trip"])
    assert trip_cost_context["trip"].total_expense_cost == 750
    assert trip_cost_context["trip"].total_transport_cost == 750
    assert trip_cost_context["trip"].actual_margin == -750


@pytest.mark.asyncio
async def test_reversal_zeros_balance_and_closes_correction_chain(
    async_client, db, trip_cost_context
):
    original_response = await async_client.post(
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs",
        headers=trip_cost_context["headers"],
        json={
            "cost_type": "toll",
            "amount": 900,
            "paid_by": "driver",
            "request_reference": f"driver-cost:{uuid4()}",
            "incurred_at": "2026-08-24T08:00:00Z",
        },
    )
    original = original_response.json()
    correction_url = (
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs/"
        f"{original['id']}/corrections"
    )
    reversal = await async_client.post(
        correction_url,
        headers={**trip_cost_context["headers"], "Idempotency-Key": f"reverse:{uuid4()}"},
        json={
            "correction_type": "reversal",
            "reason": "Lançamento associado à viagem errada",
            "request_reference": f"driver-cost-reversal:{uuid4()}",
            "incurred_at": "2026-08-24T10:00:00Z",
        },
    )
    blocked = await async_client.post(
        correction_url,
        headers={**trip_cost_context["headers"], "Idempotency-Key": f"adjust:{uuid4()}"},
        json={
            "correction_type": "adjustment",
            "adjustment_amount": 10,
            "reason": "Tentativa posterior à reversão",
            "request_reference": f"driver-cost-adjustment:{uuid4()}",
            "incurred_at": "2026-08-24T11:00:00Z",
        },
    )

    assert reversal.status_code == 201, reversal.text
    assert reversal.json()["entry_type"] == "reversal"
    assert reversal.json()["amount"] == "-900.00"
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["code"] == "trip_cost_already_reversed"
    await db.refresh(trip_cost_context["trip"])
    assert trip_cost_context["trip"].total_expense_cost == 0


@pytest.mark.asyncio
async def test_database_rejects_trip_cost_update_and_delete(
    async_client, db, trip_cost_context
):
    response = await async_client.post(
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs",
        headers=trip_cost_context["headers"],
        json={
            "cost_type": "toll",
            "amount": 100,
            "request_reference": f"immutable-cost:{uuid4()}",
            "incurred_at": "2026-08-24T08:00:00Z",
        },
    )
    cost_id = response.json()["id"]

    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(update(TripCost).where(TripCost.id == cost_id).values(amount=999))
    await db.rollback()

    with pytest.raises(DBAPIError, match="append-only"):
        await db.execute(delete(TripCost).where(TripCost.id == cost_id))
    await db.rollback()


@pytest.mark.asyncio
async def test_concurrent_reversals_create_exactly_one_physical_entry(
    async_client, db, tenant_id, trip_cost_context
):
    original_response = await async_client.post(
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs",
        headers=trip_cost_context["headers"],
        json={
            "cost_type": "toll",
            "amount": 500,
            "paid_by": "driver",
            "request_reference": f"concurrent-original:{uuid4()}",
            "incurred_at": "2026-08-24T08:00:00Z",
        },
    )
    original = original_response.json()
    url = (
        f"/api/v1/trips/{trip_cost_context['trip'].id}/costs/"
        f"{original['id']}/corrections"
    )

    async def reverse(sequence: int):
        return await async_client.post(
            url,
            headers={
                **trip_cost_context["headers"],
                "Idempotency-Key": f"concurrent-reversal-key:{uuid4()}",
            },
            json={
                "correction_type": "reversal",
                "reason": "Anulação concorrente controlada",
                "request_reference": f"concurrent-reversal:{sequence}:{uuid4()}",
                "incurred_at": "2026-08-24T10:00:00Z",
            },
        )

    responses = await asyncio.gather(reverse(1), reverse(2))

    assert sorted(response.status_code for response in responses) == [201, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json()["error"]["code"] == "trip_cost_already_reversed"
    reversal_count = await db.scalar(
        select(func.count(TripCost.id)).where(
            TripCost.tenant_id == tenant_id,
            TripCost.corrects_id == original["id"],
            TripCost.entry_type == "reversal",
        )
    )
    assert reversal_count == 1
