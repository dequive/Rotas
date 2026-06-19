# ruff: noqa: E402
import os
import uuid
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

os.environ.setdefault("DEV_TEST_TOKEN", "test-token")

from app.database import AsyncSessionLocal, engine, import_all_models  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.drivers.models import Driver  # noqa: E402
from app.modules.operational_exceptions.models import OperationalException  # noqa: E402
from app.modules.tenants.models import Tenant  # noqa: E402
from app.modules.vehicles.models import Vehicle  # noqa: E402
from app.modules.workshop.models import WorkshopTool  # noqa: E402

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
        tenant = Tenant(name=f"Tenant Calibration {suffix}", slug=f"calib-{suffix}")
        db.add(tenant)
        await db.flush()
        vehicle = Vehicle(
            tenant_id=tenant.id,
            plate=f"CAL-{suffix}",
            category="pesado",
            fuel_type="gasoleo",
        )
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Calibration {suffix}",
            phone=f"25888{suffix[:7]}",
        )
        db.add_all([vehicle, driver])
        await db.commit()
        return tenant.id, vehicle.id, driver.id


async def seed_tool(
    tenant_id: uuid.UUID,
    is_critical: bool = False,
    calibration_interval_days: int | None = None,
) -> str:
    """Insert a WorkshopTool directly in DB and return tool ID as string."""
    async with AsyncSessionLocal() as db:
        tool = WorkshopTool(
            tenant_id=tenant_id,
            code=f"TOOL-{uuid4().hex[:6]}",
            name="Test Tool",
            is_critical=is_critical,
            status="available",
            calibration_interval_days=calibration_interval_days,
        )
        db.add(tool)
        await db.commit()
        await db.refresh(tool)
        return str(tool.id)


@pytest.mark.asyncio
async def test_record_calibration_201() -> None:
    """POST /api/v1/workshop/tools/{tool_id}/calibrations returns 201."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        tool_id = await seed_tool(tenant_id, is_critical=False)

        next_due = (datetime.now(UTC) + timedelta(days=365)).isoformat()
        async with await create_api_client() as client:
            resp = await client.post(
                f"/api/v1/workshop/tools/{tool_id}/calibrations",
                headers=headers,
                json={
                    "calibrated_at": datetime.now(UTC).isoformat(),
                    "next_due_at": next_due,
                    "notes": "Annual calibration",
                },
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()
            assert "id" in data
            assert data["tool_id"] == tool_id
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_calibration_history_list_200() -> None:
    """GET /api/v1/workshop/tools/{tool_id}/calibration-history returns list with entry."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        tool_id = await seed_tool(tenant_id)

        async with await create_api_client() as client:
            await client.post(
                f"/api/v1/workshop/tools/{tool_id}/calibrations",
                headers=headers,
                json={
                    "calibrated_at": datetime.now(UTC).isoformat(),
                    "next_due_at": (datetime.now(UTC) + timedelta(days=365)).isoformat(),
                    "notes": "Calibration entry",
                },
            )
            hist_resp = await client.get(
                f"/api/v1/workshop/tools/{tool_id}/calibration-history",
                headers=headers,
            )
            assert hist_resp.status_code == 200, hist_resp.text
            events = hist_resp.json()
            assert isinstance(events, list)
            assert len(events) >= 1
            assert events[0]["notes"] == "Calibration entry"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_update_tool_patch_200() -> None:
    """PATCH /api/v1/workshop/tools/{tool_id} with location+category returns 200 with updated fields."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        tool_id = await seed_tool(tenant_id)

        async with await create_api_client() as client:
            resp = await client.patch(
                f"/api/v1/workshop/tools/{tool_id}",
                headers=headers,
                json={"location": "Bancada-A1", "category": "medicao"},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["location"] == "Bancada-A1"
            assert data["category"] == "medicao"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_no_alert_when_interval_null() -> None:
    """Critical tool with calibration_interval_days=None -> no operational_exception even near expiry."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        # is_critical=True but calibration_interval_days=None — alert must NOT fire
        tool_id = await seed_tool(tenant_id, is_critical=True, calibration_interval_days=None)

        near_due = (datetime.now(UTC) + timedelta(days=15)).isoformat()

        async with await create_api_client() as client:
            resp = await client.post(
                f"/api/v1/workshop/tools/{tool_id}/calibrations",
                headers=headers,
                json={
                    "calibrated_at": datetime.now(UTC).isoformat(),
                    "next_due_at": near_due,
                },
            )
            assert resp.status_code == 201, resp.text

        # Verify NO operational_exception was created
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OperationalException).where(
                    OperationalException.tenant_id == tenant_id,
                    OperationalException.entity_type == "workshop_tool",
                )
            )
            exceptions = result.scalars().all()
            assert len(exceptions) == 0, (
                f"Expected NO operational_exception when calibration_interval_days=None, "
                f"but got {len(exceptions)}"
            )
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")


@pytest.mark.asyncio
async def test_alert_for_critical_tool_near_expiry() -> None:
    """is_critical=True + calibration_interval_days=90 + next_due_at within 30 days -> operational_exception."""
    try:
        tenant_id, _, _ = await seed_entities()
        headers = auth_headers(tenant_id)
        # Both is_critical AND calibration_interval_days must be set for alert to fire
        tool_id = await seed_tool(tenant_id, is_critical=True, calibration_interval_days=90)

        # next_due_at = 15 days from now (within 30-day threshold)
        near_due = (datetime.now(UTC) + timedelta(days=15)).isoformat()

        async with await create_api_client() as client:
            resp = await client.post(
                f"/api/v1/workshop/tools/{tool_id}/calibrations",
                headers=headers,
                json={
                    "calibrated_at": datetime.now(UTC).isoformat(),
                    "next_due_at": near_due,
                },
            )
            assert resp.status_code == 201, resp.text

        # Verify operational_exception was created in DB
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OperationalException).where(
                    OperationalException.tenant_id == tenant_id,
                    OperationalException.entity_type == "workshop_tool",
                )
            )
            exceptions = result.scalars().all()
            assert len(exceptions) >= 1, (
                "Expected operational_exception for critical tool near calibration expiry"
            )
            assert exceptions[0].exception_type == "tool_calibration_due"
    except OperationalError as exc:
        pytest.skip(f"DB not available: {exc}")
