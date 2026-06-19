import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.errors import ApiError
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.audit.models import AuditLog
from app.modules.drivers.models import Driver
from app.modules.fuel import operations
from app.modules.fuel.models import FuelStockCount
from app.modules.fuel.operations_schemas import FuelTankCreate, VehicleRefuelCreate
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def create_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Fuel Ops {suffix}", slug=f"fuel-ops-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"OPS-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
            current_km=1000,
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Fuel Ops {suffix}",
            phone=f"25884{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant.id, vehicle.id, driver.id


@pytest.mark.asyncio
async def test_fuel_operations_receipt_refuel_and_stock_count_flow() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            tank_response = await client.post(
                "/api/v1/fuel-operations/tanks",
                headers=headers,
                json={
                    "code": "TANK-MATOLA-01",
                    "name": "Tanque principal Matola",
                    "fuel_type": "gasoleo",
                    "capacity_liters": 10000,
                    "minimum_stock_liters": 1000,
                    "location": "Base Matola",
                },
            )
            assert tank_response.status_code == 200
            tank = tank_response.json()
            assert float(tank["current_stock_liters"]) == 0

            purchase_response = await client.post(
                "/api/v1/fuel-operations/purchases",
                headers=headers,
                json={
                    "supplier_name": "Petromoc",
                    "purchase_reference": f"PO-{uuid4().hex[:8]}",
                    "fuel_type": "gasoleo",
                    "ordered_liters": 5000,
                    "unit_price": 92.5,
                    "ordered_at": "2026-06-20T08:00:00+00:00",
                },
            )
            assert purchase_response.status_code == 200
            purchase = purchase_response.json()
            assert purchase["status"] == "pending"

            receipt_before_approval = await client.post(
                "/api/v1/fuel-operations/receipts",
                headers=headers,
                json={
                    "purchase_id": purchase["id"],
                    "tank_id": tank["id"],
                    "received_liters": 5000,
                    "received_at": "2026-06-20T11:00:00+00:00",
                },
            )
            assert receipt_before_approval.status_code == 409
            assert receipt_before_approval.json()["error"]["code"] == "fuel_purchase_not_approved"

            approved = await client.post(
                f"/api/v1/fuel-operations/purchases/{purchase['id']}/approve",
                headers=headers,
            )
            assert approved.status_code == 200
            assert approved.json()["status"] == "approved"

            receipt = await client.post(
                "/api/v1/fuel-operations/receipts",
                headers=headers,
                json={
                    "purchase_id": purchase["id"],
                    "tank_id": tank["id"],
                    "received_liters": 5000,
                    "received_at": "2026-06-20T11:00:00+00:00",
                    "delivery_note_number": "DN-001",
                },
            )
            assert receipt.status_code == 200
            assert receipt.json()["movement_id"] is not None

            duplicate_receipt = await client.post(
                "/api/v1/fuel-operations/receipts",
                headers=headers,
                json={
                    "purchase_id": purchase["id"],
                    "tank_id": tank["id"],
                    "received_liters": 5000,
                    "received_at": "2026-06-20T11:00:00+00:00",
                    "delivery_note_number": "DN-001",
                },
            )
            assert duplicate_receipt.status_code == 409
            assert duplicate_receipt.json()["error"]["code"] == "fuel_receipt_delivery_note_exists"

            trip = await client.post(
                "/api/v1/trips",
                headers=headers,
                json={
                    "vehicle_id": str(vehicle_id),
                    "driver_id": str(driver_id),
                    "origin": "Matola",
                    "destination": "Beira",
                    "cargo_type": "Carga geral",
                },
            )
            assert trip.status_code == 200

            refuel_payload = {
                "tank_id": tank["id"],
                "vehicle_id": str(vehicle_id),
                "driver_id": str(driver_id),
                "trip_id": trip.json()["id"],
                "liters": 120,
                "odometer_reading": 1050,
                "refueled_at": "2026-06-20T12:00:00+00:00",
            }
            refuel = await client.post(
                "/api/v1/fuel-operations/vehicle-refuels",
                headers={**headers, "Idempotency-Key": "vehicle-refuel:trip:001"},
                json=refuel_payload,
            )
            assert refuel.status_code == 200
            assert refuel.json()["movement_id"] is not None
            assert refuel.json()["trip_id"] == trip.json()["id"]
            refuel_replay = await client.post(
                "/api/v1/fuel-operations/vehicle-refuels",
                headers={**headers, "Idempotency-Key": "vehicle-refuel:trip:001"},
                json=refuel_payload,
            )
            assert refuel_replay.status_code == 200
            assert refuel_replay.json()["id"] == refuel.json()["id"]

            movements = await client.get(
                "/api/v1/fuel-operations/movements",
                headers=headers,
                params={"tank_id": tank["id"]},
            )
            assert movements.status_code == 200
            assert [item["direction"] for item in movements.json()] == ["out", "in"]
            assert float(movements.json()[0]["balance_after_liters"]) == 4880
            assert float(movements.json()[0]["unit_cost"]) == 92.5

            insufficient = await client.post(
                "/api/v1/fuel-operations/vehicle-refuels",
                headers=headers,
                json={
                    "tank_id": tank["id"],
                    "vehicle_id": str(vehicle_id),
                    "driver_id": str(driver_id),
                    "liters": 6000,
                    "odometer_reading": 1100,
                    "refueled_at": "2026-06-20T13:00:00+00:00",
                },
            )
            assert insufficient.status_code == 409
            assert insufficient.json()["error"]["code"] == "insufficient_fuel_stock"

            stock_count = await client.post(
                "/api/v1/fuel-operations/stock-counts",
                headers=headers,
                json={
                    "tank_id": tank["id"],
                    "measured_liters": 4800,
                    "counted_at": "2026-06-20T18:00:00+00:00",
                    "notes": "Fecho diário.",
                },
            )
            assert stock_count.status_code == 200
            assert float(stock_count.json()["variance_liters"]) == -80
            assert stock_count.json()["adjustment_status"] == "pending"

            exceptions = await client.get("/api/v1/operational-exceptions", headers=headers)
            assert exceptions.status_code == 200
            assert exceptions.json()[0]["exception_type"] == "fuel_stock_variance"

            board = await client.get("/api/v1/fuel-operations/board", headers=headers)
            assert board.status_code == 200
            assert float(board.json()["summary"]["total_stock_liters"]) == 4880
            assert board.json()["summary"]["stock_adjustments_pending"] == 1

            adjustment = await client.post(
                (
                    "/api/v1/fuel-operations/stock-counts/"
                    f"{stock_count.json()['id']}/approve-adjustment"
                ),
                headers=headers,
                json={"notes": "Ajuste autorizado após reconciliação."},
            )
            assert adjustment.status_code == 200
            assert adjustment.json()["adjustment_status"] == "approved"
            assert adjustment.json()["adjustment_movement_id"] is not None

            board_after_adjustment = await client.get(
                "/api/v1/fuel-operations/board",
                headers=headers,
            )
            assert board_after_adjustment.status_code == 200
            assert float(board_after_adjustment.json()["summary"]["total_stock_liters"]) == 4800
            assert board_after_adjustment.json()["summary"]["stock_adjustments_pending"] == 0

        async with AsyncSessionLocal() as db:
            audit_actions = set(
                (
                    await db.execute(select(AuditLog.action).where(AuditLog.tenant_id == tenant_id))
                ).scalars()
            )
            assert "fuel_movement.recorded" in audit_actions
            assert "vehicle_refuel.created" in audit_actions
            assert "fuel_stock_count.created" in audit_actions
            assert "fuel_stock_adjustment.approved" in audit_actions
            linked_trip = await db.get(Trip, trip.json()["id"])
            assert linked_trip is not None
            assert float(linked_trip.total_fuel_cost) == 11100
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_simultaneous_vehicle_refuels_cannot_overdraw_tank() -> None:
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        suffix = uuid4().hex[:8]
        async with AsyncSessionLocal() as db:
            second_vehicle = Vehicle(
                tenant_id=tenant_id,
                plate=f"CON-{suffix}",
                category="pesado",
                fuel_type="gasoleo",
                current_km=2000,
            )
            second_driver = Driver(
                tenant_id=tenant_id,
                full_name=f"Driver Concurrent {suffix}",
                phone=f"25885{suffix[:7]}",
            )
            db.add_all([second_vehicle, second_driver])
            await db.commit()
            second_vehicle_id = second_vehicle.id
            second_driver_id = second_driver.id

        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            tank = (
                await client.post(
                    "/api/v1/fuel-operations/tanks",
                    headers=headers,
                    json={
                        "code": f"TANK-CON-{suffix}",
                        "name": "Tanque concorrente",
                        "capacity_liters": 5000,
                    },
                )
            ).json()
            purchase = (
                await client.post(
                    "/api/v1/fuel-operations/purchases",
                    headers=headers,
                    json={
                        "supplier_name": "Petromoc",
                        "purchase_reference": f"PO-CON-{suffix}",
                        "ordered_liters": 5000,
                        "unit_price": 90,
                        "ordered_at": "2026-06-21T08:00:00+00:00",
                    },
                )
            ).json()
            approved = await client.post(
                f"/api/v1/fuel-operations/purchases/{purchase['id']}/approve",
                headers=headers,
            )
            assert approved.status_code == 200
            receipt = await client.post(
                "/api/v1/fuel-operations/receipts",
                headers=headers,
                json={
                    "purchase_id": purchase["id"],
                    "tank_id": tank["id"],
                    "received_liters": 5000,
                    "received_at": "2026-06-21T09:00:00+00:00",
                },
            )
            assert receipt.status_code == 200

        async def refuel(vehicle, driver, odometer):
            async with AsyncSessionLocal() as db:
                try:
                    return await operations.create_vehicle_refuel(
                        db,
                        tenant_id,
                        VehicleRefuelCreate(
                            tank_id=tank["id"],
                            vehicle_id=vehicle,
                            driver_id=driver,
                            liters=3000,
                            odometer_reading=odometer,
                            refueled_at=datetime(2026, 6, 21, 10, 0, tzinfo=UTC),
                        ),
                        actor_id=None,
                    )
                except ApiError as exc:
                    await db.rollback()
                    return exc

        results = await asyncio.gather(
            refuel(vehicle_id, driver_id, 1100),
            refuel(second_vehicle_id, second_driver_id, 2100),
        )
        successes = [result for result in results if isinstance(result, dict)]
        conflicts = [result for result in results if isinstance(result, ApiError)]
        assert len(successes) == 1
        assert len(conflicts) == 1
        assert conflicts[0].code == "insufficient_fuel_stock"

        async with await create_api_client() as client:
            board = await client.get("/api/v1/fuel-operations/board", headers=headers)
            assert board.status_code == 200
            assert float(board.json()["summary"]["total_stock_liters"]) == 2000
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")


@pytest.mark.asyncio
async def test_stock_counter_cannot_approve_own_adjustment() -> None:
    try:
        tenant_id, _, _ = await seed_entities()
        actor_id = uuid4()
        async with AsyncSessionLocal() as db:
            tank = await operations.create_tank(
                db,
                tenant_id,
                FuelTankCreate(
                    code=f"TANK-SEG-{uuid4().hex[:8]}",
                    name="Tanque segregação",
                    capacity_liters=1000,
                ),
                actor_id=None,
            )
            count = FuelStockCount(
                tenant_id=tenant_id,
                tank_id=tank["id"],
                theoretical_liters=100,
                measured_liters=90,
                variance_liters=-10,
                counted_at=datetime(2026, 6, 21, 18, 0, tzinfo=UTC),
                counted_by=actor_id,
                adjustment_status="pending",
            )
            db.add(count)
            await db.commit()

            with pytest.raises(ApiError) as exc_info:
                await operations.approve_stock_adjustment(
                    db,
                    tenant_id,
                    count.id,
                    actor_id=actor_id,
                    notes="Tentativa indevida.",
                )
            assert exc_info.value.code == "fuel_stock_adjustment_role_conflict"
    except OperationalError as exc:
        pytest.skip(f"Local Postgres is not available: {exc}")
