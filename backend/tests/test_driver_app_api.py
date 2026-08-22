import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.tokens import create_access_token
from app.modules.cargo.models import DeliveryProof
from app.modules.checklists.models import Checklist, ChecklistTemplate
from app.modules.drivers.models import Driver, DriverDevice
from app.modules.fuel.models import FuelLog
from app.modules.sync.models import IdempotencyKey, SyncEvent
from app.modules.trips.models import Trip, TripStop
from app.modules.vehicles.models import Vehicle


@pytest.fixture
async def driver_app_context(db, tenant_id):
    suffix = uuid4().hex[:8]
    device_id = f"driver-device-{suffix}"
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Driver App Test",
        phone="840000000",
        status="active",
    )
    other_driver = Driver(
        tenant_id=tenant_id,
        full_name="Other Driver",
        phone="840000001",
        status="active",
    )
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"DRV-{suffix[:4]}",
        brand="Toyota",
        model="Dyna",
        status="active",
        current_km=1200,
    )
    template = ChecklistTemplate(
        tenant_id=tenant_id,
        name="Pre partida padrao",
        type="pre_partida",
        is_active=True,
        items=[
            {
                "id": "oil",
                "label": "Nivel de oleo",
                "type": "boolean",
                "is_blocking": True,
            }
        ],
    )
    db.add_all([driver, other_driver, vehicle, template])
    await db.flush()

    device = DriverDevice(
        tenant_id=tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        device_name="ROTAS App",
        is_active=True,
    )
    db.add(device)
    await db.commit()

    token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        scope="driver_app",
    )

    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": str(tenant_id),
        },
        "driver": driver,
        "other_driver": other_driver,
        "vehicle": vehicle,
        "template": template,
        "device_id": device_id,
    }


@pytest.mark.asyncio
async def test_driver_bootstrap_uses_driver_contract(async_client, driver_app_context):
    response = await async_client.get(
        "/api/v1/driver/bootstrap",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["profile"]["driver_id"] == str(driver_app_context["driver"].id)
    assert data["activeTrip"] is None
    assert [template["name"] for template in data["checklistTemplates"]] == [
        driver_app_context["template"].name
    ]
    assert data["vehicles"] == []


@pytest.mark.asyncio
async def test_dashboard_token_cannot_use_driver_contract(async_client, viewer_headers):
    response = await async_client.get(
        "/api/v1/driver/bootstrap",
        headers=viewer_headers,
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_scope_required"


@pytest.mark.asyncio
async def test_driver_cannot_list_general_fleet(async_client, driver_app_context):
    response = await async_client.get(
        "/api/v1/driver/vehicles",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"


@pytest.mark.asyncio
async def test_driver_cannot_create_trip(
    async_client, db, tenant_id, driver_app_context
):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["driver"].id),
            "origin": "Maputo",
            "destination": "Matola",
            "cargo_type": "geral",
            "load_state": "loaded",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"
    assert await db.scalar(select(func.count(Trip.id)).where(Trip.tenant_id == tenant_id)) == 0


@pytest.mark.asyncio
async def test_driver_cannot_create_trip_for_another_driver(async_client, driver_app_context):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["other_driver"].id),
            "origin": "Maputo",
            "destination": "Matola",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"


@pytest.mark.asyncio
async def test_driver_trip_creation_is_forbidden_before_payload_validation(
    async_client, driver_app_context
):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["driver"].id),
            "origin": "   ",
            "destination": "Matola",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_operation_forbidden"


@pytest.mark.asyncio
async def test_driver_sync_rejects_another_authenticated_device(
    async_client, driver_app_context
):
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={"device_id": "another-device", "operations": []},
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_device_mismatch"


@pytest.mark.asyncio
async def test_driver_sync_refuses_manager_owned_operations(
    async_client, db, tenant_id, driver_app_context
):
    operations = [
        (
            "trip",
            {
                "vehicleId": str(driver_app_context["vehicle"].id),
                "driverId": str(driver_app_context["driver"].id),
                "origin": "Maputo",
                "destination": "Matola",
            },
        ),
        ("load_permit", {"tripId": str(uuid4()), "permitNumber": "LP-001"}),
        ("cargo_manifest", {"tripId": str(uuid4()), "manifestNumber": "MAN-001"}),
        (
            "transport_document",
            {"tripId": str(uuid4()), "documentType": "guia_remessa"},
        ),
    ]
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": f"forbidden-{entity_type}",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": entity_type,
                    "payload": payload,
                }
                for entity_type, payload in operations
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert [result["error_code"] for result in response.json()["results"]] == [
        "driver_operation_forbidden",
    ] * len(operations)
    assert await db.scalar(select(func.count(Trip.id)).where(Trip.tenant_id == tenant_id)) == 0


@pytest.mark.asyncio
async def test_driver_sync_bootstrap_only_advertises_driver_owned_operations(
    async_client, driver_app_context
):
    response = await async_client.get(
        "/api/v1/sync/bootstrap",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    assert set(response.json()["supported_entity_types"]) == {
        "checklist",
        "fuel_log",
        "trip_stop",
        "delivery_proof",
        "trip_cost",
    }


@pytest.mark.asyncio
async def test_driver_sync_cannot_write_to_another_drivers_trip(
    async_client, db, tenant_id, driver_app_context
):
    other_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add(other_trip)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-stop",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "trip_stop",
                    "payload": {
                        "tripId": str(other_trip.id),
                        "stopType": "rest",
                        "address": "Matola",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_trip_forbidden"
    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == other_trip.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_driver_sync_cannot_add_operations_to_a_closed_trip(
    async_client, db, tenant_id, driver_app_context
):
    closed_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="closed",
        billing_status="pending_delivery_proof",
    )
    db.add(closed_trip)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "closed-trip-stop",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "trip_stop",
                    "payload": {
                        "tripId": str(closed_trip.id),
                        "stopType": "rest",
                        "address": "Matola",
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_trip_not_active"
    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == closed_trip.id)
        )
        == 0
    )


@pytest.mark.asyncio
async def test_driver_sync_cannot_submit_another_drivers_fuel_log(
    async_client, db, driver_app_context
):
    reference = f"foreign-driver-{uuid4()}"
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["other_driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1000,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_identity_mismatch"
    assert await db.scalar(
        select(func.count(FuelLog.id)).where(FuelLog.payment_reference == reference)
    ) == 0


@pytest.mark.asyncio
async def test_driver_sync_cannot_use_an_unassigned_vehicle(
    async_client, db, driver_app_context
):
    reference = f"unassigned-vehicle-{uuid4()}"
    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "unassigned-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1000,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_vehicle_forbidden"
    assert await db.scalar(
        select(func.count(FuelLog.id)).where(FuelLog.payment_reference == reference)
    ) == 0


@pytest.mark.asyncio
async def test_driver_sync_accepts_own_assigned_vehicle(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    db.add(assigned_trip)
    await db.commit()
    reference = f"assigned-vehicle-{uuid4()}"

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "assigned-fuel",
                    "idempotency_key": str(uuid4()),
                    "operation": "create",
                    "entity_type": "fuel_log",
                    "payload": {
                        "driverId": str(driver_app_context["driver"].id),
                        "vehicleId": str(driver_app_context["vehicle"].id),
                        "fuelDate": "2026-08-22T12:00:00+00:00",
                        "liters": 30,
                        "totalCost": 3000,
                        "kmAtRefuel": 1300,
                        "paymentReference": reference,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "processed"
    assert result["error_code"] is None
    assert await db.scalar(
        select(func.count(FuelLog.id)).where(FuelLog.payment_reference == reference)
    ) == 1


@pytest.mark.asyncio
async def test_driver_sync_cannot_update_another_drivers_fuel_log(
    async_client, db, tenant_id, driver_app_context
):
    foreign_log = FuelLog(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        fuel_date=datetime.now(UTC),
        liters=30,
        total_cost=3000,
        km_at_refuel=1300,
        payment_reference=f"foreign-update-{uuid4()}",
    )
    db.add(foreign_log)
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-fuel-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "fuel_log",
                    "payload": {
                        "serverId": str(foreign_log.id),
                        "liters": 99,
                        "totalCost": 9900,
                    },
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["error_code"] == "driver_record_forbidden"
    await db.refresh(foreign_log)
    assert float(foreign_log.liters) == 30
    assert float(foreign_log.total_cost) == 3000


@pytest.mark.asyncio
async def test_driver_sync_cannot_update_another_drivers_operational_records(
    async_client, db, tenant_id, driver_app_context
):
    foreign_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    foreign_checklist = Checklist(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["other_driver"].id,
        template_id=driver_app_context["template"].id,
        type=driver_app_context["template"].type,
        status="in_progress",
        responses={},
    )
    db.add_all([foreign_trip, foreign_checklist])
    await db.flush()
    foreign_stop = TripStop(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        stop_type="rest",
        address="Matola",
        notes="original stop",
        stopped_at=datetime.now(UTC),
    )
    foreign_proof = DeliveryProof(
        tenant_id=tenant_id,
        trip_id=foreign_trip.id,
        delivered_at=datetime.now(UTC),
        notes="original proof",
        status="pending",
    )
    db.add_all([foreign_stop, foreign_proof])
    await db.commit()

    response = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={
            "device_id": driver_app_context["device_id"],
            "operations": [
                {
                    "local_id": "foreign-checklist-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "checklist",
                    "payload": {
                        "serverId": str(foreign_checklist.id),
                        "responses": {"oil": True},
                    },
                },
                {
                    "local_id": "foreign-stop-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "trip_stop",
                    "payload": {
                        "serverId": str(foreign_stop.id),
                        "notes": "tampered stop",
                    },
                },
                {
                    "local_id": "foreign-proof-update",
                    "idempotency_key": str(uuid4()),
                    "operation": "update",
                    "entity_type": "delivery_proof",
                    "payload": {
                        "serverId": str(foreign_proof.id),
                        "notes": "tampered proof",
                    },
                },
            ],
        },
    )

    assert response.status_code == 200, response.text
    assert [result["error_code"] for result in response.json()["results"]] == [
        "driver_record_forbidden",
        "driver_record_forbidden",
        "driver_record_forbidden",
    ]
    await db.refresh(foreign_checklist)
    await db.refresh(foreign_stop)
    await db.refresh(foreign_proof)
    assert foreign_checklist.responses == {}
    assert foreign_stop.notes == "original stop"
    assert foreign_proof.notes == "original proof"


@pytest.mark.asyncio
async def test_driver_sync_rejects_idempotent_replay_from_another_owner_or_device(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Matola",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    other_device_id = f"other-driver-device-{uuid4().hex[:8]}"
    same_driver_device_id = f"same-driver-device-{uuid4().hex[:8]}"
    db.add_all(
        [
            assigned_trip,
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["other_driver"].id,
                device_id=other_device_id,
                device_name="Other Driver App",
                is_active=True,
            ),
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["driver"].id,
                device_id=same_driver_device_id,
                device_name="Second Driver App",
                is_active=True,
            ),
        ]
    )
    await db.commit()

    other_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["other_driver"].id,
        device_id=other_device_id,
        scope="driver_app",
    )
    same_driver_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["driver"].id,
        device_id=same_driver_device_id,
        scope="driver_app",
    )
    key = str(uuid4())
    operation = {
        "local_id": "owned-stop-replay",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": "trip_stop",
        "payload": {
            "tripId": str(assigned_trip.id),
            "stopType": "rest",
            "address": "Matola",
        },
    }

    first = await async_client.post(
        "/api/v1/sync/batch",
        headers=driver_app_context["headers"],
        json={"device_id": driver_app_context["device_id"], "operations": [operation]},
    )
    assert first.status_code == 200, first.text
    assert first.json()["results"][0]["status"] == "processed"

    for token, device_id, operations in (
        (other_token, other_device_id, [operation, operation]),
        (same_driver_token, same_driver_device_id, [operation]),
    ):
        replay = await async_client.post(
            "/api/v1/sync/batch",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Id": str(tenant_id),
            },
            json={"device_id": device_id, "operations": operations},
        )
        assert replay.status_code == 200, replay.text
        for result in replay.json()["results"]:
            assert result["status"] == "conflict"
            assert result["error_code"] == "idempotency_owner_mismatch"
            assert result["server_id"] is None

    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == assigned_trip.id)
        )
        == 1
    )
    mismatch_events = (
        await db.scalars(
            select(SyncEvent).where(
                SyncEvent.tenant_id == tenant_id,
                SyncEvent.idempotency_key == key,
                SyncEvent.error_code == "idempotency_owner_mismatch",
            )
        )
    ).all()
    assert len(mismatch_events) == 3
    assert {event.driver_id for event in mismatch_events} == {
        driver_app_context["driver"].id,
        driver_app_context["other_driver"].id,
    }
    assert {event.device_id for event in mismatch_events} == {
        other_device_id,
        same_driver_device_id,
    }
    assert all(event.server_id is None for event in mismatch_events)


@pytest.mark.asyncio
async def test_driver_sync_concurrent_key_consumption_accepts_exactly_one_device(
    async_client, db, tenant_id, driver_app_context
):
    assigned_trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=driver_app_context["vehicle"].id,
        driver_id=driver_app_context["driver"].id,
        origin="Maputo",
        destination="Marracuene",
        status="in_progress",
        billing_status="pending_delivery_proof",
    )
    second_device_id = f"racing-device-{uuid4().hex[:8]}"
    db.add_all(
        [
            assigned_trip,
            DriverDevice(
                tenant_id=tenant_id,
                driver_id=driver_app_context["driver"].id,
                device_id=second_device_id,
                device_name="Racing Driver App",
                is_active=True,
            ),
        ]
    )
    await db.commit()

    second_token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver_app_context["driver"].id,
        device_id=second_device_id,
        scope="driver_app",
    )
    key = str(uuid4())
    operation = {
        "local_id": "concurrent-owned-stop",
        "idempotency_key": key,
        "operation": "create",
        "entity_type": "trip_stop",
        "payload": {
            "tripId": str(assigned_trip.id),
            "stopType": "rest",
            "address": "Marracuene",
        },
    }

    async def post(token: str, device_id: str):
        return await async_client.post(
            "/api/v1/sync/batch",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-Id": str(tenant_id),
            },
            json={"device_id": device_id, "operations": [operation]},
        )

    responses = await asyncio.gather(
        post(
            driver_app_context["headers"]["Authorization"].removeprefix("Bearer "),
            driver_app_context["device_id"],
        ),
        post(second_token, second_device_id),
    )
    assert all(response.status_code == 200 for response in responses)
    results = [response.json()["results"][0] for response in responses]
    assert sorted(result["status"] for result in results) == ["conflict", "processed"]
    conflict = next(result for result in results if result["status"] == "conflict")
    assert conflict["error_code"] == "idempotency_owner_mismatch"
    assert conflict["server_id"] is None

    assert (
        await db.scalar(
            select(func.count(TripStop.id)).where(TripStop.trip_id == assigned_trip.id)
        )
        == 1
    )
    stored = await db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.tenant_id == tenant_id,
            IdempotencyKey.idempotency_key == key,
        )
    )
    assert stored is not None
    assert stored.driver_id == driver_app_context["driver"].id
    assert stored.device_id in {driver_app_context["device_id"], second_device_id}
