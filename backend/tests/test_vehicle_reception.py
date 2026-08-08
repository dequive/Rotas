from uuid import uuid4

import pytest

from app.core.limiter import limiter
from app.database import AsyncSessionLocal
from app.modules.clients.models import Client
from app.modules.drivers.models import Driver
from app.modules.files.models import File
from app.modules.vehicles.models import Vehicle

limiter.enabled = False


@pytest.fixture
async def workshop_tenant_headers(async_client, grant_product_modules):
    suffix = uuid4().hex[:8]
    reg = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"Oficina Auto {suffix}",
            "company_slug": f"oficina-{suffix}",
            "owner_full_name": "Gestor Oficina",
            "owner_email": f"gestor-{suffix}@example.test",
            "owner_password": "password123",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant"]["id"]
    await grant_product_modules(tenant_id, ["tms", "oficina"])
    return {"Authorization": f"Bearer {token}"}, tenant_id


@pytest.fixture
async def tms_only_tenant_headers(async_client):
    suffix = uuid4().hex[:8]
    reg = await async_client.post(
        "/api/v1/onboarding/register",
        json={
            "company_name": f"TMS Apenas {suffix}",
            "company_slug": f"tms-only-{suffix}",
            "owner_full_name": "Gestor TMS",
            "owner_email": f"tms-only-{suffix}@example.test",
            "owner_password": "password123",
        },
    )
    assert reg.status_code == 201, reg.text
    token = reg.json()["access_token"]
    tenant_id = reg.json()["tenant"]["id"]
    return {"Authorization": f"Bearer {token}"}, tenant_id


@pytest.mark.asyncio
async def test_reception_module_guard_and_crud(
    async_client, workshop_tenant_headers, tms_only_tenant_headers
):
    headers, tenant_id = workshop_tenant_headers
    tms_headers, _ = tms_only_tenant_headers

    # 1. Create Client & Customer Vehicle
    async with AsyncSessionLocal() as db:
        client = Client(
            tenant_id=tenant_id,
            trading_name="Cliente Manuel Silva",
            nuit=f"{uuid4().int % 1000000000:09d}",
            email="manuel@test.com",
        )
        db.add(client)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"AFM-{uuid4().hex[:4].upper()}-MC",
            brand="Toyota",
            model="Hilux",
            ownership_type="customer",
            customer_client_id=client.id,
        )
        db.add(vehicle)

        file_obj = File(
            tenant_id=tenant_id,
            file_type="reception_photo",
            original_name="foto_risco.jpg",
            storage_key=f"keys/{uuid4().hex}",
            mime_type="image/jpeg",
            size_bytes=1024,
            sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        db.add(file_obj)
        await db.commit()
        client_id = client.id
        vehicle_id = vehicle.id
        file_id = file_obj.id

    # 2. TMS-only tenant blocked from /workshop/receptions (403 Forbidden)
    bad_res = await async_client.post(
        "/api/v1/workshop/receptions",
        json={"vehicle_id": str(vehicle_id), "client_id": str(client_id)},
        headers=tms_headers,
    )
    assert bad_res.status_code == 403
    assert bad_res.json()["error"]["code"] == "module_not_subscribed"

    # 3. Create Check-in (VehicleReception)
    res = await async_client.post(
        "/api/v1/workshop/receptions",
        json={
            "vehicle_id": str(vehicle_id),
            "client_id": str(client_id),
            "odometer_at_reception": 45000,
            "reported_issues": "Ruído nos travões dianteiros",
            "visual_condition": "Risco pequeno na porta direita",
            "fuel_level": "half",
        },
        headers=headers,
    )
    assert res.status_code == 201
    rec_data = res.json()
    reception_id = rec_data["id"]
    assert rec_data["reception_number"].startswith("REC-")
    assert rec_data["status"] == "received"

    # 4. Append Photo
    photo_res = await async_client.post(
        f"/api/v1/workshop/receptions/{reception_id}/photos",
        json={"file_id": str(file_id), "caption": "Risco lateral"},
        headers=headers,
    )
    assert photo_res.status_code == 201
    assert photo_res.json()["caption"] == "Risco lateral"

    # 5. Detail view includes photo
    detail_res = await async_client.get(
        f"/api/v1/workshop/receptions/{reception_id}",
        headers=headers,
    )
    assert detail_res.status_code == 200
    assert len(detail_res.json()["photos"]) == 1

    # 6. Status update to in_service
    status_res = await async_client.patch(
        f"/api/v1/workshop/receptions/{reception_id}/status",
        json={"status": "in_service"},
        headers=headers,
    )
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "in_service"

    # 7. Release vehicle (no_service -> returned_no_service)
    release_res = await async_client.post(
        f"/api/v1/workshop/receptions/{reception_id}/release",
        json={
            "odometer_at_release": 45005,
            "release_type": "no_service",
            "notes": "Cliente recusou orçamento preliminar",
        },
        headers=headers,
    )
    assert release_res.status_code == 201
    assert release_res.json()["release_type"] == "no_service"

    # Verify reception status updated to returned_no_service
    detail_res2 = await async_client.get(
        f"/api/v1/workshop/receptions/{reception_id}",
        headers=headers,
    )
    assert detail_res2.json()["status"] == "returned_no_service"


@pytest.mark.asyncio
async def test_customer_vehicle_isolation_from_tms_trips_and_fuel(
    async_client, workshop_tenant_headers
):
    headers, tenant_id = workshop_tenant_headers

    async with AsyncSessionLocal() as db:
        cust_vehicle = Vehicle(
            tenant_id=tenant_id,
            plate=f"CUST-{uuid4().hex[:4].upper()}",
            ownership_type="customer",
        )
        db.add(cust_vehicle)

        driver = Driver(
            tenant_id=tenant_id,
            full_name="Joao Motorista",
            license_number=f"LIC-{uuid4().hex[:6]}",
            status="active",
        )
        db.add(driver)
        await db.commit()
        cust_vehicle_id = cust_vehicle.id
        driver_id = driver.id

    # Trip assignment should fail with 409 Conflict
    trip_res = await async_client.post(
        "/api/v1/trips",
        json={
            "vehicle_id": str(cust_vehicle_id),
            "driver_id": str(driver_id),
            "origin": "Maputo",
            "destination": "Matola",
        },
        headers=headers,
    )
    assert trip_res.status_code == 409
    assert trip_res.json()["error"]["code"] == "invalid_vehicle_ownership"
