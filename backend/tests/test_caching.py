import json
from unittest.mock import AsyncMock

import pytest

from app.main import app


@pytest.fixture
def mock_app_redis():
    """Mock Redis client and attach it to app.state.redis."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock(return_value=True)
    mock.keys = AsyncMock(return_value=[])
    mock.delete = AsyncMock(return_value=1)

    old_redis = getattr(app.state, "redis", None)
    app.state.redis = mock
    yield mock
    app.state.redis = old_redis


@pytest.mark.asyncio
async def test_vehicles_list_cache_miss_and_hit(async_client, auth_headers, mock_app_redis):
    # Miss case: redis.get returns None
    mock_app_redis.get.return_value = None

    response = await async_client.get("/api/v1/vehicles", headers=auth_headers)
    assert response.status_code == 200

    # Assert get was called on redis
    assert mock_app_redis.get.called
    # Assert setex was called to populate the cache (TTL = 120)
    assert mock_app_redis.setex.called
    call_args = mock_app_redis.setex.call_args[0]
    assert "vehicles" in call_args[0]
    assert call_args[1] == 120  # TTL 120s

    # Hit case: redis.get returns cached value
    mock_app_redis.get.reset_mock()
    mock_app_redis.setex.reset_mock()

    cached_data = [
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "tenant_id": "22222222-2222-4222-8222-222222222222",
            "plate": "ABC-123-MC",
            "chassis": None,
            "brand": "Toyota",
            "model": "Hino",
            "year": None,
            "color": None,
            "category": "pesado",
            "status": "active",
            "current_km": 42_000,
            "fuel_type": "gasoleo",
            "documents": None,
            "qr_code_hash": None,
            "photo_file_id": None,
            "avg_consumption_target": None,
            "fuel_limit_daily": None,
            "max_payload_kg": None,
            "ownership_type": "fleet",
            "customer_client_id": None,
            "created_at": "2026-08-20T08:00:00Z",
            "updated_at": "2026-08-20T08:00:00Z",
        }
    ]
    mock_app_redis.get.return_value = json.dumps(cached_data)

    response2 = await async_client.get("/api/v1/vehicles", headers=auth_headers)
    assert response2.status_code == 200
    assert response2.json() == cached_data
    assert mock_app_redis.get.called
    assert not mock_app_redis.setex.called  # shouldn't call setex on cache hit


@pytest.mark.asyncio
async def test_vehicle_mutation_invalidates_cache(async_client, auth_headers, mock_app_redis):
    # Mock keys call to return some cached keys for the tenant
    mock_app_redis.keys.return_value = ["tenant:some-tenant-id:vehicles:status=active"]

    # Trigger a vehicle mutation: e.g. POST /vehicles
    payload = {
        "plate": "MC-888-XX",
        "brand": "Toyota",
        "model": "Dyna",
        "year": 2020,
        "chassis": "CHASSIS1234567890",
        "status": "active",
        "type": "cargo_rigid",
        "tara_kg": 5000,
        "gross_weight_kg": 10000,
        "fuel_capacity_l": 150,
    }

    response = await async_client.post("/api/v1/vehicles", json=payload, headers=auth_headers)
    assert response.status_code in (200, 201)

    # Verify that invalidate_tenant_caches was called by checking redis.keys and redis.delete calls
    assert mock_app_redis.keys.called
    assert mock_app_redis.delete.called

    # The pattern should search for all keys under the tenant
    pattern_arg = mock_app_redis.keys.call_args[0][0]
    assert pattern_arg.startswith("tenant:")
    assert pattern_arg.endswith(":*")


@pytest.mark.asyncio
async def test_trips_list_cache_miss_and_hit(async_client, auth_headers, mock_app_redis):
    mock_app_redis.get.return_value = None

    # Caching only active trips with other filters as None
    response = await async_client.get(
        "/api/v1/trips", params={"status": "active"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert mock_app_redis.get.called
    assert mock_app_redis.setex.called
    call_args = mock_app_redis.setex.call_args[0]
    assert "trips:active" in call_args[0]
    assert call_args[1] == 30  # TTL 30s

    # Other filters present -> no cache
    mock_app_redis.get.reset_mock()
    mock_app_redis.setex.reset_mock()
    response_no_cache = await async_client.get(
        "/api/v1/trips",
        params={"status": "active", "vehicle_id": "00000000-0000-0000-0000-000000000001"},
        headers=auth_headers,
    )
    assert response_no_cache.status_code == 200
    assert not mock_app_redis.get.called
    assert not mock_app_redis.setex.called


@pytest.mark.asyncio
async def test_drivers_list_cache_miss_and_hit(async_client, auth_headers, mock_app_redis):
    mock_app_redis.get.return_value = None
    response = await async_client.get("/api/v1/drivers", headers=auth_headers)
    assert response.status_code == 200
    assert mock_app_redis.get.called
    assert mock_app_redis.setex.called
    call_args = mock_app_redis.setex.call_args[0]
    assert "drivers" in call_args[0]
    assert call_args[1] == 120  # TTL 120s


@pytest.mark.asyncio
async def test_analytics_kpis_cache_miss_and_hit(async_client, auth_headers, mock_app_redis):
    mock_app_redis.get.return_value = None
    response = await async_client.get(
        "/api/v1/analytics/kpis",
        params={"period_start": "2025-01-01T00:00:00", "period_end": "2025-12-31T23:59:59"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert mock_app_redis.get.called
    assert mock_app_redis.setex.called
    call_args = mock_app_redis.setex.call_args[0]
    assert "analytics:kpis" in call_args[0]
    assert call_args[1] == 60  # TTL 60s
