"""CLI-04 tests for the /api/v1/contracts endpoint — client_id support."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_create_contract_requires_client_id_or_name(async_client, auth_headers):
    """POST /api/v1/contracts with neither client_id nor client_name returns HTTP 422."""
    response = await async_client.post(
        "/api/v1/contracts/",
        json={
            "contract_reference": f"CTR-NO-CLIENT-{uuid.uuid4().hex[:6]}",
            "billing_cycle": "monthly",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_create_contract_with_client_name_legacy(async_client, auth_headers):
    """POST /api/v1/contracts with client_name (legacy path) still works."""
    response = await async_client.post(
        "/api/v1/contracts/",
        json={
            "client_name": "Legacy Client Lda",
            "contract_reference": f"CTR-LEGACY-{uuid.uuid4().hex[:6]}",
            "billing_cycle": "monthly",
        },
        headers=auth_headers,
    )
    assert response.status_code in (200, 201), response.text
    data = response.json()
    assert data["client_name"] == "Legacy Client Lda"
    assert data["client_id"] is None


@pytest.mark.asyncio
async def test_create_contract_with_client_id(async_client, auth_headers, client_payload):
    """POST /api/v1/contracts with client_id populates client_name from client.trading_name."""
    # 1. Create a client
    r = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    # 2. Create contract referencing that client
    r2 = await async_client.post(
        "/api/v1/contracts/",
        json={
            "client_id": client_id,
            "contract_reference": f"CTR-CLI-04-{uuid.uuid4().hex[:6]}",
            "billing_cycle": "monthly",
        },
        headers=auth_headers,
    )
    assert r2.status_code in (200, 201), r2.text
    data = r2.json()
    assert data["client_name"] == client_payload["trading_name"]
    assert data["client_id"] == client_id


@pytest.mark.asyncio
async def test_create_contract_client_id_cross_tenant(
    async_client, auth_headers, client_payload, db
):
    """POST /api/v1/contracts with client_id from another tenant returns 404."""
    from app.modules.clients.models import Client
    from app.modules.tenants.models import Tenant

    # Create a client in a different tenant
    other_tenant = Tenant(
        name=f"Other Tenant {uuid.uuid4().hex[:6]}",
        slug=f"other-{uuid.uuid4().hex[:6]}",
    )
    db.add(other_tenant)
    await db.flush()

    other_client = Client(
        tenant_id=other_tenant.id,
        trading_name="Other Tenant Client",
        nuit="999999999",
        payment_terms_days=30,
    )
    db.add(other_client)
    await db.commit()
    await db.refresh(other_client)

    # Try to create a contract in the original tenant referencing the other tenant's client
    r = await async_client.post(
        "/api/v1/contracts/",
        json={
            "client_id": str(other_client.id),
            "contract_reference": f"CTR-CROSS-{uuid.uuid4().hex[:6]}",
            "billing_cycle": "monthly",
        },
        headers=auth_headers,
    )
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_list_contracts_filter_by_client_id(async_client, auth_headers, client_payload):
    """GET /api/v1/contracts?client_id={id} returns only contracts for that client."""
    # Create client
    r = await async_client.post("/api/v1/clients", json=client_payload, headers=auth_headers)
    assert r.status_code == 201
    client_id = r.json()["id"]

    # Create contract linked to client
    r2 = await async_client.post(
        "/api/v1/contracts/",
        json={
            "client_id": client_id,
            "contract_reference": f"CTR-FILTER-{uuid.uuid4().hex[:6]}",
            "billing_cycle": "monthly",
        },
        headers=auth_headers,
    )
    assert r2.status_code in (200, 201)
    linked_contract_id = r2.json()["id"]

    # Create contract NOT linked to this client (legacy)
    r3 = await async_client.post(
        "/api/v1/contracts/",
        json={
            "client_name": "Another Client",
            "contract_reference": f"CTR-OTHER-{uuid.uuid4().hex[:6]}",
            "billing_cycle": "monthly",
        },
        headers=auth_headers,
    )
    assert r3.status_code in (200, 201)

    # List with client_id filter
    list_r = await async_client.get(
        f"/api/v1/contracts/?client_id={client_id}",
        headers=auth_headers,
    )
    assert list_r.status_code == 200
    data = list_r.json()
    ids = [c["id"] for c in data]
    assert linked_contract_id in ids
    # The unlinked contract should not appear
    assert all(c["client_id"] == client_id for c in data)
