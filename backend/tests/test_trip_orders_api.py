import asyncio
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

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


def auth_headers(tenant_id) -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def create_seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Orders {suffix}", slug=f"orders-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"ORD-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Orders {suffix}",
            phone=f"25885{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant.id, vehicle.id, driver.id


async def create_confirmed_order(client: httpx.AsyncClient, headers: dict[str, str]) -> dict:
    response = await client.post(
        "/api/v1/trip-orders",
        headers=headers,
        json={
            "origin": "Matola",
            "destination": "Beira",
            "cargo_type": "Carga geral",
            "requested_pickup_date": "2026-06-15",
            "priority": "high",
            "requires_load_permit": True,
        },
    )
    assert response.status_code == 200
    order = response.json()

    confirm_response = await client.post(
        f"/api/v1/trip-orders/{order['id']}/confirm",
        headers=headers,
        json={"reason": "Cliente confirmou disponibilidade de carga"},
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    return confirm_response.json()


@pytest.mark.asyncio
async def test_trip_order_assignment_creates_planned_trip_and_audit_logs() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            order = await create_confirmed_order(client, headers)

            assign_response = await client.post(
                f"/api/v1/trip-orders/{order['id']}/assign",
                headers=headers,
                json={
                    "vehicle_id": str(vehicle_id),
                    "driver_id": str(driver_id),
                    "reason": "Viatura e motorista disponiveis",
                },
            )
            assert assign_response.status_code == 200
            payload = assign_response.json()
            assert payload["trip_order"]["status"] == "assigned"
            assert payload["trip_order"]["assigned_vehicle_id"] == str(vehicle_id)
            assert payload["trip_order"]["assigned_driver_id"] == str(driver_id)
            assert payload["trip"]["trip_order_id"] == order["id"]
            assert payload["trip"]["status"] == "planned"
            assert payload["trip"]["requires_load_permit"] is True

        async with AsyncSessionLocal() as db:
            trip_count = await db.scalar(
                select(func.count(Trip.id)).where(
                    Trip.tenant_id == tenant_id,
                    Trip.trip_order_id == order["id"],
                )
            )
            assert trip_count == 1

            audit_count = await db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.entity_type.in_(("trip_order", "trip")),
                )
            )
            assert audit_count >= 3
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_trip_order_assignment_blocks_active_vehicle_and_driver_conflict() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()

        async with await create_api_client() as client:
            headers = auth_headers(tenant_id)
            first_order = await create_confirmed_order(client, headers)
            second_order = await create_confirmed_order(client, headers)

            first_assign = await client.post(
                f"/api/v1/trip-orders/{first_order['id']}/assign",
                headers=headers,
                json={"vehicle_id": str(vehicle_id), "driver_id": str(driver_id)},
            )
            assert first_assign.status_code == 200

            second_assign = await client.post(
                f"/api/v1/trip-orders/{second_order['id']}/assign",
                headers=headers,
                json={"vehicle_id": str(vehicle_id), "driver_id": str(driver_id)},
            )
            assert second_assign.status_code == 409
            error = second_assign.json()["error"]
            assert error["code"] == "vehicle_assignment_conflict"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_concurrent_trip_order_assignment_creates_only_one_active_trip() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await create_seed_entities()

        async with await create_api_client() as setup_client:
            headers = auth_headers(tenant_id)
            first_order = await create_confirmed_order(setup_client, headers)
            second_order = await create_confirmed_order(setup_client, headers)

        async def assign(order_id: str) -> httpx.Response:
            async with await create_api_client() as client:
                return await client.post(
                    f"/api/v1/trip-orders/{order_id}/assign",
                    headers=headers,
                    json={
                        "vehicle_id": str(vehicle_id),
                        "driver_id": str(driver_id),
                        "reason": "Concorrencia operacional",
                    },
                )

        responses = await asyncio.gather(assign(first_order["id"]), assign(second_order["id"]))
        statuses = sorted(response.status_code for response in responses)
        assert statuses == [200, 409]
        conflict = next(response for response in responses if response.status_code == 409)
        assert conflict.json()["error"]["code"] in {
            "assignment_conflict",
            "vehicle_assignment_conflict",
            "driver_assignment_conflict",
        }

        async with AsyncSessionLocal() as db:
            active_trip_count = await db.scalar(
                select(func.count(Trip.id)).where(
                    Trip.tenant_id == tenant_id,
                    Trip.vehicle_id == vehicle_id,
                    Trip.driver_id == driver_id,
                    Trip.status.in_(
                        (
                            "planned",
                            "dispatch_pending",
                            "dispatched",
                            "in_progress",
                            "delayed",
                            "incident",
                        )
                    ),
                )
            )
            assert active_trip_count == 1
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
