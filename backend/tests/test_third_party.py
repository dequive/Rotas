"""Phase 23 — Third Party Registry integration tests.

Covers Plans 02, 05, 06, 07, 08:
- TP-02: ThirdParty CRUD + roles
- TP-05: DriverVehicleAssignment
- TP-06: OperationalDocument CRUD + verify + expiring
- TP-10: Document expiry alerts (worker task — mocked)
- TP-11: Party directory UNION ALL
"""

import uuid
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


async def test_doc_expiry_alerts():
    """TP-10: Document expiring in 15 days generates 1 alert with correct fields.

    Mocks the DB session and create_alert — no live DB or Redis required.
    """
    doc_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    expiry = date.today() + timedelta(days=15)

    # Mock OperationalDocument ORM row
    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.subject_type = "driver"
    mock_doc.subject_id = subject_id
    mock_doc.document_type = "license"
    mock_doc.expiry_date = expiry

    captured_alerts: list = []

    async def mock_create_alert(db, tenant_id_arg, payload):
        captured_alerts.append((tenant_id_arg, payload))

    # Build a minimal ARQ ctx with a mock db_factory
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc]

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_session)
    ctx = {"db_factory": mock_factory}

    with patch("app.modules.alerts.service.create_alert", side_effect=mock_create_alert):
        from app.worker import task_check_document_expiry

        result = await task_check_document_expiry(ctx)

    assert "1" in result, f"Expected 1 alert in result message, got: {result!r}"
    assert len(captured_alerts) == 1, f"Expected 1 captured alert, got {len(captured_alerts)}"

    _tid, alert = captured_alerts[0]
    assert alert.entity_type == "driver"
    assert alert.entity_id == subject_id
    assert alert.priority == "high", f"15-day expiry should be 'high', got {alert.priority!r}"
    assert f"doc_expiry:{doc_id}" in alert.request_reference
    assert expiry.isoformat() in alert.request_reference
    assert alert.channel == "dashboard"
    assert alert.alert_type == "document_expiring_soon"


async def test_doc_expiry_critical_priority():
    """TP-10: Document expiring in 5 days gets priority='critical'."""
    doc_id = uuid.uuid4()
    subject_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    expiry = date.today() + timedelta(days=5)

    mock_doc = MagicMock()
    mock_doc.id = doc_id
    mock_doc.tenant_id = tenant_id
    mock_doc.subject_type = "vehicle"
    mock_doc.subject_id = subject_id
    mock_doc.document_type = "insurance"
    mock_doc.expiry_date = expiry

    captured_alerts: list = []

    async def mock_create_alert(db, tenant_id_arg, payload):
        captured_alerts.append(payload)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_doc]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": MagicMock(return_value=mock_session)}

    with patch("app.modules.alerts.service.create_alert", side_effect=mock_create_alert):
        from app.worker import task_check_document_expiry

        await task_check_document_expiry(ctx)

    assert len(captured_alerts) == 1
    assert captured_alerts[0].priority == "critical", (
        f"5-day expiry should be 'critical', got {captured_alerts[0].priority!r}"
    )


async def test_doc_expiry_alert_error_continues():
    """TP-10: If create_alert raises for one doc, the task continues without aborting."""
    doc_id_1, doc_id_2 = uuid.uuid4(), uuid.uuid4()
    tenant_id = uuid.uuid4()
    expiry_1 = date.today() + timedelta(days=3)
    expiry_2 = date.today() + timedelta(days=20)

    def make_doc(doc_id, expiry, doc_type):
        m = MagicMock()
        m.id = doc_id
        m.tenant_id = tenant_id
        m.subject_type = "driver"
        m.subject_id = uuid.uuid4()
        m.document_type = doc_type
        m.expiry_date = expiry
        return m

    docs = [make_doc(doc_id_1, expiry_1, "passport"), make_doc(doc_id_2, expiry_2, "license")]

    call_count = 0

    async def mock_create_alert_raises_first(db, tenant_id_arg, payload):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("simulated alert failure")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = docs
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": MagicMock(return_value=mock_session)}

    with patch(
        "app.modules.alerts.service.create_alert",
        side_effect=mock_create_alert_raises_first,
    ):
        from app.worker import task_check_document_expiry

        result = await task_check_document_expiry(ctx)

    # First doc raised, second succeeded → 1 alert counted
    assert "1" in result
    assert call_count == 2, "create_alert should have been called for both docs"


async def test_doc_expiry_no_docs():
    """TP-10: No expiring documents → task returns 0 alerts, no errors."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    ctx = {"db_factory": MagicMock(return_value=mock_session)}

    from app.worker import task_check_document_expiry

    result = await task_check_document_expiry(ctx)
    assert "0" in result


async def test_worker_settings_registration():
    """TP-10: task_check_document_expiry is in WorkerSettings.functions and cron_jobs."""
    from app.worker import WorkerSettings, task_check_document_expiry

    assert task_check_document_expiry in WorkerSettings.functions, (
        "task_check_document_expiry must be in WorkerSettings.functions"
    )
    cron_funcs = [c.coroutine for c in WorkerSettings.cron_jobs]
    assert task_check_document_expiry in cron_funcs, (
        "task_check_document_expiry must be registered in WorkerSettings.cron_jobs"
    )


# ── TP-02: ThirdParty CRUD ────────────────────────────────────────────────────


async def test_create_third_party(async_client, auth_headers):
    """POST /api/v1/third-party creates and returns a third party."""
    resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Petromoc Maputo", "status": "active", "nuit": "400999000"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Petromoc Maputo"
    assert data["status"] == "active"
    assert data["nuit"] == "400999000"
    assert "id" in data


async def test_create_third_party_duplicate_nuit(async_client, auth_headers):
    """POST with duplicate NUIT for same tenant returns 409."""
    payload = {"name": "Empresa A", "nuit": f"5001{str(uuid.uuid4().int)[:5]}"}
    await async_client.post("/api/v1/third-party", json=payload, headers=auth_headers)
    resp = await async_client.post("/api/v1/third-party", json=payload, headers=auth_headers)
    assert resp.status_code == 409


async def test_list_third_parties(async_client, auth_headers):
    """GET /api/v1/third-party returns the created third parties."""
    await async_client.post(
        "/api/v1/third-party",
        json={"name": "Empresa Lista", "status": "active"},
        headers=auth_headers,
    )
    resp = await async_client.get("/api/v1/third-party", headers=auth_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


async def test_get_and_update_third_party(async_client, auth_headers):
    """GET + PATCH /api/v1/third-party/{id} — full CRUD round-trip."""
    create_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Empresa Update", "status": "active"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    tp_id = create_resp.json()["id"]

    get_resp = await async_client.get(f"/api/v1/third-party/{tp_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == tp_id

    patch_resp = await async_client.patch(
        f"/api/v1/third-party/{tp_id}",
        json={"status": "inactive"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "inactive"


async def test_third_party_cross_tenant_isolation(async_client, auth_headers, db):
    """Third party from tenant A is not accessible to tenant B."""
    from app.modules.tenants.models import Tenant

    create_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Empresa Isolada", "status": "active"},
        headers=auth_headers,
    )
    tp_id = create_resp.json()["id"]

    tenant_b = Tenant(name="Tenant B TP", slug=f"tb-tp-{uuid.uuid4().hex[:6]}")
    db.add(tenant_b)
    await db.commit()
    await db.refresh(tenant_b)

    other_headers = {"Authorization": "Bearer test-token", "X-Tenant-Id": str(tenant_b.id)}
    resp = await async_client.get(f"/api/v1/third-party/{tp_id}", headers=other_headers)
    assert resp.status_code == 404


async def test_create_and_list_roles(async_client, auth_headers):
    """POST + GET /api/v1/third-party/{id}/roles."""
    create_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Fornecedor Combustivel", "status": "active"},
        headers=auth_headers,
    )
    tp_id = create_resp.json()["id"]

    role_resp = await async_client.post(
        f"/api/v1/third-party/{tp_id}/roles",
        json={"role_type": "fuel_supplier", "is_active": True},
        headers=auth_headers,
    )
    assert role_resp.status_code == 201
    assert role_resp.json()["role_type"] == "fuel_supplier"

    list_resp = await async_client.get(f"/api/v1/third-party/{tp_id}/roles", headers=auth_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_duplicate_role_rejected(async_client, auth_headers):
    """Adding the same role twice returns 409."""
    create_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Fornecedor Dup", "status": "active"},
        headers=auth_headers,
    )
    tp_id = create_resp.json()["id"]
    role_payload = {"role_type": "fuel_supplier", "is_active": True}
    await async_client.post(
        f"/api/v1/third-party/{tp_id}/roles", json=role_payload, headers=auth_headers
    )
    resp = await async_client.post(
        f"/api/v1/third-party/{tp_id}/roles", json=role_payload, headers=auth_headers
    )
    assert resp.status_code == 409


# ── TP-05: DriverVehicleAssignment ───────────────────────────────────────────


async def test_assign_and_unassign_driver_vehicle(async_client, auth_headers, db, tenant_id):
    """POST + DELETE driver-vehicle-assignments creates and soft-deletes assignment."""
    from app.modules.drivers.models import Driver
    from app.modules.vehicles.models import Vehicle

    driver = Driver(tenant_id=tenant_id, full_name="Motorista Atribuição", status="active")
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add_all([driver, vehicle])
    await db.commit()
    await db.refresh(driver)
    await db.refresh(vehicle)

    assign_resp = await async_client.post(
        "/api/v1/third-party/driver-vehicle-assignments",
        json={
            "driver_id": str(driver.id),
            "vehicle_id": str(vehicle.id),
            "assignment_type": "primary",
        },
        headers=auth_headers,
    )
    assert assign_resp.status_code == 201, assign_resp.text
    assignment_id = assign_resp.json()["id"]
    assert assign_resp.json()["unassigned_at"] is None

    unassign_resp = await async_client.delete(
        f"/api/v1/third-party/driver-vehicle-assignments/{assignment_id}",
        headers=auth_headers,
    )
    assert unassign_resp.status_code == 200
    assert unassign_resp.json()["unassigned_at"] is not None


async def test_assignment_cross_tenant_rejected(async_client, auth_headers, db, tenant_id):
    """Cannot assign a driver from tenant B to a vehicle from tenant A."""
    from app.modules.drivers.models import Driver
    from app.modules.tenants.models import Tenant
    from app.modules.vehicles.models import Vehicle

    tenant_b = Tenant(name="Tenant B Assign", slug=f"tb-assign-{uuid.uuid4().hex[:6]}")
    db.add(tenant_b)
    await db.commit()
    await db.refresh(tenant_b)

    other_driver = Driver(
        tenant_id=tenant_b.id, full_name="Motorista Outro Tenant", status="active"
    )
    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid.uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add_all([other_driver, vehicle])
    await db.commit()
    await db.refresh(other_driver)
    await db.refresh(vehicle)

    resp = await async_client.post(
        "/api/v1/third-party/driver-vehicle-assignments",
        json={
            "driver_id": str(other_driver.id),
            "vehicle_id": str(vehicle.id),
            "assignment_type": "primary",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── TP-06: OperationalDocument ───────────────────────────────────────────────


async def test_create_and_verify_operational_document(async_client, auth_headers, db, tenant_id):
    """POST /documents + POST /documents/{id}/verify round-trip."""
    from app.modules.drivers.models import Driver

    driver = Driver(tenant_id=tenant_id, full_name="Motorista Documento", status="active")
    db.add(driver)
    await db.commit()
    await db.refresh(driver)

    expiry = (date.today() + timedelta(days=60)).isoformat()
    create_resp = await async_client.post(
        "/api/v1/third-party/documents",
        json={
            "subject_type": "driver",
            "subject_id": str(driver.id),
            "document_type": "driving_license",
            "document_number": "L-MZ-2024-001",
            "expiry_date": expiry,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    doc_id = create_resp.json()["id"]
    assert create_resp.json()["verification_status"] == "pending"

    verify_resp = await async_client.post(
        f"/api/v1/third-party/documents/{doc_id}/verify",
        json={"verification_status": "verified"},
        headers=auth_headers,
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verification_status"] == "verified"


async def test_list_documents_by_subject(async_client, auth_headers, db, tenant_id):
    """GET /documents?subject_type=driver filters correctly."""
    from app.modules.drivers.models import Driver

    driver = Driver(tenant_id=tenant_id, full_name="Motorista Lista Doc", status="active")
    db.add(driver)
    await db.commit()
    await db.refresh(driver)

    await async_client.post(
        "/api/v1/third-party/documents",
        json={
            "subject_type": "driver",
            "subject_id": str(driver.id),
            "document_type": "driving_license",
        },
        headers=auth_headers,
    )

    resp = await async_client.get(
        f"/api/v1/third-party/documents?subject_type=driver&subject_id={driver.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(row["subject_type"] == "driver" for row in data)


async def test_expiring_documents_endpoint(async_client, auth_headers, db, tenant_id):
    """GET /documents/expiring?days_ahead=30 returns docs expiring within 30 days."""
    from app.modules.drivers.models import Driver

    driver = Driver(tenant_id=tenant_id, full_name="Motorista Expiry", status="active")
    db.add(driver)
    await db.commit()
    await db.refresh(driver)

    expiry = (date.today() + timedelta(days=10)).isoformat()
    await async_client.post(
        "/api/v1/third-party/documents",
        json={
            "subject_type": "driver",
            "subject_id": str(driver.id),
            "document_type": "driving_license",
            "expiry_date": expiry,
        },
        headers=auth_headers,
    )

    resp = await async_client.get(
        "/api/v1/third-party/documents/expiring?days_ahead=30",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert any(row["expiry_date"] == expiry for row in data)


# ── TP-11: Party Directory UNION ALL (Plan 08) ───────────────────────────────


async def test_party_directory_union_all(async_client, auth_headers, db, tenant_id):
    """GET /party-directory returns entries from drivers, clients, and third_parties."""
    from app.modules.clients.models import Client
    from app.modules.drivers.models import Driver

    driver = Driver(tenant_id=tenant_id, full_name="Américo Machava", status="active")
    client = Client(
        tenant_id=tenant_id,
        trading_name="Transportes Beira Lda",
        nuit=f"4001{uuid.uuid4().int % 100000:05d}",
        is_active=True,
    )
    db.add_all([driver, client])
    await db.commit()

    tp_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Petromoc Maputo", "status": "active"},
        headers=auth_headers,
    )
    assert tp_resp.status_code == 201

    resp = await async_client.get("/api/v1/third-party/party-directory", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    types_found = {row["subject_type"] for row in data}
    assert "driver" in types_found
    assert "client" in types_found
    assert "third_party" in types_found

    for row in data:
        assert "subject_id" in row
        assert "name" in row
        assert "status" in row


async def test_party_directory_filter_subject_type(async_client, auth_headers, db, tenant_id):
    """?subject_type=third_party returns ONLY third_party rows."""
    from app.modules.drivers.models import Driver

    driver = Driver(tenant_id=tenant_id, full_name="Driver Filter Test", status="active")
    db.add(driver)
    await db.commit()

    tp_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Filtered TP", "status": "active"},
        headers=auth_headers,
    )
    assert tp_resp.status_code == 201

    resp = await async_client.get(
        "/api/v1/third-party/party-directory?subject_type=third_party",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all(row["subject_type"] == "third_party" for row in data)


async def test_party_directory_name_search(async_client, auth_headers, db, tenant_id):
    """?q=<fragment> returns only entries whose name matches."""
    from app.modules.drivers.models import Driver

    driver_a = Driver(tenant_id=tenant_id, full_name="Américo Machava", status="active")
    driver_b = Driver(tenant_id=tenant_id, full_name="João Nhantumbo", status="active")
    db.add_all([driver_a, driver_b])
    await db.commit()

    resp = await async_client.get(
        "/api/v1/third-party/party-directory?q=Américo",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert all("américo" in row["name"].lower() for row in data)


async def test_party_directory_cross_tenant_isolation(async_client, auth_headers, db, tenant_id):
    """Party directory does not return entries from another tenant."""
    from app.modules.drivers.models import Driver
    from app.modules.tenants.models import Tenant

    tenant_b = Tenant(name="Tenant B Dir", slug=f"tb-dir-{uuid.uuid4().hex[:6]}")
    db.add(tenant_b)
    await db.commit()
    await db.refresh(tenant_b)

    other_driver = Driver(
        tenant_id=tenant_b.id, full_name="Motorista Outro Tenant Dir", status="active"
    )
    db.add(other_driver)
    await db.commit()

    resp = await async_client.get("/api/v1/third-party/party-directory", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert str(other_driver.id) not in {row["subject_id"] for row in data}


# ── F7.3 Specific Tests ────────────────────────────────────────────────────────


async def test_create_role_client_accepted(async_client, auth_headers):
    """F7.3: POST /{tp_id}/roles accepts role_type='client' with 201 Created."""
    create_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": "Cliente Papel Teste", "status": "active"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    tp_id = create_resp.json()["id"]

    role_resp = await async_client.post(
        f"/api/v1/third-party/{tp_id}/roles",
        json={"role_type": "client", "is_active": True},
        headers=auth_headers,
    )
    assert role_resp.status_code == 201, role_resp.text
    role_data = role_resp.json()
    assert role_data["role_type"] == "client"
    assert role_data["is_active"] is True


async def test_party_directory_single_role_migrated_client(async_client, auth_headers, db, tenant_id):
    """F7.3: Full client creation lifecycle -> Party Directory returns 1 deduplicated entry as third_party."""
    from sqlalchemy import select
    from app.modules.clients.models import Client
    from app.modules.third_party.models import ThirdParty, ThirdPartyRole

    # NUIT must be 9 digits — hex slices leak a-f and fail schema validation.
    unique_nuit = f"4002{uuid.uuid4().int % 100000:05d}"
    client_name = f"ABC Transportes {uuid.uuid4().hex[:4]} Lda"

    # 1. Create client via clients API
    client_resp = await async_client.post(
        "/api/v1/clients",
        json={
            "trading_name": client_name,
            "legal_name": client_name,
            "nuit": unique_nuit,
            "client_type": "organization",
            "payment_terms_days": 30,
        },
        headers=auth_headers,
    )
    assert client_resp.status_code == 201, client_resp.text
    client_id = uuid.UUID(client_resp.json()["id"])

    # 2. Verify DB state: Client.third_party_id != None, ThirdParty exists, ThirdPartyRole(client) exists
    client_row = await db.get(Client, client_id)
    assert client_row is not None
    assert client_row.third_party_id is not None

    tp_row = await db.get(ThirdParty, client_row.third_party_id)
    assert tp_row is not None
    assert tp_row.name == client_name

    role_result = await db.execute(
        select(ThirdPartyRole).where(
            ThirdPartyRole.third_party_id == tp_row.id,
            ThirdPartyRole.role_type == "client",
            ThirdPartyRole.is_active.is_(True),
        )
    )
    assert role_result.scalar_one_or_none() is not None

    # 3. Query directory by query string
    dir_resp = await async_client.get(
        f"/api/v1/third-party/party-directory?q={client_name}",
        headers=auth_headers,
    )
    assert dir_resp.status_code == 200, dir_resp.text
    matches = [r for r in dir_resp.json() if r["name"] == client_name]

    # 4. Assert exact deduplication
    assert len(matches) == 1, f"Expected exactly 1 entry for migrated client, got {len(matches)}"
    assert matches[0]["subject_id"] == str(tp_row.id)
    assert matches[0]["subject_type"] == "third_party"
    assert set(matches[0]["roles"]) == {"client"}


async def test_party_directory_multi_role_aggregation(async_client, auth_headers):
    """F7.3: ThirdParty with multiple roles (client + service_provider) returns 1 entry with aggregated roles."""
    tp_name = f"Logística Multi Role {uuid.uuid4().hex[:6]}"
    create_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": tp_name, "status": "active"},
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    tp_id = create_resp.json()["id"]

    # Assign role: client
    r1 = await async_client.post(
        f"/api/v1/third-party/{tp_id}/roles",
        json={"role_type": "client", "is_active": True},
        headers=auth_headers,
    )
    assert r1.status_code == 201

    # Assign role: service_provider
    r2 = await async_client.post(
        f"/api/v1/third-party/{tp_id}/roles",
        json={"role_type": "service_provider", "is_active": True},
        headers=auth_headers,
    )
    assert r2.status_code == 201

    dir_resp = await async_client.get(
        f"/api/v1/third-party/party-directory?q={tp_name}",
        headers=auth_headers,
    )
    assert dir_resp.status_code == 200
    matches = [r for r in dir_resp.json() if r["name"] == tp_name]

    assert len(matches) == 1, f"Expected 1 aggregated entry, got {len(matches)}"
    assert matches[0]["subject_type"] == "third_party"
    assert set(matches[0]["roles"]) == {"client", "service_provider"}


async def test_party_directory_legacy_client_visible(async_client, auth_headers, db, tenant_id):
    """F7.3: Legacy client (third_party_id IS NULL) remains visible as subject_type='client'."""
    from app.modules.clients.models import Client

    legacy_name = f"Cliente Legado {uuid.uuid4().hex[:6]}"
    legacy_client = Client(
        tenant_id=tenant_id,
        trading_name=legacy_name,
        nuit=f"4003{uuid.uuid4().hex[:5]}",
        is_active=True,
        third_party_id=None,
    )
    db.add(legacy_client)
    await db.commit()

    dir_resp = await async_client.get(
        f"/api/v1/third-party/party-directory?q={legacy_name}",
        headers=auth_headers,
    )
    assert dir_resp.status_code == 200
    matches = [r for r in dir_resp.json() if r["name"] == legacy_name]

    assert len(matches) == 1, f"Expected 1 legacy client entry, got {len(matches)}"
    assert matches[0]["subject_id"] == str(legacy_client.id)
    assert matches[0]["subject_type"] == "client"


async def test_provinces_and_profiles_and_payments_typed_responses(async_client, auth_headers):
    """F7.3: Verify provinces, profiles, and payments endpoints return expected typed structures."""
    # 1. Provinces
    prov_resp = await async_client.get("/api/v1/third-party/provinces")
    assert prov_resp.status_code == 200
    assert isinstance(prov_resp.json(), list)

    # 2. Third Party + Supplier Profile
    tp_resp = await async_client.post(
        "/api/v1/third-party",
        json={"name": f"Fornecedor Typed {uuid.uuid4().hex[:4]}", "status": "active"},
        headers=auth_headers,
    )
    assert tp_resp.status_code == 201
    tp_id = tp_resp.json()["id"]

    supp_resp = await async_client.put(
        f"/api/v1/third-party/{tp_id}/supplier-profile",
        json={"payment_terms": "30_days", "bank_name": "Standard Bank"},
        headers=auth_headers,
    )
    assert supp_resp.status_code == 200
    supp_data = supp_resp.json()
    assert supp_data["third_party_id"] == tp_id
    assert supp_data["payment_terms"] == "30_days"

    # 3. Service Provider Profile
    sp_resp = await async_client.put(
        f"/api/v1/third-party/{tp_id}/service-provider-profile",
        json={"response_time_hours": 4, "rate_per_hour": "1500.00"},
        headers=auth_headers,
    )
    assert sp_resp.status_code == 200
    sp_data = sp_resp.json()
    assert sp_data["third_party_id"] == tp_id
    assert sp_data["response_time_hours"] == 4

    # 4. Payment
    pay_resp = await async_client.post(
        f"/api/v1/third-party/{tp_id}/payments",
        json={"amount": "25000.00", "currency": "MZN", "description": "Pagamento Adiantado"},
        headers=auth_headers,
    )
    assert pay_resp.status_code == 201
    pay_data = pay_resp.json()
    assert pay_data["third_party_id"] == tp_id
    assert pay_data["amount"] == "25000.00"
    assert pay_data["entry_type"] == "credit"

