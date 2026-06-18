from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.cargo.models import DeliveryProof
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips import service as trip_service
from app.modules.trips.schemas import TripCreate
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def seed_trip():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Sync {suffix}", slug=f"sync-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"SYNC-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Sync {suffix}",
            phone=f"25884{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.flush()

        trip = await trip_service.create_trip(
            db,
            tenant.id,
            TripCreate(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                origin="Matola",
                destination="Beira",
                cargo_type="Carga geral",
            ),
        )
        return tenant.id, trip["id"]


@pytest.mark.asyncio
async def test_sync_batch_replays_same_idempotency_key_without_duplicate_write() -> None:
    tenant_id, trip_id = await seed_trip()
    idempotency_key = str(uuid4())

    operation = {
        "local_id": "delivery_proof_local_001",
        "idempotency_key": idempotency_key,
        "operation": "create",
        "entity_type": "delivery_proof",
        "payload": {
            "tripId": str(trip_id),
            "documentNumber": "GD-SYNC-001",
            "proofType": "client_discharge_note",
            "clientType": "company",
            "deliveredAt": "2026-08-02T12:00:00+00:00",
            "quantityDelivered": 1,
        },
    }

    async with await create_api_client() as client:
        first_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant_id),
            json={"device_id": "driver-phone-001", "operations": [operation]},
        )
        assert first_response.status_code == 200
        first_result = first_response.json()["results"][0]
        assert first_result["status"] == "processed"
        assert first_result["server_id"] is not None

        replay_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant_id),
            json={"device_id": "driver-phone-001", "operations": [operation]},
        )
        assert replay_response.status_code == 200
        replay_result = replay_response.json()["results"][0]
        assert replay_result["status"] == "processed"
        assert replay_result["server_id"] == first_result["server_id"]
        assert replay_result["message"] == "idempotent_replay"

        conflict_operation = {
            **operation,
            "payload": {
                **operation["payload"],
                "documentNumber": "GD-SYNC-CHANGED",
            },
        }
        conflict_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant_id),
            json={"device_id": "driver-phone-001", "operations": [conflict_operation]},
        )
        assert conflict_response.status_code == 200
        conflict_result = conflict_response.json()["results"][0]
        assert conflict_result["status"] == "conflict"
        assert conflict_result["error_code"] == "idempotency_key_reused"

    async with AsyncSessionLocal() as db:
        proof_count = await db.scalar(
            select(func.count(DeliveryProof.id)).where(
                DeliveryProof.tenant_id == tenant_id,
                DeliveryProof.trip_id == trip_id,
            )
        )
        assert proof_count == 1
