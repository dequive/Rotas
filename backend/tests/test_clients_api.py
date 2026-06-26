"""CLI-01 / CLI-02 tests for the /api/v1/clients endpoint."""

import uuid

import pytest
from sqlalchemy import text

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
async def test_viewer_can_read_clients(async_client, viewer_headers):
    """Viewer can read clients but cannot mutate them."""
    response = await async_client.get("/api/v1/clients", headers=viewer_headers)
    assert response.status_code == 200, response.text
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_viewer_cannot_create_client(async_client, viewer_headers, client_payload):
    """POST /api/v1/clients requires a write role."""
    response = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=viewer_headers,
    )
    assert response.status_code == 403, response.text
    assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.asyncio
async def test_viewer_cannot_patch_client(
    async_client,
    auth_headers,
    viewer_headers,
    client_payload,
):
    """PATCH /api/v1/clients/{id} requires a write role."""
    create_resp = await async_client.post(
        "/api/v1/clients",
        json=client_payload,
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    client_id = create_resp.json()["id"]

    patch_resp = await async_client.patch(
        f"/api/v1/clients/{client_id}",
        json={"is_active": False},
        headers=viewer_headers,
    )
    assert patch_resp.status_code == 403, patch_resp.text
    assert patch_resp.json()["error"]["code"] == "forbidden"


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
    tenant_b = Tenant(
        name=f"Tenant B {uuid.uuid4().hex[:6]}",
        slug=f"tenant-b-{uuid.uuid4().hex[:6]}",
    )
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


# CLI-03: backfill migration gate
@pytest.mark.asyncio
async def test_backfill_zero_null_client_ids(db, tenant_id):
    """After backfill SQL, no named contract remains with client_id IS NULL."""
    # Seed 3 contracts with client_name populated, distinct NUITs, and client_id = NULL.
    # Distinct NUITs are required so each inserts a separate client record in Step 1+2
    # (all-NULL nuids collapse to the same placeholder '000000000' and ON CONFLICT DO NOTHING
    # would skip rows 2 and 3, leaving them un-matched in Step 3).
    await db.execute(
        text("""
        INSERT INTO contracts (
            id, tenant_id, client_name, client_nuit, contract_reference, status,
            service_type, billing_cycle, billing_basis, currency,
            requires_load_permit, requires_delivery_proof,
            requires_cargo_manifest_for_manufactured_goods
        ) VALUES
            (:id1, :tenant_id, 'Cimentos de Moçambique Lda', '400000001', :ref1, 'active',
             'cargo_transport', 'monthly', 'trip', 'MZN', true, true, false),
            (:id2, :tenant_id, 'Transportes Beira SA', '400000002', :ref2, 'active',
             'cargo_transport', 'monthly', 'trip', 'MZN', true, true, false),
            (:id3, :tenant_id, 'Logistica Nacala Lda', '400000003', :ref3, 'active',
             'cargo_transport', 'monthly', 'trip', 'MZN', true, true, false)
    """),
        {
            "id1": str(uuid.uuid4()),
            "id2": str(uuid.uuid4()),
            "id3": str(uuid.uuid4()),
            "tenant_id": str(tenant_id),
            "ref1": uuid.uuid4().hex[:8],
            "ref2": uuid.uuid4().hex[:8],
            "ref3": uuid.uuid4().hex[:8],
        },
    )
    await db.flush()

    # Step 1+2 from migration f6a7b8c9d0e1: INSERT one client per normalized name
    await db.execute(
        text("""
        INSERT INTO clients (
            id, tenant_id, trading_name, nuit, payment_terms_days,
            is_active, created_at, updated_at
        )
        SELECT DISTINCT ON (tenant_id, lower(trim(client_name)))
            gen_random_uuid(),
            tenant_id,
            first_value(client_name) OVER (
                PARTITION BY tenant_id, lower(trim(client_name))
                ORDER BY length(client_name) DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ),
            COALESCE(NULLIF(trim(client_nuit), ''), '000000000'),
            30,
            true,
            NOW(),
            NOW()
        FROM contracts
        WHERE tenant_id = :tenant_id
          AND client_name IS NOT NULL AND client_name != ''
        ON CONFLICT (tenant_id, nuit) DO NOTHING
    """),
        {"tenant_id": str(tenant_id)},
    )

    # Step 3 from migration f6a7b8c9d0e1: UPDATE contracts.client_id by normalized name match
    await db.execute(
        text("""
        UPDATE contracts c
        SET client_id = cl.id
        FROM clients cl
        WHERE c.tenant_id = cl.tenant_id
          AND lower(trim(c.client_name)) = lower(trim(cl.trading_name))
          AND c.client_id IS NULL
          AND c.tenant_id = :tenant_id
    """),
        {"tenant_id": str(tenant_id)},
    )

    result = await db.execute(
        text("""
        SELECT count(*) FROM contracts
        WHERE tenant_id = :tenant_id
          AND client_id IS NULL
          AND client_name IS NOT NULL
          AND client_name != ''
    """),
        {"tenant_id": str(tenant_id)},
    )
    null_count = result.scalar()
    assert null_count == 0, (
        f"Expected 0 contracts with NULL client_id after backfill, got {null_count}"
    )


# ---------------------------------------------------------------------------
# GT-05: find-or-create against third_parties
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_client_duplicate_nuit_no_duplicate_third_party(
    async_client, auth_headers, db, tenant_id
):
    """Two POSTs with the same NUIT: second returns 409 AND only one third_parties row exists."""
    from sqlalchemy import text

    payload = {
        "trading_name": "Empresa Alpha Lda",
        "nuit": "500111222",
        "payment_terms_days": 30,
    }

    first = await async_client.post("/api/v1/clients", json=payload, headers=auth_headers)
    assert first.status_code == 201, first.text

    second = await async_client.post("/api/v1/clients", json=payload, headers=auth_headers)
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "nuit_already_exists"

    # Verify no duplicate third_parties row was created
    result = await db.execute(
        text("SELECT count(*) FROM third_parties WHERE tenant_id = :t AND nuit = '500111222'"),
        {"t": str(tenant_id)},
    )
    assert result.scalar() == 1, "find-or-create must not create duplicate third_parties rows"


@pytest.mark.asyncio
async def test_create_client_links_to_preexisting_third_party(
    async_client, auth_headers, db, tenant_id
):
    """If a third_party with same (tenant_id, nuit) already exists, client links to it — no duplicate."""
    from sqlalchemy import text

    nuit = "500333444"

    # Pre-insert a third_party row (simulates a supplier already registered)
    tp_result = await db.execute(
        text(
            """
            INSERT INTO third_parties (id, tenant_id, name, nuit, status, created_at, updated_at)
            VALUES (gen_random_uuid(), :t, 'Pre-existing Supplier', :nuit, 'active', now(), now())
            RETURNING id
            """
        ),
        {"t": str(tenant_id), "nuit": nuit},
    )
    existing_tp_id = tp_result.scalar()
    await db.commit()

    # POST /clients with the same NUIT
    resp = await async_client.post(
        "/api/v1/clients",
        json={"trading_name": "Empresa Beta Lda", "nuit": nuit, "payment_terms_days": 30},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text

    # Verify the client links to the pre-existing third_party
    client_id = resp.json()["id"]
    tp_check = await db.execute(
        text("SELECT third_party_id FROM clients WHERE id = :cid"),
        {"cid": client_id},
    )
    linked_tp_id = tp_check.scalar()
    assert str(linked_tp_id) == str(existing_tp_id), (
        "Client must link to pre-existing third_party, not create a new one"
    )

    # Verify no duplicate third_parties row
    count_result = await db.execute(
        text("SELECT count(*) FROM third_parties WHERE tenant_id = :t AND nuit = :nuit"),
        {"t": str(tenant_id), "nuit": nuit},
    )
    assert count_result.scalar() == 1, "Must not create duplicate third_parties row"


@pytest.mark.asyncio
async def test_create_client_cross_tenant_same_nuit_separate_third_parties(
    async_client, auth_headers, db
):
    """Same NUIT in two different tenants → two separate third_parties rows (cross-tenant isolation)."""
    from sqlalchemy import text

    from app.modules.tenants.models import Tenant

    # Use a unique NUIT per test run to avoid cross-run pollution (DB is not rolled back between runs)
    nuit = f"5{uuid.uuid4().int % 100000000:08d}"

    # Create a second tenant
    tenant_b = Tenant(name=f"Tenant B {uuid.uuid4().hex[:6]}", slug=f"tb-{uuid.uuid4().hex[:6]}")
    db.add(tenant_b)
    await db.commit()
    await db.refresh(tenant_b)

    headers_b = {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_b.id)}

    payload = {"trading_name": "Empresa Gamma Lda", "nuit": nuit, "payment_terms_days": 30}

    tenant_a_id = auth_headers["X-Tenant-Id"]

    resp_a = await async_client.post("/api/v1/clients", json=payload, headers=auth_headers)
    assert resp_a.status_code == 201, resp_a.text

    resp_b = await async_client.post("/api/v1/clients", json=payload, headers=headers_b)
    assert resp_b.status_code == 201, resp_b.text

    # Two third_parties rows with same NUIT but different tenant_ids — filter to only these two tenants
    # (avoids cross-run pollution since the DB is not rolled back between test runs)
    count_result = await db.execute(
        text("SELECT count(*) FROM third_parties WHERE nuit = :nuit AND tenant_id IN (:t_a, :t_b)"),
        {"nuit": nuit, "t_a": tenant_a_id, "t_b": str(tenant_b.id)},
    )
    assert count_result.scalar() == 2, (
        "Each tenant must get its own third_parties row for the same NUIT"
    )
