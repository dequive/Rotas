import pytest


# CLI-01 stubs
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_create_client(async_client, auth_headers):
    """POST /api/v1/clients creates client with NUIT, trading_name, city."""
    ...


@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_create_client_duplicate_nuit(async_client, auth_headers):
    """POST with duplicate NUIT for same tenant returns HTTP 409."""
    ...


@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_list_clients_tenant_scoped(async_client, auth_headers):
    """GET /api/v1/clients returns only clients for authenticated tenant."""
    ...


@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_patch_client_deactivate(async_client, auth_headers):
    """PATCH /api/v1/clients/{id} with is_active=false deactivates client."""
    ...


@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_client_cross_tenant_isolation(async_client):
    """Client created in tenant A is not visible when authenticated as tenant B."""
    ...


# CLI-02 stubs
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_credit_limit_warning_thresholds(async_client, auth_headers):
    """Client with outstanding 80% of limit exposes warning; 100%+ exposes exceeded."""
    ...


# CLI-03 stub
@pytest.mark.skip(reason="Wave 0 stub — implement in Plan 01")
async def test_backfill_zero_null_client_ids(async_client, auth_headers):
    """After migration (c): contracts WHERE client_id IS NULL = 0."""
    ...
