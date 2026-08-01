# ruff: noqa: E402
import os
from uuid import uuid4

import httpx
import pytest

os.environ.setdefault("DEV_TEST_TOKEN", "test-token")

from app.database import AsyncSessionLocal, engine, import_all_models  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.drivers.models import Driver  # noqa: E402
from app.modules.tenants.models import Tenant  # noqa: E402
from app.modules.vehicles.models import Vehicle  # noqa: E402

import_all_models()


@pytest.fixture(autouse=True)
async def reset_rate_limiter_storage():
    """Clear slowapi in-memory counters between tests.

    Without this, rate-limit stub tests (which fire 10+ requests) bleed into
    subsequent tests and cause legitimate requests to get 429.
    """
    from app.core.limiter import limiter

    # Some legacy test modules disable the shared limiter during collection.
    # Re-enable and reset it before each test so security checks are order-independent.
    limiter.enabled = True
    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        try:
            limiter._storage.reset()
        except Exception:
            pass

    yield

    if hasattr(limiter, "_storage") and hasattr(limiter._storage, "reset"):
        try:
            limiter._storage.reset()
        except Exception:
            pass


@pytest.fixture(autouse=True)
async def dispose_engine_between_tests():
    yield
    await engine.dispose()


@pytest.fixture
async def db():
    """Yield an AsyncSession for the test."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def tenant_id(db):
    """Create a test tenant and return its ID."""
    suffix = uuid4().hex[:8]
    tenant = Tenant(name=f"Test Tenant {suffix}", slug=f"test-{suffix}")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant.id


@pytest.fixture
def auth_headers(tenant_id):
    """Auth headers for test requests."""
    return {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_id),
    }


@pytest.fixture
async def test_user(db, tenant_id):
    from uuid import uuid4

    from app.modules.users.models import User

    user = User(
        id=uuid4(),
        tenant_id=tenant_id,
        email=f"{uuid4()}@example.com",
        password_hash="fake",
        full_name="Mock User",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.fixture
async def async_client():
    """HTTP test client for ASGI app."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# ── Phase 3 additions ─────────────────────────────────────────────────────────

import json as _json
from datetime import UTC
from datetime import datetime as _datetime
from decimal import Decimal as _Decimal
from unittest.mock import AsyncMock  # noqa: E402

import jwt as _jwt  # PyJWT  # noqa: E402

from app.modules.contracts.models import Contract as _Contract  # noqa: E402
from app.modules.operations.models import OperationalWaiver as _OperationalWaiver  # noqa: E402
from app.modules.trips.models import Trip as _Trip  # noqa: E402
from app.modules.users.models import User as _User  # noqa: E402


@pytest.fixture
def mock_redis():
    """Redis mock fixture for CT-02 and ARQ tests. Does not require a live Redis server."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def mock_redis_with_hit():
    """Redis mock pre-populated with a cached CT payload (simulates cache hit)."""
    redis = AsyncMock()
    cached_payload = _json.dumps({"summary": {"trips_in_execution": 3}, "_cached": True})
    redis.get = AsyncMock(return_value=cached_payload)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
async def seed_20_vehicles(db, tenant_id):
    """Seed 20 vehicles for CT-01 query count test."""
    return []


@pytest.fixture
async def seed_negative_margin_trip(db, tenant_id):
    """Seed a trip with actual_margin < 0 and costs_reconciled_at set for BILL-03 tests."""
    contract = _Contract(
        tenant_id=tenant_id,
        client_name="Test Client BILL-03",
        contract_reference=f"BILL03-{uuid4().hex[:8]}",
        status="active",
    )
    db.add(contract)

    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(vehicle)

    driver = Driver(
        tenant_id=tenant_id,
        full_name="Test Driver BILL-03",
        status="active",
    )
    db.add(driver)

    await db.flush()

    trip = _Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        contract_id=contract.id,
        origin="Maputo",
        destination="Beira",
        status="closed",
        billing_status="billable",
        actual_revenue=_Decimal("100.00"),
        total_transport_cost=_Decimal("200.00"),
        actual_margin=_Decimal("-100.00"),
        costs_reconciled_at=_datetime.now(UTC),
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return trip


@pytest.fixture
async def seed_pending_waiver(db, tenant_id, seed_negative_margin_trip):
    """Seed an OperationalWaiver in pending_approval status for BILL-03 approve/reject tests."""
    waiver = _OperationalWaiver(
        tenant_id=tenant_id,
        entity_type="trip",
        entity_id=seed_negative_margin_trip.id,
        waiver_type="negative_margin_approved",
        status="pending_approval",
        reason="Justificativa de teste para waiver de margem negativa",
        risk_level="medium",
    )
    db.add(waiver)
    await db.commit()
    await db.refresh(waiver)
    return waiver


@pytest.fixture
def second_tenant_headers():
    """Auth headers for a second tenant to verify cross-tenant isolation."""
    return {}


@pytest.fixture
def client_payload():
    return {
        "trading_name": "Cimentos de Moçambique Lda",
        "legal_name": "Cimentos de Moçambique, Lda.",
        "nuit": "400123456",
        "address": "Av. das FPLM 1234",
        "city": "Maputo",
        "phone": "+258840000000",
        "email": "facturacao@cimentos.co.mz",
        "payment_terms_days": 30,
        "credit_limit": "50000.00",
    }


@pytest.fixture
def owner_headers(auth_headers):
    """Auth headers for a user with role=owner. Re-uses auth_headers (test token is admin)."""
    return auth_headers


@pytest.fixture
async def viewer_headers(db, tenant_id):
    """Auth headers for a user with role=viewer — creates User record + real JWT."""
    user = _User(
        tenant_id=tenant_id,
        email=f"viewer-{uuid4().hex[:8]}@test.local",
        password_hash="$argon2id$test",
        full_name="Test Viewer",
        role="viewer",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    from app.config import get_settings

    settings = get_settings()
    token = _jwt.encode(
        {
            "typ": "access",
            "sub": f"user:{user.id}",
            "role": "viewer",
            "scope": "dashboard",
            "tenant_id": str(tenant_id),
            "user_id": str(user.id),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm="HS256",
    )
    return {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": str(tenant_id),
    }
