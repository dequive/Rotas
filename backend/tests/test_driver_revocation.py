"""
Failing test stubs for D-08: backend must return "driver_access_revoked" error code
(not "driver_inactive") when DriverDevice.is_active=False.

The PWA client uses this distinction to know whether to show a "contact manager" screen
(revoked, can't self-recover) vs "log in again" (token expired, self-recoverable).

Test RED criteria:
- test_deactivated_driver_device_returns_driver_access_revoked FAILS because current
  auth.py raises ApiError("driver_inactive", ...) not ApiError("driver_access_revoked", ...)
- test_active_driver_device_succeeds PASSES (sanity check)
"""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.config import get_settings
from app.core.tokens import create_access_token
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver, DriverDevice
from app.modules.tenants.models import Tenant
from app.modules.vehicles.models import Vehicle

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


async def create_api_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def create_driver_and_device() -> tuple[Tenant, Driver, DriverDevice, str]:
    """Create a Tenant, Driver, and DriverDevice (is_active=True).

    Returns (tenant, driver, device, access_token).
    The access_token is a real JWT scoped to driver_app for use in sync requests.
    """
    suffix = uuid4().hex[:8]
    device_id = f"device-test-{suffix}"

    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Revocation Tenant {suffix}", slug=f"revoc-{suffix}")
        db.add(tenant)
        await db.flush()

        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"REV-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Revoc {suffix}",
            phone=f"25884{suffix[:7]}",
            status="active",
        )
        db.add_all([vehicle, driver])
        await db.flush()

        device = DriverDevice(
            tenant_id=tenant.id,
            driver_id=driver.id,
            device_id=device_id,
            device_name="Test Device",
            is_active=True,
        )
        db.add(device)
        await db.commit()

        # Generate a real JWT for this driver/device pair
        access_token, _ = create_access_token(
            tenant_id=tenant.id,
            driver_id=driver.id,
            device_id=device_id,
            scope="driver_app",
        )

        await db.refresh(tenant)
        await db.refresh(driver)
        await db.refresh(device)
        return tenant, driver, device, access_token


async def deactivate_device(device_id_pk: object) -> None:
    """Set DriverDevice.is_active = False by primary key."""
    async with AsyncSessionLocal() as db:
        device = await db.get(DriverDevice, device_id_pk)
        assert device is not None, "Device not found for deactivation"
        device.is_active = False
        await db.commit()


async def test_deactivated_driver_device_returns_driver_access_revoked():
    """D-08: Backend must return driver_access_revoked error code (not driver_inactive) when
    DriverDevice.is_active=False. The client uses this to distinguish revocation from token expiry.

    WILL FAIL: current auth.py raises ApiError("driver_inactive", ...) instead of
    ApiError("driver_access_revoked", ...).
    """
    tenant, driver, device, access_token = await create_driver_and_device()

    # Deactivate the device — simulates a manager revoking driver access from the dashboard
    await deactivate_device(device.id)

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/sync/batch",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Tenant-Id": str(tenant.id),
            },
            json={"device_id": device.device_id, "operations": []},
        )

    assert response.status_code == 401, (
        f"Expected 401 but got {response.status_code}: {response.text}"
    )
    body = response.json()
    # Error envelope: {"error": {"code": ..., "message": ..., "details": ..., "request_id": ...}}
    error_code = body["error"]["code"]
    assert error_code == "driver_access_revoked", (
        f"Expected error code 'driver_access_revoked' but got: {body}"
    )


async def test_active_driver_device_succeeds():
    """D-08: Sanity check — active driver device must NOT be rejected.

    This test SHOULD PASS immediately — it verifies the happy path is not broken.
    """
    tenant, driver, device, access_token = await create_driver_and_device()

    async with await create_api_client() as client:
        response = await client.post(
            "/api/v1/sync/batch",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Tenant-Id": str(tenant.id),
            },
            json={"device_id": device.device_id, "operations": []},
        )

    assert response.status_code == 200, (
        f"Active driver should succeed but got {response.status_code}: {response.text}"
    )
