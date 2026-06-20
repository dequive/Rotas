"""
E2E offline sync test (Track C — Phase 24).

Simulates a driver completing a full trip workflow offline and submitting the
entire batch when connectivity is restored.  The sync batch must process all
6 entity types that the PWA produces during a real trip:

  1. checklist  — pre-trip inspection
  2. fuel_log   — refuelling stop
  3. load_permit — cargo permission document
  4. cargo_manifest — cargo description
  5. trip_stop  — waypoint (break, border, etc.)
  6. delivery_proof — unloading proof at destination

All 6 operations must return status="processed" with a non-null server_id.

The test uses the dev-test-token bypass so it does not need a real DriverDevice —
see app.core.auth.get_driver_principal for the bypass rule.
"""

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.checklists.models import ChecklistTemplate
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips import service as trip_service
from app.modules.trips.schemas import TripCreate
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def _seed_scenario():
    """Seed tenant + vehicle + driver + checklist template + trip. Return IDs."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"OfflineE2E {suffix}", slug=f"e2e-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"MZ-E2E-{suffix[:4].upper()}",
            fuel_type="gasoleo",
            status="active",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Motorista E2E {suffix}",
            status="active",
        )
        db.add_all([vehicle, driver])
        await db.flush()

        template = ChecklistTemplate(
            tenant_id=tenant.id,
            name="Pre-Trip Check",
            type="pre_trip",
            items=[{"id": "tyres", "label": "Pneus", "type": "ok_fail"}],
        )
        db.add(template)
        await db.flush()

        trip = await trip_service.create_trip(
            db,
            tenant.id,
            TripCreate(
                vehicle_id=vehicle.id,
                driver_id=driver.id,
                origin="Maputo",
                destination="Beira",
                cargo_type="Carga geral",
            ),
        )
        await db.commit()

        return {
            "tenant_id": tenant.id,
            "vehicle_id": vehicle.id,
            "driver_id": driver.id,
            "template_id": template.id,
            "trip_id": trip["id"],
        }


async def test_offline_sync_batch_all_entity_types_processed():
    """
    PWA submits a 6-operation offline batch after reconnection.
    All entity types must return status='processed' with a non-null server_id.
    """
    ids = await _seed_scenario()
    tenant_id = ids["tenant_id"]
    trip_id = str(ids["trip_id"])
    device_id = f"phone-{uuid4().hex[:8]}"

    operations = [
        {
            "local_id": "local_checklist_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "checklist",
            "payload": {
                "vehicleId": str(ids["vehicle_id"]),
                "driverId": str(ids["driver_id"]),
                "templateId": str(ids["template_id"]),
                "type": "pre_trip",
                "responses": {"tyres": "ok"},
                "complete": True,
            },
        },
        {
            "local_id": "local_fuel_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "fuel_log",
            "payload": {
                "vehicleId": str(ids["vehicle_id"]),
                "driverId": str(ids["driver_id"]),
                "fuelDate": _now(),
                "fuelType": "gasoleo",
                "liters": 80.0,
                "totalCost": 7200.0,
                "kmAtRefuel": 42000,
                "stationName": "Galp Inchope",
            },
        },
        {
            "local_id": "local_permit_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "load_permit",
            "payload": {
                "tripId": trip_id,
                "clientName": "Cimentos de Moçambique",
                "origin": "Matola",
                "destination": "Beira",
                "loadState": "loaded",
            },
        },
        {
            "local_id": "local_manifest_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "cargo_manifest",
            "payload": {
                "tripId": trip_id,
                "cargoDescription": "Sacos de cimento 50kg",
                "cargoType": "bulk",
                "grossWeight": 20000.0,
                "packageCount": 400,
            },
        },
        {
            "local_id": "local_stop_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "trip_stop",
            "payload": {
                "tripId": trip_id,
                "stopType": "rest",
                "address": "Posto Inchope",
                "notes": "Paragem obrigatória — controlo policial",
            },
        },
        {
            "local_id": "local_delivery_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "delivery_proof",
            "payload": {
                "tripId": trip_id,
                "proofType": "client_discharge_note",
                "clientType": "company",
                "receiverName": "Armazém Beira",
                "deliveredAt": _now(),
                "cargoCondition": "intact",
                "quantityDelivered": 400.0,
            },
        },
    ]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/sync/batch",
            headers=_headers(tenant_id),
            json={"device_id": device_id, "operations": operations},
        )

    assert response.status_code == 200, response.text
    results = response.json()["results"]
    assert len(results) == 6

    for result in results:
        assert result["status"] == "processed", (
            f"Entity {result['entity_type']} (local_id={result['local_id']}) "
            f"returned status={result['status']!r}: {result.get('message')}"
        )
        assert result["server_id"] is not None, (
            f"Entity {result['entity_type']} returned no server_id"
        )


async def test_offline_sync_batch_idempotent_replay():
    """Replaying the same batch must return same server_ids without duplicates."""
    ids = await _seed_scenario()
    tenant_id = ids["tenant_id"]
    trip_id = str(ids["trip_id"])
    device_id = f"phone-{uuid4().hex[:8]}"
    idempotency_key = str(uuid4())

    operation = {
        "local_id": "local_stop_idem",
        "idempotency_key": idempotency_key,
        "operation": "create",
        "entity_type": "trip_stop",
        "payload": {
            "tripId": trip_id,
            "stopType": "border",
            "address": "Fronteira Machipanda",
        },
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post(
            "/api/v1/sync/batch",
            headers=_headers(tenant_id),
            json={"device_id": device_id, "operations": [operation]},
        )
        replay = await client.post(
            "/api/v1/sync/batch",
            headers=_headers(tenant_id),
            json={"device_id": device_id, "operations": [operation]},
        )

    assert first.status_code == 200, first.text
    assert replay.status_code == 200, replay.text

    first_result = first.json()["results"][0]
    replay_result = replay.json()["results"][0]

    assert first_result["status"] == "processed"
    assert replay_result["status"] == "processed"
    assert replay_result["server_id"] == first_result["server_id"], (
        "Replay must return same server_id"
    )
    assert replay_result["message"] == "idempotent_replay"


async def test_offline_sync_dashboard_token_rejected_on_sync_batch():
    """Manager dashboard token (non-development:user) must be rejected on sync/batch."""
    ids = await _seed_scenario()
    tenant_id = ids["tenant_id"]

    import jwt as _jwt

    from app.config import get_settings
    from app.modules.users.models import User

    settings = get_settings()
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"mgr-{uuid4().hex[:8]}@test.local",
            password_hash="$argon2id$test",
            full_name="Test Manager",
            role="manager",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        mgr_token = _jwt.encode(
            {
                "typ": "access",
                "sub": f"user:{user.id}",
                "role": "manager",
                "scope": "dashboard",
                "tenant_id": str(tenant_id),
                "user_id": str(user.id),
            },
            settings.jwt_secret_key.get_secret_value(),
            algorithm="HS256",
        )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        r = await client.post(
            "/api/v1/sync/batch",
            headers={"Authorization": f"Bearer {mgr_token}", "X-Tenant-Id": str(tenant_id)},
            json={"device_id": "test-device", "operations": []},
        )

    assert r.status_code == 403, r.text
