"""Driver Scorecard — integration tests (D-08 through D-11).

Score formula: 40% delivery proof rate + 25% sync discipline + 20% distance + 15% stop efficiency.
Rolling 30-day window. Score 0-100. Manager only.
"""

from uuid import uuid4

import httpx
import pytest

from app.database import AsyncSessionLocal, engine, import_all_models
from app.main import app
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant

import_all_models()


@pytest.fixture(autouse=True)
async def dispose_engine():
    yield
    await engine.dispose()


def auth_headers(tenant_id) -> dict[str, str]:
    return {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_id)}


async def seed_driver() -> tuple:
    """Seed tenant + driver for scorecard tests."""
    suffix = uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=f"Tenant Score {suffix}", slug=f"score-{suffix}")
        db.add(tenant)
        await db.flush()
        driver = Driver(
            tenant_id=tenant.id,
            full_name=f"Driver Score {suffix}",
            phone=f"25884{suffix[:7]}",
        )
        db.add(driver)
        await db.commit()
        return tenant.id, driver.id


async def test_scorecard_score_range():
    """D-09: Scorecard endpoint returns dict with score in 0-100 and valid tier."""
    tenant_id, driver_id = await seed_driver()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get(
            f"/api/v1/drivers/{driver_id}/scorecard",
            headers=auth_headers(tenant_id),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "score" in data
    assert "tier" in data
    assert data["tier"] in ("verde", "amarelo", "vermelho", "insuficiente")
    if data["score"] is not None:
        assert 0 <= data["score"] <= 100


async def test_scorecard_insufficient_data():
    """D-09/D-10: Driver with 0 trips in 30d returns tier='insuficiente' and score=None."""
    tenant_id, driver_id = await seed_driver()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get(
            f"/api/v1/drivers/{driver_id}/scorecard",
            headers=auth_headers(tenant_id),
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["score"] is None
    assert data["tier"] == "insuficiente"
    assert data["completed_trips"] == 0


async def test_scorecard_no_division_by_zero():
    """Pitfall 5: Driver with 0 completed trips does not cause 500 error."""
    tenant_id, driver_id = await seed_driver()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get(
            f"/api/v1/drivers/{driver_id}/scorecard",
            headers=auth_headers(tenant_id),
        )
    # Must be 200, not 500
    assert resp.status_code == 200


async def test_scorecard_api_endpoint_returns_200():
    """D-11: GET /drivers/{driver_id}/scorecard returns 200 for manager user."""
    tenant_id, driver_id = await seed_driver()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        resp = await client.get(
            f"/api/v1/drivers/{driver_id}/scorecard",
            headers=auth_headers(tenant_id),
        )
    assert resp.status_code == 200, resp.text
    assert resp.json()["driver_id"] == str(driver_id)
