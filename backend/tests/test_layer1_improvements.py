import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.main import app
from app.modules.drivers.models import Driver
from app.modules.vehicles.models import Vehicle


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.delete = AsyncMock(return_value=1)
    redis.keys = AsyncMock(return_value=[])
    return redis


@pytest.mark.asyncio
async def test_vehicle_plate_normalization(async_client, db, tenant_id, auth_headers):
    # Test creation plate normalization
    payload = {
        "plate": "   mc-88-29-gp   ",
        "chassis": "1234567890",
        "brand": "Toyota",
        "model": "Hino",
        "year": 2020,
        "category": "pesado",
        "fuel_type": "gasoleo",
        "current_km": 100,
    }
    response = await async_client.post("/api/v1/vehicles", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["plate"] == "MC-88-29-GP"

    # Verify database has the normalized plate
    vehicle_id = data["id"]
    vehicle = await db.get(Vehicle, uuid.UUID(vehicle_id))
    assert vehicle.plate == "MC-88-29-GP"

    # Test patch plate normalization
    patch_payload = {"plate": "   lh-00-11-mc   "}
    patch_response = await async_client.patch(
        f"/api/v1/vehicles/{vehicle_id}", json=patch_payload, headers=auth_headers
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["plate"] == "LH-00-11-MC"

    # Verify db updated to normalized value
    await db.refresh(vehicle)
    assert vehicle.plate == "LH-00-11-MC"


@pytest.mark.asyncio
async def test_driver_data_normalization_and_validation(async_client, db, tenant_id, auth_headers):
    # Test valid driver creation (emails/phones normalized)
    payload = {
        "full_name": "António Muchanga",
        "phone": "  84 999 1111  ",  # 9 digits starting with Moz operator
        "email": "   ANTONIO@Muchanga.co.mz   ",
        "emergency_contact_name": "Maria Muchanga",
        "emergency_contact_phone": "  82-999-2222  ",
        "employment_type": "full_time",
    }
    response = await async_client.post("/api/v1/drivers", json=payload, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+258849991111"
    assert data["email"] == "antonio@muchanga.co.mz"
    assert data["emergency_contact_phone"] == "+258829992222"

    # Test invalid email format
    invalid_email = payload.copy()
    invalid_email["email"] = "invalidemail"
    response = await async_client.post("/api/v1/drivers", json=invalid_email, headers=auth_headers)
    assert response.status_code == 422

    # Test invalid phone format
    invalid_phone = payload.copy()
    invalid_phone["phone"] = "12345"
    response = await async_client.post("/api/v1/drivers", json=invalid_phone, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_driver_document_expiration_validation(async_client, db, tenant_id, auth_headers):
    # Past expiration date on create
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    payload = {
        "full_name": "António Muchanga",
        "phone": "849991111",
        "email": "antonio@muchanga.co.mz",
        "license_valid_until": yesterday,
    }
    response = await async_client.post("/api/v1/drivers", json=payload, headers=auth_headers)
    assert response.status_code == 422
    assert "Date must be today or in the future" in response.text

    # Past expiration date on renew
    driver_id = uuid.uuid4()
    # seed driver
    async with db.begin_nested():
        d = Driver(id=driver_id, tenant_id=tenant_id, full_name="Driver Test", status="active")
        db.add(d)
        await db.commit()

    renewal_payload = {"valid_until": yesterday}
    response = await async_client.post(
        f"/api/v1/drivers/{driver_id}/documents/license/renew",
        json=renewal_payload,
        headers=auth_headers,
    )
    assert response.status_code == 422
    assert "Date must be today or in the future" in response.text


@pytest.mark.asyncio
async def test_vehicle_insurance_dates_validation(async_client, db, tenant_id, auth_headers):
    # Insurance valid_until <= valid_from
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # seed vehicle
    vehicle_id = uuid.uuid4()
    async with db.begin_nested():
        v = Vehicle(id=vehicle_id, tenant_id=tenant_id, plate="MZ-99-99-GP", status="active")
        db.add(v)
        await db.commit()

    insurance_payload = {
        "policy_number": "POL-123",
        "insurer": "Fidelidade",
        "coverage_type": "comprehensive",
        "valid_from": today,
        "valid_until": yesterday,
    }
    response = await async_client.post(
        f"/api/v1/vehicles/{vehicle_id}/insurance", json=insurance_payload, headers=auth_headers
    )
    assert response.status_code == 422
    assert "Insurance valid_until must be after valid_from" in response.text


@pytest.mark.asyncio
async def test_cache_invalidation_triggered(async_client, db, tenant_id, auth_headers, mock_redis):
    # Attach mock redis to app state
    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock_redis
    try:
        # Mutate driver
        payload = {
            "full_name": "António Muchanga",
            "phone": "849991111",
            "email": "antonio@muchanga.co.mz",
        }
        response = await async_client.post("/api/v1/drivers", json=payload, headers=auth_headers)
        assert response.status_code == 200

        # Verify redis.delete was called for the tenant limits key
        mock_redis.delete.assert_any_call(f"tenant:limits:{tenant_id}")
    finally:
        app.state.redis = old_redis
