import asyncio
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.core.idempotency import execute_http_idempotent
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.outbox.models import OutboxEvent
from app.modules.sync.models import IdempotencyKey
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


@pytest.mark.asyncio
async def test_failed_handler_rolls_back_reservation_and_business_mutation() -> None:
    tenant, _, _ = await seed_entities()
    plate = f"ROLLBACK-{uuid4().hex[:8]}"
    auxiliary_slug = f"auxiliary-{uuid4().hex[:8]}"
    rollback_marker = uuid4().hex

    async with AsyncSessionLocal() as db:

        async def failing_handler() -> dict:
            async with AsyncSessionLocal() as auxiliary_db:
                auxiliary_db.add(Tenant(name="Auxiliary commit", slug=auxiliary_slug))
                await auxiliary_db.commit()
            db.add(Vehicle(tenant_id=tenant.id, plate=plate, category="pesado"))
            db.add(
                AuditLog(
                    tenant_id=tenant.id,
                    action=f"test.rollback.{rollback_marker}",
                    entity_type="vehicle",
                    new_values={"plate": plate},
                )
            )
            db.add(
                OutboxEvent(
                    tenant_id=tenant.id,
                    aggregate_type="vehicle",
                    event_type=f"test.rollback.{rollback_marker}",
                    payload={"plate": plate},
                )
            )
            await db.commit()
            raise RuntimeError("simulated failure after service commit")

        with pytest.raises(RuntimeError, match="simulated failure"):
            await execute_http_idempotent(
                db,
                tenant_id=tenant.id,
                idempotency_key="vehicle:rollback:1",
                operation="vehicles.create",
                entity_type="vehicle",
                payload={"plate": plate},
                handler=failing_handler,
            )

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(Vehicle.id)).where(Vehicle.plate == plate)) == 0
        assert (
            await db.scalar(
                select(func.count(IdempotencyKey.id)).where(
                    IdempotencyKey.tenant_id == tenant.id,
                    IdempotencyKey.idempotency_key == "vehicle:rollback:1",
                )
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.tenant_id == tenant.id,
                    AuditLog.action == f"test.rollback.{rollback_marker}",
                )
            )
            == 0
        )
        assert (
            await db.scalar(
                select(func.count(OutboxEvent.id)).where(
                    OutboxEvent.tenant_id == tenant.id,
                    OutboxEvent.event_type == f"test.rollback.{rollback_marker}",
                )
            )
            == 0
        )
        assert await db.scalar(select(func.count(Tenant.id)).where(Tenant.slug == auxiliary_slug)) == 1


@pytest.mark.asyncio
async def test_concurrent_same_key_executes_handler_once_and_replays() -> None:
    tenant, _, _ = await seed_entities()
    plate = f"CONCURRENT-{uuid4().hex[:8]}"
    handler_started = asyncio.Event()
    executions = 0

    async def run_request() -> dict:
        nonlocal executions
        async with AsyncSessionLocal() as db:

            async def handler() -> dict:
                nonlocal executions
                executions += 1
                vehicle = Vehicle(tenant_id=tenant.id, plate=plate, category="pesado")
                db.add(vehicle)
                await db.commit()
                handler_started.set()
                await asyncio.sleep(0.2)
                return {"id": str(vehicle.id), "plate": vehicle.plate}

            return await execute_http_idempotent(
                db,
                tenant_id=tenant.id,
                idempotency_key="vehicle:concurrent:1",
                operation="vehicles.create",
                entity_type="vehicle",
                payload={"plate": plate},
                handler=handler,
            )

    first_task = asyncio.create_task(run_request())
    await handler_started.wait()
    second_task = asyncio.create_task(run_request())
    first, second = await asyncio.gather(first_task, second_task)

    assert executions == 1
    assert second == first
    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count(Vehicle.id)).where(Vehicle.plate == plate)) == 1
