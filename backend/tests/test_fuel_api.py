from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import func, select

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.fuel.models import FuelLog
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
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


async def seed_fuel_entities(
    *,
    current_km: int = 1000,
    avg_consumption_target: float | None = 30,
):
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Fuel {suffix}", slug=f"fuel-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"FUEL-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            current_km=current_km,
            avg_consumption_target=avg_consumption_target,
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Fuel {suffix}",
            phone=f"25886{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        await db.refresh(tenant)
        await db.refresh(vehicle)
        await db.refresh(driver)
        return tenant, vehicle, driver


def fuel_payload(vehicle_id, driver_id, *, fuel_date: str, km: int, liters: float, cost: float):
    return {
        "vehicle_id": str(vehicle_id),
        "driver_id": str(driver_id),
        "fuel_date": fuel_date,
        "station_name": "Petromoc Matola",
        "fuel_type": "gasoleo",
        "liters": liters,
        "price_per_liter": cost / liters,
        "total_cost": cost,
        "km_at_refuel": km,
        "payment_method": "mpesa",
        "payment_reference": f"MP-{uuid4().hex[:8]}",
    }


@pytest.mark.asyncio
async def test_fuel_log_rejects_trip_from_another_tenant() -> None:
    tenant, vehicle, driver = await seed_fuel_entities()
    foreign_tenant, foreign_vehicle, foreign_driver = await seed_fuel_entities()
    async with AsyncSessionLocal() as db:
        foreign_trip = Trip(
            tenant_id=foreign_tenant.id,
            vehicle_id=foreign_vehicle.id,
            driver_id=foreign_driver.id,
            origin="Beira",
            destination="Tete",
            status="in_progress",
        )
        db.add(foreign_trip)
        await db.commit()
        foreign_trip_id = foreign_trip.id

    payload = fuel_payload(
        vehicle.id,
        driver.id,
        fuel_date="2026-08-01T08:00:00+00:00",
        km=1000,
        liters=30,
        cost=3000,
    )
    payload["trip_id"] = str(foreign_trip_id)
    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/fuel",
            headers=auth_headers(tenant.id),
            json=payload,
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "trip_not_found"


@pytest.mark.asyncio
async def test_fuel_log_flow_calculates_consumption_and_anomalies() -> None:
    tenant, vehicle, driver = await seed_fuel_entities()

    async with await create_api_client() as client:
        first_payload = fuel_payload(
            vehicle.id,
            driver.id,
            fuel_date="2026-08-01T08:00:00+00:00",
            km=1000,
            liters=30,
            cost=3000,
        )
        first_response = await client.post(
            "/api/v1/fuel",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "fuel-log:first:001"},
            json=first_payload,
        )
        assert first_response.status_code == 200
        first = first_response.json()
        assert first["km_since_last"] is None
        assert first["consumption_l_per_100km"] is None
        assert first["flagged"] is False
        first_replay = await client.post(
            "/api/v1/fuel",
            headers={**auth_headers(tenant.id), "Idempotency-Key": "fuel-log:first:001"},
            json=first_payload,
        )
        assert first_replay.status_code == 200
        assert first_replay.json()["id"] == first["id"]

        second_response = await client.post(
            "/api/v1/fuel",
            headers=auth_headers(tenant.id),
            json=fuel_payload(
                vehicle.id,
                driver.id,
                fuel_date="2026-08-02T08:00:00+00:00",
                km=1100,
                liters=40,
                cost=4000,
            ),
        )
        assert second_response.status_code == 200
        second = second_response.json()
        assert second["km_since_last"] == 100
        assert float(second["consumption_l_per_100km"]) == 40
        assert second["flagged"] is True

        list_response = await client.get(
            "/api/v1/fuel",
            headers=auth_headers(tenant.id),
            params={"vehicle_id": str(vehicle.id)},
        )
        assert list_response.status_code == 200
        assert [item["id"] for item in list_response.json()] == [second["id"], first["id"]]

        stats_response = await client.get(
            "/api/v1/fuel/stats",
            headers=auth_headers(tenant.id),
            params={"vehicle_id": str(vehicle.id)},
        )
        assert stats_response.status_code == 200
        stats = stats_response.json()
        assert stats["count"] == 2
        assert float(stats["total_liters"]) == 70
        assert float(stats["total_cost"]) == 7000
        assert stats["total_km"] == 100
        assert float(stats["cost_per_km"]) == 70

        anomalies_response = await client.get(
            "/api/v1/fuel/anomalies",
            headers=auth_headers(tenant.id),
        )
        assert anomalies_response.status_code == 200
        assert [item["id"] for item in anomalies_response.json()] == [second["id"]]

        verify_response = await client.patch(
            f"/api/v1/fuel/{second['id']}/verify",
            headers=auth_headers(tenant.id),
            json={"is_verified": True, "flagged": False},
        )
        assert verify_response.status_code == 200
        verified = verify_response.json()
        assert verified["is_verified"] is True
        assert verified["flagged"] is False
        assert verified["verified_at"] is not None

    async with AsyncSessionLocal() as db:
        audit_rows = await db.execute(
            select(AuditLog.action).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_id == UUID(second["id"]),
            )
        )
        assert set(audit_rows.scalars()) == {"fuel_log.created", "fuel_log.verified"}

        vehicle_audit_rows = await db.execute(
            select(AuditLog.action).where(
                AuditLog.tenant_id == tenant.id,
                AuditLog.entity_id == vehicle.id,
                AuditLog.action == "vehicle.odometer_updated_from_fuel",
            )
        )
        assert len(list(vehicle_audit_rows.scalars())) == 1


@pytest.mark.asyncio
async def test_fuel_log_rejects_odometer_regression() -> None:
    tenant, vehicle, driver = await seed_fuel_entities(current_km=5000)

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/fuel",
            headers=auth_headers(tenant.id),
            json=fuel_payload(
                vehicle.id,
                driver.id,
                fuel_date="2026-08-01T08:00:00+00:00",
                km=4999,
                liters=20,
                cost=2000,
            ),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "odometer_regression"


@pytest.mark.asyncio
async def test_sync_fuel_log_create_is_idempotent() -> None:
    tenant, vehicle, driver = await seed_fuel_entities(avg_consumption_target=None)

    async with await create_api_client() as client:
        receipt_response = await client.post(
            "/api/v1/files/upload",
            headers=auth_headers(tenant.id),
            data={"file_type": "receipt", "entity_type": "fuel_log"},
            files={"upload": ("receipt.jpg", b"receipt-image", "image/jpeg")},
        )
        assert receipt_response.status_code == 200

        odometer_response = await client.post(
            "/api/v1/files/upload",
            headers=auth_headers(tenant.id),
            data={"file_type": "photo", "entity_type": "fuel_log"},
            files={"upload": ("odometer.jpg", b"odometer-image", "image/jpeg")},
        )
        assert odometer_response.status_code == 200

        receipt_file_id = receipt_response.json()["id"]
        odometer_file_id = odometer_response.json()["id"]
        operation = {
            "local_id": "fuel_local_001",
            "idempotency_key": str(uuid4()),
            "operation": "create",
            "entity_type": "fuel_log",
            "payload": {
                "vehicleId": str(vehicle.id),
                "driverId": str(driver.id),
                "fuelDate": "2026-08-01T08:00:00+00:00",
                "stationName": "TotalEnergies Beira",
                "fuelType": "gasoleo",
                "liters": 25,
                "pricePerLiter": 100,
                "totalCost": 2500,
                "kmAtRefuel": 1000,
                "paymentMethod": "dinheiro",
                "receiptFileId": receipt_file_id,
                "odometerFileId": odometer_file_id,
            },
        }

        first_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant.id),
            json={"device_id": "driver-phone-fuel", "operations": [operation]},
        )
        assert first_response.status_code == 200
        first = first_response.json()["results"][0]
        assert first["status"] == "processed"

        replay_response = await client.post(
            "/api/v1/sync/batch",
            headers=auth_headers(tenant.id),
            json={"device_id": "driver-phone-fuel", "operations": [operation]},
        )
        assert replay_response.status_code == 200
        replay = replay_response.json()["results"][0]
        assert replay["server_id"] == first["server_id"]
        assert replay["message"] == "idempotent_replay"

    async with AsyncSessionLocal() as db:
        fuel_log = await db.scalar(select(FuelLog).where(FuelLog.tenant_id == tenant.id))
        assert fuel_log is not None
        assert str(fuel_log.receipt_file_id) == receipt_file_id
        assert str(fuel_log.odometer_file_id) == odometer_file_id

        count = await db.scalar(
            select(func.count(FuelLog.id)).where(
                FuelLog.tenant_id == tenant.id,
                FuelLog.vehicle_id == vehicle.id,
            )
        )
        assert count == 1
