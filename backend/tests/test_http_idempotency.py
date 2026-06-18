from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant HTTP Idem {suffix}", slug=f"http-idem-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(tenant_id=tenant.id, plate=f"IDEM-{suffix}", category="pesado")
        driver = Driver(tenant_id=tenant.id, full_name="Driver Idem")
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant, vehicle, driver


def headers(tenant_id, key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
        "Idempotency-Key": key,
    }


@pytest.mark.asyncio
async def test_trip_creation_replays_http_idempotency_key_and_rejects_payload_change() -> None:
    tenant, vehicle, driver = await seed_entities()
    payload = {
        "vehicle_id": str(vehicle.id),
        "driver_id": str(driver.id),
        "origin": "Maputo",
        "destination": "Matola",
    }
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        first = await client.post(
            "/api/v1/trips",
            headers=headers(tenant.id, "trip:idem:1"),
            json=payload,
        )
        assert first.status_code == 200
        replay = await client.post(
            "/api/v1/trips",
            headers=headers(tenant.id, "trip:idem:1"),
            json=payload,
        )
        assert replay.status_code == 200
        assert replay.json()["id"] == first.json()["id"]

        conflict = await client.post(
            "/api/v1/trips",
            headers=headers(tenant.id, "trip:idem:1"),
            json={**payload, "destination": "Boane"},
        )
        assert conflict.status_code == 409

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(Trip.id)).where(Trip.tenant_id == tenant.id)) == 1
        audit_count = await db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_type == "trip",
                AuditLog.action == "trip.created",
            )
        )
        assert audit_count == 1
