# ruff: noqa: E402
import os
import uuid
from uuid import uuid4

import httpx
import jwt as _jwt
import pytest
from sqlalchemy.exc import OperationalError

os.environ.setdefault("DEV_TEST_TOKEN", "test-token")

from app.config import get_settings  # noqa: E402
from app.database import AsyncSessionLocal, engine, import_all_models  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.drivers.models import Driver  # noqa: E402
from app.modules.tenants.models import Tenant  # noqa: E402
from app.modules.users.models import User  # noqa: E402
from app.modules.vehicles.models import Vehicle  # noqa: E402

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


def jwt_headers_for_user(tenant_id: uuid.UUID, user_id: uuid.UUID, role: str = "admin") -> dict[str, str]:
    """Mint a real JWT so principal.user_id is populated (required for labor cost accumulation)."""
    settings = get_settings()
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


async def create_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


async def seed_entities():
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant StaffRate {suffix}", slug=f"staffrate-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"SR-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver StaffRate {suffix}",
            phone=f"25887{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant.id, vehicle.id, driver.id


async def seed_user_in_db(tenant_id: uuid.UUID, role: str = "admin") -> uuid.UUID:
    """Insert a User directly in DB and return user_id."""
    async with AsyncSessionLocal() as db:
        user = User(
            tenant_id=tenant_id,
            email=f"user-{uuid4().hex[:6]}@test.com",
            full_name="Test User",
            role=role,
            password_hash="noop",
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user.id


async def seed_work_order_with_task(client: httpx.AsyncClient, headers: dict, vehicle_id) -> tuple[str, str]:
    """Create maintenance request + approved + started work order + one task.
    Returns (wo_id, task_id) — work order is in_progress so tasks can be completed.
    """
    mr = await client.post("/api/v1/workshop/maintenance-requests", headers=headers, json={
        "vehicle_id": str(vehicle_id),
        "request_type": "corrective",
        "priority": "normal",
        "description": "Test maintenance for staff rates",
    })
    assert mr.status_code == 200, f"MR creation failed: {mr.text}"
    mr_id = mr.json()["id"]

    wo = await client.post("/api/v1/workshop/work-orders", headers=headers, json={
        "maintenance_request_id": mr_id,
        "vehicle_id": str(vehicle_id),
        "planned_work": "Test work for staff rates",
    })
    assert wo.status_code == 200, f"WO creation failed: {wo.text}"
    wo_id = wo.json()["id"]

    approved = await client.post(f"/api/v1/workshop/work-orders/{wo_id}/approve", headers=headers, json={})
    assert approved.status_code == 200, f"WO approve failed: {approved.text}"

    started = await client.post(f"/api/v1/workshop/work-orders/{wo_id}/start", headers=headers, json={})
    assert started.status_code == 200, f"WO start failed: {started.text}"

    task = await client.post(f"/api/v1/workshop/work-orders/{wo_id}/tasks", headers=headers, json={
        "description": "Test task for staff rates",
    })
    assert task.status_code == 200, f"Task creation failed: {task.text}"
    task_id = task.json()["id"]

    return wo_id, task_id


@pytest.mark.asyncio
async def test_create_staff_rate_201() -> None:
    """POST /api/v1/workshop/staff-rates returns 201 with id and hourly_rate."""
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        user_id = await seed_user_in_db(tenant_id)
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            resp = await client.post("/api/v1/workshop/staff-rates", headers=headers, json={
                "user_id": str(user_id),
                "hourly_rate": "150.00",
                "effective_from": "2026-01-01",
            })
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert "id" in data
            assert float(data["hourly_rate"]) == 150.0
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_list_staff_rates_returns_created() -> None:
    """GET /api/v1/workshop/staff-rates includes the just-created rate."""
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        user_id = await seed_user_in_db(tenant_id)
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            create_resp = await client.post("/api/v1/workshop/staff-rates", headers=headers, json={
                "user_id": str(user_id),
                "hourly_rate": "200.00",
                "effective_from": "2026-01-01",
            })
            assert create_resp.status_code == 201, create_resp.text
            rate_id = create_resp.json()["id"]

            list_resp = await client.get("/api/v1/workshop/staff-rates", headers=headers)
            assert list_resp.status_code == 200
            rates = list_resp.json()
            assert any(r["id"] == rate_id for r in rates), f"Rate {rate_id} not found in list: {rates}"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_assign_task_to_mechanic_200() -> None:
    """PATCH /workshop/work-orders/{wo_id}/tasks/{task_id} with user_id+estimated_minutes returns 200."""
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        user_id = await seed_user_in_db(tenant_id)
        headers = auth_headers(tenant_id)
        async with await create_api_client() as client:
            wo_id, task_id = await seed_work_order_with_task(client, headers, vehicle_id)

            resp = await client.patch(
                f"/api/v1/workshop/work-orders/{wo_id}/tasks/{task_id}",
                headers=headers,
                json={"assigned_to": str(user_id), "estimated_minutes": 90},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert str(data["assigned_to"]) == str(user_id)
            assert data["estimated_minutes"] == 90
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_labor_cost_increments_on_complete() -> None:
    """Rate=100 MZN/hr, actual_minutes=90 -> labor_cost += 150.00 on work order."""
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        # Create a real user so we can mint a JWT with user_id (DEV_TEST_TOKEN has user_id=None)
        user_id = await seed_user_in_db(tenant_id, role="admin")
        headers = auth_headers(tenant_id)
        user_headers = jwt_headers_for_user(tenant_id, user_id, role="admin")

        async with await create_api_client() as client:
            # Create the staff rate for this user
            rate_resp = await client.post("/api/v1/workshop/staff-rates", headers=headers, json={
                "user_id": str(user_id),
                "hourly_rate": "100.00",
                "effective_from": "2026-01-01",
            })
            assert rate_resp.status_code == 201, rate_resp.text

            # Create WO + task (in_progress so task can be completed)
            wo_id, task_id = await seed_work_order_with_task(client, headers, vehicle_id)

            # Assign task to mechanic
            assign_resp = await client.patch(
                f"/api/v1/workshop/work-orders/{wo_id}/tasks/{task_id}",
                headers=headers,
                json={"assigned_to": str(user_id), "estimated_minutes": 90},
            )
            assert assign_resp.status_code == 200, assign_resp.text

            # Complete task using real JWT headers so actor_id = user_id for rate lookup
            complete_resp = await client.post(
                f"/api/v1/workshop/work-orders/{wo_id}/tasks/{task_id}/complete",
                headers=user_headers,
                json={"notes": "Done", "actual_minutes": 90},
            )
            assert complete_resp.status_code == 200, complete_resp.text

            # Verify labor_cost on the work order (no single-WO GET — use list filtered by vehicle)
            wo_list_resp = await client.get(
                f"/api/v1/workshop/work-orders?vehicle_id={vehicle_id}",
                headers=headers,
            )
            assert wo_list_resp.status_code == 200, wo_list_resp.text
            work_orders = wo_list_resp.json()
            wo_data = next((w for w in work_orders if w["id"] == wo_id), None)
            assert wo_data is not None, f"Work order {wo_id} not found in list"
            labor_cost = float(wo_data.get("labor_cost", 0))
            # 100 MZN/hr * 90 min / 60 = 150.00
            assert abs(labor_cost - 150.0) < 0.01, f"Expected 150.00, got {labor_cost}"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_mechanic_cannot_access_billing() -> None:
    """mechanic role is in DASHBOARD_ROLES (can read billing) but blocked from billing mutations.

    DASHBOARD_ROLES = {owner, admin, manager, viewer, mechanic} — mechanic CAN read billing GET.
    WRITE_ROLES = {owner, admin, manager} — mechanic CANNOT create billing documents (POST -> 403).
    This test verifies: mechanic GET billing/documents=200, POST billing/documents=403.
    """
    try:
        tenant_id, vehicle_id, driver_id = await seed_entities()
        user_id = await seed_user_in_db(tenant_id, role="mechanic")
        mechanic_headers = jwt_headers_for_user(tenant_id, user_id, role="mechanic")

        async with await create_api_client() as client:
            # mechanic is in DASHBOARD_ROLES — GET billing is allowed (200)
            billing_get_resp = await client.get("/api/v1/billing/documents", headers=mechanic_headers)
            assert billing_get_resp.status_code == 200, (
                f"Expected 200 for mechanic reading billing documents, got {billing_get_resp.status_code}"
            )

            # mechanic is NOT in WRITE_ROLES — POST billing is blocked (403)
            billing_post_resp = await client.post(
                "/api/v1/billing/documents",
                headers=mechanic_headers,
                json={"contract_id": "00000000-0000-0000-0000-000000000001", "period_start": "2026-01-01", "period_end": "2026-01-31"},
            )
            assert billing_post_resp.status_code == 403, (
                f"Expected 403 for mechanic creating billing document, got {billing_post_resp.status_code}: {billing_post_resp.text}"
            )
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_staff_rate_cross_tenant_isolation() -> None:
    """Rate created as tenant A is not in list when authenticated as tenant B."""
    try:
        tenant_a_id, _, _ = await seed_entities()
        tenant_b_id, _, _ = await seed_entities()
        user_a_id = await seed_user_in_db(tenant_a_id)
        headers_a = auth_headers(tenant_a_id)
        headers_b = auth_headers(tenant_b_id)

        async with await create_api_client() as client:
            create_resp = await client.post("/api/v1/workshop/staff-rates", headers=headers_a, json={
                "user_id": str(user_a_id),
                "hourly_rate": "300.00",
                "effective_from": "2026-01-01",
            })
            assert create_resp.status_code == 201, create_resp.text
            rate_id = create_resp.json()["id"]

            list_b = await client.get("/api/v1/workshop/staff-rates", headers=headers_b)
            assert list_b.status_code == 200
            b_ids = [r["id"] for r in list_b.json()]
            assert rate_id not in b_ids, f"Staff rate {rate_id} from tenant A leaked into tenant B"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")
