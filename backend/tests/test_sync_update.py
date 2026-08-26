"""
Contract tests for AUTH-04 sync updates of trip, checklist, trip_stop and
delivery_proof. Fuel facts are append-only under ADR-012. Also covers client_timestamp schema field and
bootstrap supported_operations reporting.

These tests are intentionally RED against the current codebase:
- _dispatch_update returns "unsupported_entity_type_for_update" for all types except checklist
- SyncOperation schema has no client_timestamp field
- bootstrap returns ["create"] only, not ["create", "update"]
"""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_driver_tenant():
    """Create a Tenant, Vehicle, and Driver, return (tenant, vehicle, driver)."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"SyncUpdate Tenant {suffix}", slug=f"sync-upd-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"UPD-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Update {suffix}",
            phone=f"25884{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant, vehicle, driver


def make_operation(entity_type: str, operation: str, payload: dict) -> dict:
    return {
        "local_id": f"local_{uuid4().hex[:8]}",
        "idempotency_key": f"idem_{uuid4().hex}",
        "operation": operation,
        "entity_type": entity_type,
        "payload": payload,
    }


async def sync_batch(client: httpx.AsyncClient, tenant_id, operations_list: list) -> dict:
    response = await client.post(
        "/api/v1/sync/batch",
        headers=auth_headers(tenant_id),
        json={"device_id": "test-device", "operations": operations_list},
    )
    assert response.status_code == 200, f"sync/batch failed: {response.text}"
    return response.json()


async def test_sync_update_trip_returns_processed():
    """AUTH-04: sync update for trip must return processed status.

    Current behavior: _dispatch_update returns "unsupported_entity_type_for_update" — MUST FAIL.
    """
    tenant, vehicle, driver = await create_driver_tenant()

    async with await create_api_client() as client:
        # Create a trip via sync batch create op
        create_op = make_operation(
            "trip",
            "create",
            {
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Beira",
                "cargo_type": "geral",
            },
        )
        create_result = await sync_batch(client, tenant.id, [create_op])
        trip_id = create_result["results"][0]["server_id"]
        assert trip_id is not None, "Trip creation must succeed before update test"

        # Now send an update operation for the same trip
        update_op = make_operation(
            "trip",
            "update",
            {
                "server_id": trip_id,
                "cargo_type": "perecivel",
                "client_timestamp": datetime.now(UTC).isoformat(),
            },
        )
        update_result = await sync_batch(client, tenant.id, [update_op])
        result = update_result["results"][0]

    # WILL FAIL: current code returns "unsupported_entity_type_for_update"
    assert result["status"] == "processed", (
        f"Expected 'processed' but got '{result['status']}' with error '{result.get('error_code')}'"
    )


async def test_sync_update_fuel_log_is_not_supported():
    """ADR-012: submitted fuel facts cannot be rewritten through Sync."""
    tenant, vehicle, driver = await create_driver_tenant()

    async with await create_api_client() as client:
        # Create a fuel_log via sync batch create op
        create_op = make_operation(
            "fuel_log",
            "create",
            {
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "fuel_date": datetime.now(UTC).isoformat(),
                "km_at_refuel": 1000,
                "liters": 50.0,
                "total_cost": 4500.0,
                "station_name": "Test Station",
                "payment_method": "cash",
            },
        )
        create_result = await sync_batch(client, tenant.id, [create_op])
        fuel_log_id = create_result["results"][0]["server_id"]
        assert fuel_log_id is not None, "FuelLog creation must succeed before update test"

        # Now send an update operation for the fuel log
        update_op = make_operation(
            "fuel_log",
            "update",
            {
                "server_id": fuel_log_id,
                "liters": 55.0,
                "client_timestamp": datetime.now(UTC).isoformat(),
            },
        )
        update_result = await sync_batch(client, tenant.id, [update_op])
        result = update_result["results"][0]

    assert result["status"] == "failed"
    assert result["error_code"] == "unsupported_entity_type_for_update"


async def test_sync_update_trip_stop_returns_processed():
    """AUTH-04: sync update for trip_stop must return processed status.

    Current behavior: _dispatch_update returns "unsupported_entity_type_for_update" — MUST FAIL.
    """
    tenant, vehicle, driver = await create_driver_tenant()

    async with await create_api_client() as client:
        # First create a trip
        create_trip_op = make_operation(
            "trip",
            "create",
            {
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Tete",
                "cargo_type": "geral",
            },
        )
        create_trip_result = await sync_batch(client, tenant.id, [create_trip_op])
        trip_id = create_trip_result["results"][0]["server_id"]
        assert trip_id is not None, "Trip creation must succeed"

        # Create a trip_stop on that trip
        create_stop_op = make_operation(
            "trip_stop",
            "create",
            {
                "trip_id": trip_id,
                "stop_type": "pausa",
                "address": "Inchope",
            },
        )
        create_stop_result = await sync_batch(client, tenant.id, [create_stop_op])
        stop_id = create_stop_result["results"][0]["server_id"]
        assert stop_id is not None, "TripStop creation must succeed before update test"

        # Now send an update operation for the trip stop
        update_op = make_operation(
            "trip_stop",
            "update",
            {
                "server_id": stop_id,
                "notes": "Paragem actualizada",
                "client_timestamp": datetime.now(UTC).isoformat(),
            },
        )
        update_result = await sync_batch(client, tenant.id, [update_op])
        result = update_result["results"][0]

    # WILL FAIL: current code returns "unsupported_entity_type_for_update"
    assert result["status"] == "processed", (
        f"Expected 'processed' but got '{result['status']}' with error '{result.get('error_code')}'"
    )


async def test_sync_update_delivery_proof_returns_processed():
    """AUTH-04: sync update for delivery_proof must return processed status.

    Current behavior: _dispatch_update returns "unsupported_entity_type_for_update" — MUST FAIL.
    """
    tenant, vehicle, driver = await create_driver_tenant()

    async with await create_api_client() as client:
        # First create a trip
        create_trip_op = make_operation(
            "trip",
            "create",
            {
                "vehicle_id": str(vehicle.id),
                "driver_id": str(driver.id),
                "origin": "Maputo",
                "destination": "Nacala",
                "cargo_type": "carga_geral",
            },
        )
        create_trip_result = await sync_batch(client, tenant.id, [create_trip_op])
        trip_id = create_trip_result["results"][0]["server_id"]
        assert trip_id is not None, "Trip creation must succeed"

        # Create a delivery_proof on that trip
        create_proof_op = make_operation(
            "delivery_proof",
            "create",
            {
                "trip_id": trip_id,
                "delivered_at": datetime.now(UTC).isoformat(),
                "receiver_name": "Destinatario Teste",
            },
        )
        create_proof_result = await sync_batch(client, tenant.id, [create_proof_op])
        proof_id = create_proof_result["results"][0]["server_id"]
        assert proof_id is not None, "DeliveryProof creation must succeed before update test"

        # Now send an update operation for the delivery proof
        update_op = make_operation(
            "delivery_proof",
            "update",
            {
                "server_id": proof_id,
                "notes": "Comprovante actualizado",
                "client_timestamp": datetime.now(UTC).isoformat(),
            },
        )
        update_result = await sync_batch(client, tenant.id, [update_op])
        result = update_result["results"][0]

    # WILL FAIL: current code returns "unsupported_entity_type_for_update"
    assert result["status"] == "processed", (
        f"Expected 'processed' but got '{result['status']}' with error '{result.get('error_code')}'"
    )


async def test_sync_operation_accepts_client_timestamp():
    """ROADMAP: SyncOperation should accept client_timestamp for clock skew handling.

    Currently SyncOperation schema has no client_timestamp field.
    This test verifies the field is accepted without 422 validation error.
    WILL FAIL if SyncOperation does not have a client_timestamp field.
    """
    tenant, vehicle, driver = await create_driver_tenant()

    async with await create_api_client() as client:
        # Send a create operation with client_timestamp as a top-level field on the operation
        # (not inside payload — this tests the SyncOperation schema itself)
        response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant.id),
            json={
                "device_id": "test-device",
                "operations": [
                    {
                        "local_id": f"local_{uuid4().hex[:8]}",
                        "idempotency_key": f"idem_{uuid4().hex}",
                        "operation": "create",
                        "entity_type": "trip",
                        "client_timestamp": datetime.now(UTC).isoformat(),
                        "payload": {
                            "vehicle_id": str(vehicle.id),
                            "driver_id": str(driver.id),
                            "origin": "Maputo",
                            "destination": "Quelimane",
                        },
                    }
                ],
            },
        )

    # WILL FAIL: Pydantic forbids extra fields unless SyncOperation sets model_config extra="ignore"
    # or explicitly adds client_timestamp field
    assert response.status_code == 200, (
        f"Expected 200 but got {response.status_code}: {response.text}"
    )


async def test_bootstrap_reports_update_operation():
    """AUTH-04: bootstrap must report 'update' in supported_operations after implementation.

    Current behavior: returns ["create"] only — MUST FAIL.
    """
    tenant, vehicle, driver = await create_driver_tenant()

    async with await create_api_client() as client:
        response = await client.get(
            "/api/v1/sync/bootstrap",
            headers=auth_headers(tenant.id),
        )

    assert response.status_code == 200, f"Bootstrap failed: {response.text}"
    data = response.json()

    # WILL FAIL: current bootstrap returns ["create"] only
    assert "update" in data["supported_operations"], (
        f"Expected 'update' in supported_operations but got: {data['supported_operations']}"
    )
