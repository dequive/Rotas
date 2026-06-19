# ruff: noqa: E402
import os
import uuid
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

os.environ.setdefault("DEV_TEST_TOKEN", "test-token")

from app.database import AsyncSessionLocal, engine, import_all_models  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.drivers.models import Driver  # noqa: E402
from app.modules.tenants.models import Tenant  # noqa: E402
from app.modules.vehicles.models import Vehicle  # noqa: E402
from app.modules.workshop.models import SparePartInventory, SparePartMovement  # noqa: E402

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
        tenant = Tenant(name=f"Tenant Serial {suffix}", slug=f"serial-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"SRL-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Serial {suffix}",
            phone=f"25889{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant.id, vehicle.id, driver.id


async def seed_spare_part(
    tenant_id: uuid.UUID,
    current_qty: Decimal = Decimal("10.00"),
    min_qty: Decimal = Decimal("2.00"),
) -> str:
    """Insert a SparePartInventory directly in DB and return part ID as string."""
    async with AsyncSessionLocal() as db:
        part = SparePartInventory(
            tenant_id=tenant_id,
            sku=f"SKU-{uuid4().hex[:6]}",
            name="Test Part",
            unit="unit",
            current_quantity=current_qty,
            minimum_quantity=min_qty,
            average_unit_cost=Decimal("50.00"),
            status="active",
        )
        db.add(part)
        await db.commit()
        await db.refresh(part)
        return str(part.id)


@pytest.mark.asyncio
async def test_register_serial_201() -> None:
    """POST /api/v1/workshop/spare-parts/{part_id}/serials returns 201 with status=in_stock."""
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        part_id = await seed_spare_part(tenant_id)
        serial_num = f"SN-{uuid4().hex[:8]}"

        async with await create_api_client() as client:
            resp = await client.post(
                f"/api/v1/workshop/spare-parts/{part_id}/serials",
                headers=headers,
                json={"serial_number": serial_num},
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert data["serial_number"] == serial_num
            assert data["status"] == "in_stock"
            assert data["vehicle_id"] is None
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_duplicate_serial_409() -> None:
    """Registering same serial_number twice under same tenant returns 409."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        part_id = await seed_spare_part(tenant_id)
        serial_num = f"SN-UNIQUE-{uuid4().hex[:6]}"

        async with await create_api_client() as client:
            r1 = await client.post(
                f"/api/v1/workshop/spare-parts/{part_id}/serials",
                headers=headers,
                json={"serial_number": serial_num},
            )
            assert r1.status_code == 201, r1.text

            r2 = await client.post(
                f"/api/v1/workshop/spare-parts/{part_id}/serials",
                headers=headers,
                json={"serial_number": serial_num},
            )
            assert r2.status_code == 409, (
                f"Expected 409 for duplicate serial, got {r2.status_code}: {r2.text}"
            )
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_install_serial_sets_installed() -> None:
    """POST /api/v1/workshop/spare-parts/serials/{serial_id}/install sets status=installed."""
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        part_id = await seed_spare_part(tenant_id)
        serial_num = f"SN-INSTALL-{uuid4().hex[:6]}"

        async with await create_api_client() as client:
            reg = await client.post(
                f"/api/v1/workshop/spare-parts/{part_id}/serials",
                headers=headers,
                json={"serial_number": serial_num},
            )
            assert reg.status_code == 201, reg.text
            serial_id = reg.json()["id"]

            install_resp = await client.post(
                f"/api/v1/workshop/spare-parts/serials/{serial_id}/install",
                headers=headers,
                json={"vehicle_id": str(vehicle_id)},
            )
            assert install_resp.status_code == 200, install_resp.text
            data = install_resp.json()
            assert data["status"] == "installed"
            assert str(data["vehicle_id"]) == str(vehicle_id)
            assert data["installed_at"] is not None

        # Verify SparePartMovement was created with direction=out and movement_type=serial_install
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(SparePartMovement).where(
                    SparePartMovement.tenant_id == tenant_id,
                    SparePartMovement.movement_type == "serial_install",
                    SparePartMovement.direction == "out",
                )
            )
            movements = result.scalars().all()
            assert len(movements) == 1, f"Expected 1 serial_install movement, got {len(movements)}"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_installed_parts_for_vehicle() -> None:
    """GET /api/v1/workshop/vehicles/{vehicle_id}/installed-parts includes installed item."""
    try:
        tenant_id, vehicle_id, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        part_id = await seed_spare_part(tenant_id)
        serial_num = f"SN-VEH-{uuid4().hex[:6]}"

        async with await create_api_client() as client:
            reg = await client.post(
                f"/api/v1/workshop/spare-parts/{part_id}/serials",
                headers=headers,
                json={"serial_number": serial_num},
            )
            assert reg.status_code == 201, reg.text
            serial_id = reg.json()["id"]

            await client.post(
                f"/api/v1/workshop/spare-parts/serials/{serial_id}/install",
                headers=headers,
                json={"vehicle_id": str(vehicle_id)},
            )

            installed_resp = await client.get(
                f"/api/v1/workshop/vehicles/{vehicle_id}/installed-parts",
                headers=headers,
            )
            assert installed_resp.status_code == 200, installed_resp.text
            parts = installed_resp.json()
            assert len(parts) >= 1
            assert any(p["serial_number"] == serial_num for p in parts)
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_low_stock_endpoint() -> None:
    """Part with current_qty=1, min_qty=5 appears in GET /api/v1/workshop/spare-parts/low-stock."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)

        # Seed a low-stock part directly (current < minimum)
        async with AsyncSessionLocal() as db:
            low_part = SparePartInventory(
                tenant_id=tenant_id,
                sku=f"LOW-SKU-{uuid4().hex[:6]}",
                name="Low Stock Part",
                current_quantity=Decimal("1.00"),
                minimum_quantity=Decimal("5.00"),
                average_unit_cost=Decimal("10.00"),
                status="active",
            )
            db.add(low_part)
            await db.commit()
            low_part_sku = low_part.sku

        async with await create_api_client() as client:
            resp = await client.get("/api/v1/workshop/spare-parts/low-stock", headers=headers)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert "items" in data
            skus = [item["sku"] for item in data["items"]]
            assert low_part_sku in skus, f"Low stock part not in response: {skus}"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_serial_cross_tenant_isolation() -> None:
    """Serial registered under tenant A is not returned when listing as tenant B."""
    try:
        tenant_a_id, vehicle_a_id, _ = await seed_entities()
        tenant_b_id, vehicle_b_id, _ = await seed_entities()
        headers_a = auth_headers(tenant_a_id)
        headers_b = auth_headers(tenant_b_id)

        # Seed a part for tenant A
        part_id_a = await seed_spare_part(tenant_a_id)
        serial_num = f"SN-CROSS-{uuid4().hex[:6]}"

        async with await create_api_client() as client:
            reg = await client.post(
                f"/api/v1/workshop/spare-parts/{part_id_a}/serials",
                headers=headers_a,
                json={"serial_number": serial_num},
            )
            assert reg.status_code == 201, reg.text
            serial_id_a = reg.json()["id"]

            # Install on vehicle A
            await client.post(
                f"/api/v1/workshop/spare-parts/serials/{serial_id_a}/install",
                headers=headers_a,
                json={"vehicle_id": str(vehicle_a_id)},
            )

            # Tenant B should get 0 installed parts for vehicle A (or 404)
            resp_b = await client.get(
                f"/api/v1/workshop/vehicles/{vehicle_a_id}/installed-parts",
                headers=headers_b,
            )
            # Either 404 (vehicle not found for tenant B) or empty list
            if resp_b.status_code == 200:
                parts = resp_b.json()
                serials_b = [p["serial_number"] for p in parts]
                assert serial_num not in serials_b, (
                    f"Serial {serial_num} from tenant A leaked into tenant B response"
                )
            else:
                assert resp_b.status_code in (403, 404)
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")
