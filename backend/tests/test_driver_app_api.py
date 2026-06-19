from uuid import uuid4

import pytest

from app.core.tokens import create_access_token
from app.modules.checklists.models import ChecklistTemplate
from app.modules.drivers.models import Driver, DriverDevice
from app.modules.vehicles.models import Vehicle


@pytest.fixture
async def driver_app_context(db, tenant_id):
    suffix = uuid4().hex[:8]
    device_id = f"driver-device-{suffix}"
    driver = Driver(
        tenant_id=tenant_id,
        full_name="Driver App Test",
        phone="840000000",
        status="active",
    )
    other_driver = Driver(
        tenant_id=tenant_id,
        full_name="Other Driver",
        phone="840000001",
        status="active",
    )
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"DRV-{suffix[:4]}",
        brand="Toyota",
        model="Dyna",
        status="active",
        current_km=1200,
    )
    template = ChecklistTemplate(
        tenant_id=tenant_id,
        name="Pre partida padrao",
        type="pre_partida",
        is_active=True,
        items=[
            {
                "id": "oil",
                "label": "Nivel de oleo",
                "type": "boolean",
                "is_blocking": True,
            }
        ],
    )
    db.add_all([driver, other_driver, vehicle, template])
    await db.flush()

    device = DriverDevice(
        tenant_id=tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        device_name="ROTAS App",
        is_active=True,
    )
    db.add(device)
    await db.commit()

    token, _ = create_access_token(
        tenant_id=tenant_id,
        driver_id=driver.id,
        device_id=device_id,
        scope="driver_app",
    )

    return {
        "headers": {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": str(tenant_id),
        },
        "driver": driver,
        "other_driver": other_driver,
        "vehicle": vehicle,
        "template": template,
    }


@pytest.mark.asyncio
async def test_driver_bootstrap_uses_driver_contract(async_client, driver_app_context):
    response = await async_client.get(
        "/api/v1/driver/bootstrap",
        headers=driver_app_context["headers"],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["profile"]["driver_id"] == str(driver_app_context["driver"].id)
    assert data["activeTrip"] is None
    assert [template["name"] for template in data["checklistTemplates"]] == [
        driver_app_context["template"].name
    ]
    assert [vehicle["plate"] for vehicle in data["vehicles"]] == [
        driver_app_context["vehicle"].plate
    ]


@pytest.mark.asyncio
async def test_dashboard_token_cannot_use_driver_contract(async_client, viewer_headers):
    response = await async_client.get(
        "/api/v1/driver/bootstrap",
        headers=viewer_headers,
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_scope_required"


@pytest.mark.asyncio
async def test_driver_can_create_own_trip(async_client, driver_app_context):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["driver"].id),
            "origin": "Maputo",
            "destination": "Matola",
            "cargo_type": "geral",
            "load_state": "loaded",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["driver_id"] == str(driver_app_context["driver"].id)
    assert data["vehicle_id"] == str(driver_app_context["vehicle"].id)
    assert data["origin"] == "Maputo"


@pytest.mark.asyncio
async def test_driver_cannot_create_trip_for_another_driver(async_client, driver_app_context):
    response = await async_client.post(
        "/api/v1/driver/trips",
        headers=driver_app_context["headers"],
        json={
            "vehicle_id": str(driver_app_context["vehicle"].id),
            "driver_id": str(driver_app_context["other_driver"].id),
            "origin": "Maputo",
            "destination": "Matola",
        },
    )

    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "driver_mismatch"
