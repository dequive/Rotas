import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.main import app
from app.modules.drivers.models import Driver
from app.modules.operational_exceptions.models import OperationalException
from app.modules.trip_orders.models import TripOrder
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle


@pytest.mark.asyncio
async def test_trip_patch_and_cache_invalidation(async_client, db, tenant_id, auth_headers, mock_redis):
    # Seed vehicle and driver
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate="MZ-99-AA-GP",
        category="pesado",
        fuel_type="gasoleo",
        max_payload_kg=Decimal("5000.00"),
        status="active"
    )
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Driver Layer2",
        status="active"
    )
    db.add_all([vehicle, driver])
    await db.commit()
    await db.refresh(vehicle)
    await db.refresh(driver)

    # Seed Trip
    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Matola",
        status="planned",
        cargo_weight=Decimal("3000.00"),
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    # Attach mock redis to app state
    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # 1. Test patch trip with new cargo weight within capacity
        payload = {
            "cargo_weight": 4000,
            "cargo_type": "Carga Geral Updated",
        }
        response = await async_client.patch(
            f"/api/v1/trips/{trip.id}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert float(response.json()["cargo_weight"]) == 4000.0
        
        # Verify cache invalidation was triggered
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

        # Reset mock
        mock_redis.delete.reset_mock()

        # 2. Test patch trip cargo weight exceeding vehicle capacity without override
        payload_exceeded = {
            "cargo_weight": 6000
        }
        response = await async_client.patch(
            f"/api/v1/trips/{trip.id}",
            json=payload_exceeded,
            headers=auth_headers
        )
        assert response.status_code == 409
        err = response.json()["error"]
        assert err["code"] == "payload_exceeded"
        assert "exceeds vehicle max payload capacity" in err["message"]

        # 3. Test patch trip cargo weight exceeding vehicle capacity WITH override reason
        payload_override = {
            "cargo_weight": 6000,
            "payload_override_reason": "Special approval from director"
        }
        response = await async_client.patch(
            f"/api/v1/trips/{trip.id}",
            json=payload_override,
            headers=auth_headers
        )
        assert response.status_code == 200
        assert float(response.json()["cargo_weight"]) == 6000.0
        assert response.json()["payload_override_reason"] == "Special approval from director"

    finally:
        app.state.redis = old_redis


@pytest.mark.asyncio
async def test_trip_order_assignment_payload_capacity(async_client, db, tenant_id, auth_headers):
    # Seed vehicle with 4000kg max payload
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate="MZ-88-BB-GP",
        category="pesado",
        fuel_type="gasoleo",
        max_payload_kg=Decimal("4000.00"),
        status="active"
    )
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Driver Assign",
        status="active"
    )
    db.add_all([vehicle, driver])
    await db.commit()
    await db.refresh(vehicle)
    await db.refresh(driver)

    # Seed Trip Order with 5000kg estimated weight (exceeds payload)
    order = TripOrder(
        tenant_id=tenant_id,
        origin="Maputo",
        destination="Gaza",
        cargo_type="Ferro",
        estimated_weight=Decimal("5000.00"),
        requested_pickup_date=date.today(),
        status="confirmed"
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # 1. Assign without override (should fail with 409)
    response = await async_client.post(
        f"/api/v1/trip-orders/{order.id}/assign",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "reason": "Test assigning big cargo"
        },
        headers=auth_headers
    )
    assert response.status_code == 409
    err = response.json()["error"]
    assert err["code"] == "payload_exceeded"
    assert "exceeds vehicle max payload capacity" in err["message"]

    # 2. Assign with override reason (should succeed)
    response = await async_client.post(
        f"/api/v1/trip-orders/{order.id}/assign",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "reason": "Test assigning big cargo",
            "payload_override_reason": "Extra trailer attached"
        },
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["trip_order"]["status"] == "assigned"
    assert data["trip"]["payload_override_reason"] == "Extra trailer attached"
    assert float(data["trip"]["cargo_weight"]) == 5000.0


@pytest.mark.asyncio
async def test_cargo_mutations_invalidate_cache(async_client, db, tenant_id, auth_headers, mock_redis):
    # Seed vehicle and driver and trip
    vehicle = Vehicle(tenant_id=tenant_id, plate="MZ-77-CC-GP", category="pesado", fuel_type="gasoleo", status="active")
    driver = Driver(tenant_id=tenant_id, full_name="Driver Cargo", status="active")
    db.add_all([vehicle, driver])
    await db.commit()
    await db.refresh(vehicle)
    await db.refresh(driver)

    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        origin="Maputo",
        destination="Maxixe",
        status="planned"
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)

    # Attach mock redis
    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # Test create load permit invalidates cache
        payload = {
            "permit_number": "PERMIT123",
            "authority_name": "INATRO",
            "permitted_weight_kg": 5000
        }
        mock_redis.delete.reset_mock()
        response = await async_client.post(
            f"/api/v1/trips/{trip.id}/load-permits",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

        # Test create guia-remessa invalidates cache
        payload_guia = {
            "client_name": "Cliente A",
            "recipient_name": "Cliente X",
            "origin": "Maputo",
            "destination": "Maxixe",
            "gross_weight": 500.0,
            "package_count": 10
        }
        mock_redis.delete.reset_mock()
        response = await async_client.post(
            f"/api/v1/trips/{trip.id}/guia-remessa",
            json=payload_guia,
            headers=auth_headers
        )
        assert response.status_code == 201
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

    finally:
        app.state.redis = old_redis


@pytest.mark.asyncio
async def test_operational_exceptions_invalidate_cache(async_client, db, tenant_id, auth_headers, mock_redis):
    # Seed operational exception
    exc = OperationalException(
        tenant_id=tenant_id,
        entity_type="trip",
        entity_id=uuid.uuid4(),
        exception_type="checklist_failed",
        severity="medium",
        title="Extintor em falta",
        message="Falta de extintor de incendios",
        status="open"
    )
    db.add(exc)
    await db.commit()
    await db.refresh(exc)

    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis

    try:
        # Acknowledge exception
        mock_redis.delete.reset_mock()
        response = await async_client.post(
            f"/api/v1/operational-exceptions/{exc.id}/acknowledge",
            headers=auth_headers
        )
        assert response.status_code == 200
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

        # Resolve exception
        mock_redis.delete.reset_mock()
        response = await async_client.post(
            f"/api/v1/operational-exceptions/{exc.id}/resolve",
            json={"resolution_notes": "Extintor colocado e inspecionado"},
            headers=auth_headers
        )
        assert response.status_code == 200
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")

    finally:
        app.state.redis = old_redis
