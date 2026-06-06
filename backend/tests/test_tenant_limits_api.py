"""Tests for INFRA-03: GET /api/v1/tenants/me/limits endpoint."""
import pytest


@pytest.mark.skip(reason="Wave 3 — /tenants/me/limits endpoint not yet implemented")
async def test_get_limits_returns_correct_counts(client, auth_headers):
    """GET /api/v1/tenants/me/limits returns vehicle_count, vehicle_max,
    driver_count, driver_max, user_count, user_max, upgrade_url."""
    pass


@pytest.mark.skip(reason="Wave 3 — /tenants/me/limits endpoint not yet implemented")
async def test_get_limits_null_max_for_unlimited_tenant(client, auth_headers):
    """When Tenant.max_vehicles is None, vehicle_max is null in response."""
    pass


@pytest.mark.skip(reason="Wave 3 — Redis cache not yet wired to limits")
async def test_redis_cache_hit_skips_db_count(client, auth_headers, monkeypatch):
    """Second call to /tenants/me/limits within 30s reads from Redis, not DB."""
    pass


@pytest.mark.skip(reason="Wave 3 — /tenants/me/limits endpoint not yet implemented")
async def test_limits_requires_auth(client):
    """GET /api/v1/tenants/me/limits returns 401 without auth token."""
    pass
