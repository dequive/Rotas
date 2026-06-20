"""
RBAC deny-matrix tests (Track D — Phase 24).

Verifies that roles below the required threshold get 403 on write/admin endpoints
across the five critical domains: trips, vehicles, drivers, files, billing.
Also verifies that driver_app-scoped tokens cannot access dashboard endpoints.

Roles under test:
  viewer   — DASHBOARD_ROLES but NOT WRITE_ROLES/ADMIN_ROLES
  mechanic — DASHBOARD_ROLES + WORKSHOP_WRITE_ROLES but NOT WRITE_ROLES for core domains
"""

from uuid import uuid4

import httpx
import jwt as _jwt
import pytest

from app.config import get_settings
from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver, DriverDevice
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


async def _make_tenant() -> Tenant:
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"RBAC-Deny-{suffix}", slug=f"rbac-{suffix}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        return tenant


async def _dashboard_headers(tenant_id, role: str) -> dict[str, str]:
    """Create a real User with the given role and return JWT headers."""
    settings = get_settings()
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"{role}-{uuid4().hex[:8]}@rbac.test",
            password_hash="$argon2id$test",
            full_name=f"RBAC {role.title()} Tester",
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    token = _jwt.encode(
        {
            "typ": "access",
            "sub": f"user:{user_id}",
            "role": role,
            "scope": "dashboard",
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


async def _driver_app_headers(tenant_id) -> dict[str, str]:
    """Create Driver + DriverDevice records and return driver_app JWT headers."""
    settings = get_settings()
    device_id = str(uuid4())
    async with AsyncSessionLocal() as db:
        driver = Driver(
            tenant_id=tenant_id,
            full_name="RBAC Driver Tester",
            status="active",
        )
        db.add(driver)
        await db.flush()

        device = DriverDevice(
            tenant_id=tenant_id,
            driver_id=driver.id,
            device_id=device_id,
            device_name="Test Device",
            is_active=True,
        )
        db.add(device)
        await db.commit()
        await db.refresh(driver)
        driver_id = driver.id

    token = _jwt.encode(
        {
            "typ": "access",
            "sub": f"driver:{driver_id}",
            "role": None,
            "scope": "driver_app",
            "tenant_id": str(tenant_id),
            "driver_id": str(driver_id),
            "device_id": device_id,
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant_id)}


_transport = httpx.ASGITransport(app=app)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=_transport, base_url="http://testserver")


# ── RBAC-01: viewer/mechanic cannot create/update/delete vehicles ─────────────


async def test_viewer_cannot_create_vehicle():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.post(
            "/api/v1/vehicles",
            headers=headers,
            json={"plate": f"MZ-V-{uuid4().hex[:4].upper()}", "fuel_type": "diesel"},
        )
    assert r.status_code == 403, r.text


async def test_mechanic_cannot_create_vehicle():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "mechanic")
    async with _client() as c:
        r = await c.post(
            "/api/v1/vehicles",
            headers=headers,
            json={"plate": f"MZ-M-{uuid4().hex[:4].upper()}", "fuel_type": "diesel"},
        )
    assert r.status_code == 403, r.text


async def test_viewer_cannot_update_vehicle():
    tenant = await _make_tenant()
    viewer = await _dashboard_headers(tenant.id, "viewer")
    admin = await _dashboard_headers(tenant.id, "admin")
    async with _client() as c:
        r = await c.post(
            "/api/v1/vehicles",
            headers=admin,
            json={"plate": f"MZ-A-{uuid4().hex[:4].upper()}", "fuel_type": "diesel"},
        )
        assert r.status_code in (200, 201), r.text
        vehicle_id = r.json()["id"]
        r2 = await c.patch(f"/api/v1/vehicles/{vehicle_id}", headers=viewer, json={"make": "Ford"})
    assert r2.status_code == 403, r2.text


# ── RBAC-02: viewer/mechanic cannot create/update drivers ─────────────────────


async def test_viewer_cannot_create_driver():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.post(
            "/api/v1/drivers",
            headers=headers,
            json={"full_name": "Driver Viewer Block", "license_number": "L123456"},
        )
    assert r.status_code == 403, r.text


async def test_mechanic_cannot_create_driver():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "mechanic")
    async with _client() as c:
        r = await c.post(
            "/api/v1/drivers",
            headers=headers,
            json={"full_name": "Driver Mech Block", "license_number": "L654321"},
        )
    assert r.status_code == 403, r.text


# ── RBAC-03: viewer/mechanic cannot create trips ──────────────────────────────


async def test_viewer_cannot_create_trip():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.post(
            "/api/v1/trips",
            headers=headers,
            json={
                "vehicle_id": str(uuid4()),
                "driver_id": str(uuid4()),
                "origin": "Maputo",
                "destination": "Beira",
            },
        )
    assert r.status_code == 403, r.text


async def test_mechanic_cannot_create_trip():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "mechanic")
    async with _client() as c:
        r = await c.post(
            "/api/v1/trips",
            headers=headers,
            json={
                "vehicle_id": str(uuid4()),
                "driver_id": str(uuid4()),
                "origin": "Maputo",
                "destination": "Beira",
            },
        )
    assert r.status_code == 403, r.text


# ── RBAC-04: viewer/mechanic cannot create billing documents ──────────────────


async def test_viewer_cannot_create_billing_document():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.post(
            "/api/v1/billing/documents",
            headers=headers,
            json={
                "contract_id": str(uuid4()),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )
    assert r.status_code == 403, r.text


async def test_mechanic_cannot_create_billing_document():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "mechanic")
    async with _client() as c:
        r = await c.post(
            "/api/v1/billing/documents",
            headers=headers,
            json={
                "contract_id": str(uuid4()),
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
            },
        )
    assert r.status_code == 403, r.text


# ── RBAC-05: viewer/mechanic cannot write known-routes ────────────────────────


async def test_viewer_cannot_create_known_route():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.post(
            "/api/v1/known-routes",
            headers=headers,
            json={"origin": "Maputo", "destination": "Beira", "distance_km": 1050},
        )
    assert r.status_code == 403, r.text


async def test_mechanic_cannot_create_known_route():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "mechanic")
    async with _client() as c:
        r = await c.post(
            "/api/v1/known-routes",
            headers=headers,
            json={"origin": "Maputo", "destination": "Beira", "distance_km": 1050},
        )
    assert r.status_code == 403, r.text


async def test_viewer_cannot_delete_known_route():
    tenant = await _make_tenant()
    viewer = await _dashboard_headers(tenant.id, "viewer")
    admin = await _dashboard_headers(tenant.id, "admin")
    async with _client() as c:
        r = await c.post(
            "/api/v1/known-routes",
            headers=admin,
            json={"origin": "Nampula", "destination": "Pemba", "distance_km": 350},
        )
        assert r.status_code in (200, 201), r.text
        route_id = r.json()["id"]
        r2 = await c.delete(f"/api/v1/known-routes/{route_id}", headers=viewer)
    assert r2.status_code == 403, r2.text


async def test_manager_cannot_delete_known_route():
    """DELETE is ADMIN_ROLES only — manager must be denied."""
    tenant = await _make_tenant()
    manager = await _dashboard_headers(tenant.id, "manager")
    admin = await _dashboard_headers(tenant.id, "admin")
    async with _client() as c:
        r = await c.post(
            "/api/v1/known-routes",
            headers=admin,
            json={"origin": "Tete", "destination": "Chimoio", "distance_km": 240},
        )
        assert r.status_code in (200, 201), r.text
        route_id = r.json()["id"]
        r2 = await c.delete(f"/api/v1/known-routes/{route_id}", headers=manager)
    assert r2.status_code == 403, r2.text


# ── RBAC-06: driver_app scope cannot hit dashboard endpoints ──────────────────


async def test_driver_app_token_denied_on_vehicles():
    tenant = await _make_tenant()
    headers = await _driver_app_headers(tenant.id)
    async with _client() as c:
        r = await c.get("/api/v1/vehicles", headers=headers)
    assert r.status_code == 403, r.text


async def test_driver_app_token_denied_on_trips_post():
    tenant = await _make_tenant()
    headers = await _driver_app_headers(tenant.id)
    async with _client() as c:
        r = await c.post(
            "/api/v1/trips",
            headers=headers,
            json={
                "vehicle_id": str(uuid4()),
                "driver_id": str(uuid4()),
                "origin": "X",
                "destination": "Y",
            },
        )
    assert r.status_code == 403, r.text


async def test_driver_app_token_denied_on_billing():
    tenant = await _make_tenant()
    headers = await _driver_app_headers(tenant.id)
    async with _client() as c:
        r = await c.get("/api/v1/billing/documents", headers=headers)
    assert r.status_code == 403, r.text


# ── RBAC-07: read access is open to all dashboard roles ───────────────────────


async def test_viewer_can_list_vehicles():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.get("/api/v1/vehicles", headers=headers)
    assert r.status_code == 200, r.text


async def test_mechanic_can_list_vehicles():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "mechanic")
    async with _client() as c:
        r = await c.get("/api/v1/vehicles", headers=headers)
    assert r.status_code == 200, r.text


async def test_viewer_can_list_trips():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.get("/api/v1/trips", headers=headers)
    assert r.status_code == 200, r.text


async def test_viewer_can_list_known_routes():
    tenant = await _make_tenant()
    headers = await _dashboard_headers(tenant.id, "viewer")
    async with _client() as c:
        r = await c.get("/api/v1/known-routes", headers=headers)
    assert r.status_code == 200, r.text
