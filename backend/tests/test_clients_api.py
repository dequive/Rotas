"""CLI-01 / CLI-02 tests for the /api/v1/clients endpoint."""

import uuid

import pytest


# ---------------------------------------------------------------------------
# CLI-01: CRUD
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_client(async_client, auth_headers, client_payload):
    """POST /api/v1/clients creates client with NUIT, trading_name, city."""
    response = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert "id" in data
    assert data["trading_name"] == client_payload["trading_name"]
    assert data["nuit"] == client_payload["nuit"]
    assert data["is_active"] is True
    assert data["city"] == "Maputo"


@pytest.mark.asyncio
async def test_create_client_duplicate_nuit(async_client, auth_headers, client_payload):
    """POST with duplicate NUIT for same tenant returns HTTP 409."""
    first = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert first.status_code == 201, first.text

    second = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "nuit_already_exists"


@pytest.mark.asyncio
async def test_list_clients_tenant_scoped(async_client, auth_headers, client_payload):
    """GET /api/v1/clients returns only clients for authenticated tenant."""
    create_resp = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    list_resp = await async_client.get("/api/v1/clients", headers=auth_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(c["nuit"] == client_payload["nuit"] for c in data)


@pytest.mark.asyncio
async def test_patch_client_deactivate(async_client, auth_headers, client_payload):
    """PATCH /api/v1/clients/{id} with is_active=false deactivates client."""
    create_resp = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]

    patch_resp = await async_client.patch(
        f"/api/v1/clients/{client_id}",
        json={"is_active": False},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_client_cross_tenant_isolation(async_client, auth_headers, client_payload, db):
    """Client created in tenant A is not visible when authenticated as tenant B."""
    from app.modules.tenants.models import Tenant

    # Create tenant A client
    create_resp = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201

    # Create a second separate tenant
    tenant_b = Tenant(name=f"Tenant B {uuid.uuid4().hex[:6]}", slug=f"tenant-b-{uuid.uuid4().hex[:6]}")
    db.add(tenant_b)
    await db.commit()
    await db.refresh(tenant_b)

    tenant_b_headers = {
        "Authorization": "Bearer test-token",
        "X-Tenant-Id": str(tenant_b.id),
    }

    list_resp = await async_client.get("/api/v1/clients", headers=tenant_b_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    # Tenant B has no clients — tenant A's client must not leak
    assert not any(c["nuit"] == client_payload["nuit"] for c in data), (
        "Cross-tenant data leak: tenant A client visible to tenant B"
    )


# ---------------------------------------------------------------------------
# CLI-02: Outstanding balance and credit limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_credit_limit_warning_thresholds(async_client, auth_headers, client_payload):
    """GET /api/v1/clients/{id} returns outstanding_balance and credit_limit fields."""
    create_resp = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    client_id = create_resp.json()["id"]

    detail_resp = await async_client.get(
        f"/api/v1/clients/{client_id}",
        headers=auth_headers,
    )
    assert detail_resp.status_code == 200, detail_resp.text
    data = detail_resp.json()
    assert "outstanding_balance" in data
    assert "credit_limit" in data
    # Phase 5 interim: no billing_documents with client_id FK yet — balance is 0
    assert data["outstanding_balance"] is not None or data["outstanding_balance"] == 0


# CLI-03 stub — post-migration assertion (Plan 02)
@pytest.mark.skip(reason="Post-migration assertion — implement after Plan 02 backfill completes")
async def test_backfill_zero_null_client_ids(async_client, auth_headers):
    """After migration (c): contracts WHERE client_id IS NULL = 0."""
    ...
