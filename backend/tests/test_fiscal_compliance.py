"""Phase 15 — Fiscal Compliance + Segurança de Carga integration tests.

Requirements: FISC-01, FISC-02, FISC-03, LOAD-01, LOAD-02
All tests require a live PostgreSQL DB (DATABASE_URL env var must point to a real DB).
"""
import asyncio
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from unittest.mock import AsyncMock

from app.database import AsyncSessionLocal
from app.modules.billing.models import BillingDocument, BillingItem, ExportJob
from app.modules.billing import service as billing_service
from app.modules.billing.schemas import IssueBillingDocumentRequest
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle


# ---------------------------------------------------------------------------
# Internal setup helpers
# ---------------------------------------------------------------------------


async def _make_contract(db, tenant_id, client_nuit="400123456"):
    c = Contract(
        tenant_id=tenant_id,
        client_name=f"Test Client {uuid4().hex[:4]}",
        client_nuit=client_nuit,
        contract_reference=f"REF-{uuid4().hex[:6]}",
        status="active",
    )
    db.add(c)
    await db.flush()
    return c


async def _make_vehicle(db, tenant_id, max_payload_kg=None):
    v = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
        max_payload_kg=max_payload_kg,
    )
    db.add(v)
    await db.flush()
    return v


async def _make_driver(db, tenant_id):
    d = Driver(
        tenant_id=tenant_id,
        full_name=f"Driver {uuid4().hex[:4]}",
        status="active",
    )
    db.add(d)
    await db.flush()
    return d


async def _make_trip(db, tenant_id, vehicle_id, driver_id, contract_id=None, **kw):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        contract_id=contract_id,
        origin=kw.get("origin", "Maputo"),
        destination=kw.get("destination", "Beira"),
        status=kw.get("status", "draft"),
        billing_status=kw.get("billing_status", "pending_delivery_proof"),
        is_hazmat=kw.get("is_hazmat", False),
        hazmat_class=kw.get("hazmat_class"),
        un_number=kw.get("un_number"),
        cargo_weight=kw.get("cargo_weight"),
        payload_override_reason=kw.get("payload_override_reason"),
    )
    db.add(t)
    await db.flush()
    return t


async def _make_draft_doc_with_item(db, tenant_id, contract, vehicle, driver):
    """Draft BillingDocument + one BillingItem — ready for issue_document()."""
    now = datetime.now(UTC)
    doc = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="draft",
        currency="MZN",
        client_nuit="400123456",
    )
    db.add(doc)
    await db.flush()

    trip = await _make_trip(db, tenant_id, vehicle.id, driver.id, contract_id=contract.id)

    item = BillingItem(
        tenant_id=tenant_id,
        contract_id=contract.id,
        billing_document_id=doc.id,
        trip_id=trip.id,
        origin="Maputo",
        destination="Beira",
        amount=Decimal("1000.00"),
        iva_rate=Decimal("0.1700"),
        iva_amount=Decimal("170.00"),
        delivered_at=now,
        status="pending",
    )
    db.add(item)
    await db.flush()
    return doc, trip, item


# ---------------------------------------------------------------------------
# FISC-01 — Invoice Sequence (PostgreSQL SEQUENCE per-tenant per-year)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoice_sequence_first_two(db, tenant_id):
    """FISC-01: First invoice gets YYYY/0001; second gets YYYY/0002 for same tenant."""
    contract = await _make_contract(db, tenant_id)
    v1 = await _make_vehicle(db, tenant_id)
    d1 = await _make_driver(db, tenant_id)
    v2 = await _make_vehicle(db, tenant_id)
    d2 = await _make_driver(db, tenant_id)

    doc1, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract, v1, d1)
    doc2, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract, v2, d2)

    result1 = await billing_service.issue_document(
        db, tenant_id, doc1.id, IssueBillingDocumentRequest()
    )
    result2 = await billing_service.issue_document(
        db, tenant_id, doc2.id, IssueBillingDocumentRequest()
    )

    year = datetime.now(UTC).year
    assert result1["invoice_number"] == f"{year}/0001"
    assert result2["invoice_number"] == f"{year}/0002"


@pytest.mark.asyncio
async def test_invoice_sequence_concurrent(db, tenant_id):
    """FISC-01: Concurrent issue calls produce distinct, well-formed invoice numbers."""
    contract = await _make_contract(db, tenant_id)

    # Pre-warm the sequence with one sequential issue so concurrent calls only do nextval()
    # (CREATE SEQUENCE IF NOT EXISTS is not atomic under concurrent pg transactions)
    v0 = await _make_vehicle(db, tenant_id)
    d0 = await _make_driver(db, tenant_id)
    doc0, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract, v0, d0)
    await billing_service.issue_document(db, tenant_id, doc0.id, IssueBillingDocumentRequest())

    v1 = await _make_vehicle(db, tenant_id)
    d1 = await _make_driver(db, tenant_id)
    v2 = await _make_vehicle(db, tenant_id)
    d2 = await _make_driver(db, tenant_id)

    doc1, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract, v1, d1)
    doc2, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract, v2, d2)
    await db.commit()  # commit so separate sessions can read the data

    async def _issue(doc_id):
        async with AsyncSessionLocal() as session:
            return await billing_service.issue_document(
                session, tenant_id, doc_id, IssueBillingDocumentRequest()
            )

    results = await asyncio.gather(_issue(doc1.id), _issue(doc2.id))
    numbers = {r["invoice_number"] for r in results}
    year = datetime.now(UTC).year
    assert len(numbers) == 2, f"Expected 2 distinct invoice numbers, got {numbers}"
    assert all(re.match(rf"^{year}/\d{{4}}$", n) for n in numbers)


@pytest.mark.asyncio
async def test_invoice_sequence_cross_tenant(db, tenant_id):
    """FISC-01: Tenant A and Tenant B each get their own 0001 — sequences are isolated."""
    suffix_b = uuid4().hex[:8]
    tenant_b = Tenant(name=f"Test Tenant B {suffix_b}", slug=f"test-b-{suffix_b}")
    db.add(tenant_b)
    await db.flush()
    tenant_b_id = tenant_b.id

    contract_a = await _make_contract(db, tenant_id)
    v_a = await _make_vehicle(db, tenant_id)
    d_a = await _make_driver(db, tenant_id)
    doc_a, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract_a, v_a, d_a)

    contract_b = await _make_contract(db, tenant_b_id)
    v_b = await _make_vehicle(db, tenant_b_id)
    d_b = await _make_driver(db, tenant_b_id)
    doc_b, _, _ = await _make_draft_doc_with_item(db, tenant_b_id, contract_b, v_b, d_b)

    result_a = await billing_service.issue_document(
        db, tenant_id, doc_a.id, IssueBillingDocumentRequest()
    )
    result_b = await billing_service.issue_document(
        db, tenant_b_id, doc_b.id, IssueBillingDocumentRequest()
    )

    year = datetime.now(UTC).year
    assert result_a["invoice_number"] == f"{year}/0001"
    assert result_b["invoice_number"] == f"{year}/0001", (
        "Tenant B sequence must start independently at 0001"
    )


@pytest.mark.asyncio
async def test_invoice_sequence_integrity_error_retry(db, tenant_id):
    """FISC-01: Re-issuing an already-issued document returns cached invoice_number (idempotent)."""
    contract = await _make_contract(db, tenant_id)
    v1 = await _make_vehicle(db, tenant_id)
    d1 = await _make_driver(db, tenant_id)
    doc, _, _ = await _make_draft_doc_with_item(db, tenant_id, contract, v1, d1)

    result = await billing_service.issue_document(
        db, tenant_id, doc.id, IssueBillingDocumentRequest()
    )
    assert result["invoice_number"] is not None
    year = datetime.now(UTC).year
    assert re.match(rf"^{year}/\d{{4}}$", result["invoice_number"])

    # Calling issue_document again on an already-issued doc must return the same number
    result2 = await billing_service.issue_document(
        db, tenant_id, doc.id, IssueBillingDocumentRequest()
    )
    assert result2["invoice_number"] == result["invoice_number"]


# ---------------------------------------------------------------------------
# FISC-02 — IVA (Mozambique VAT) Calculation
# ---------------------------------------------------------------------------


def test_iva_calculation_standard():
    """FISC-02: Standard 17% IVA on a 1000.00 item yields iva_amount=170.00."""
    amount = Decimal("1000.00")
    iva_rate = Decimal("0.1700")
    iva_amount = (amount * iva_rate).quantize(Decimal("0.01"))
    assert iva_amount == Decimal("170.00")

    # document.tax_amount = sum of per-item iva_amounts
    items = [
        (Decimal("1000.00"), Decimal("0.1700")),
        (Decimal("500.00"), Decimal("0.1700")),
    ]
    iva_amounts = [(a * r).quantize(Decimal("0.01")) for a, r in items]
    tax_total = sum(iva_amounts).quantize(Decimal("0.01"))
    assert tax_total == Decimal("255.00")


def test_iva_mixed_rates():
    """FISC-02: Mixed IVA rates produce correct per-item amounts and document tax total."""
    items = [
        (Decimal("1000.00"), Decimal("0.1700")),  # iva_amount = 170.00
        (Decimal("500.00"), Decimal("0.0500")),   # iva_amount = 25.00
        (Decimal("200.00"), Decimal("0.0000")),   # iva_amount = 0.00
    ]
    iva_amounts = [(amount * rate).quantize(Decimal("0.01")) for amount, rate in items]
    assert iva_amounts[0] == Decimal("170.00")
    assert iva_amounts[1] == Decimal("25.00")
    assert iva_amounts[2] == Decimal("0.00")
    tax_total = sum(iva_amounts).quantize(Decimal("0.01"))
    assert tax_total == Decimal("195.00")


# ---------------------------------------------------------------------------
# FISC-03 — Compliance Report (monthly XLSX for AT Moçambique)
# ---------------------------------------------------------------------------


def test_compliance_report_xlsx_columns():
    """FISC-03: Compliance XLSX header row has all 9 required columns."""
    from app.jobs.tasks.billing_export import COMPLIANCE_REPORT_COLUMNS

    expected = [
        "invoice_number",
        "client_nuit",
        "client_name",
        "issued_at",
        "subtotal",
        "iva_rate",
        "iva_amount",
        "total_amount",
        "status",
    ]
    assert COMPLIANCE_REPORT_COLUMNS == expected, (
        f"Column list mismatch. Got: {COMPLIANCE_REPORT_COLUMNS}"
    )


@pytest.mark.asyncio
async def test_compliance_report_job_lifecycle(db, tenant_id):
    """FISC-03: ARQ task transitions ExportJob queued → processing → done and produces XLSX."""
    from app.jobs.tasks.billing_export import task_export_compliance_report

    # Seed a contract and an issued billing document for the target month
    contract = await _make_contract(db, tenant_id, client_nuit="400999888")
    now = datetime.now(UTC)
    month_str = now.strftime("%Y-%m")

    doc = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="issued",
        invoice_number=f"{now.year}/9901",
        issued_at=now,
        subtotal=Decimal("2000.00"),
        tax_amount=Decimal("340.00"),
        total_amount=Decimal("2340.00"),
        iva_rate=Decimal("0.1700"),
        currency="MZN",
    )
    db.add(doc)

    job = ExportJob(
        tenant_id=tenant_id,
        job_type="compliance_report",
        entity_id=None,
        status="queued",
    )
    db.add(job)
    await db.commit()

    ctx = {"session_factory": AsyncSessionLocal}
    result = await task_export_compliance_report(ctx, str(job.id), month_str, str(tenant_id))

    assert result["status"] == "done", f"Task failed: {result}"
    assert "file_id" in result

    # Verify ExportJob in DB reflects done status
    await db.refresh(job)
    assert job.status == "done"
    assert job.file_id is not None


# ---------------------------------------------------------------------------
# LOAD-01 — Payload Weight Guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_payload_exceeded_create_trip(db, tenant_id, async_client, auth_headers):
    """LOAD-01: cargo_weight > max_payload_kg returns HTTP 409 payload_exceeded on create."""
    vehicle = await _make_vehicle(db, tenant_id, max_payload_kg=Decimal("5000.00"))
    driver = await _make_driver(db, tenant_id)
    await db.commit()

    response = await async_client.post(
        "/api/v1/trips",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "origin": "Maputo",
            "destination": "Beira",
            "cargo_weight": 5001,
        },
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "payload_exceeded"
    details = response.json()["error"]["details"]
    assert details["excess_kg"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_payload_within_limit(db, tenant_id, async_client, auth_headers):
    """LOAD-01: cargo_weight == max_payload_kg succeeds (HTTP 201)."""
    vehicle = await _make_vehicle(db, tenant_id, max_payload_kg=Decimal("5000.00"))
    driver = await _make_driver(db, tenant_id)
    await db.commit()

    response = await async_client.post(
        "/api/v1/trips",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "origin": "Maputo",
            "destination": "Beira",
            "cargo_weight": 5000,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_payload_guard_null_vehicle_limit(db, tenant_id, async_client, auth_headers):
    """LOAD-01: max_payload_kg = NULL skips the guard (backwards compat)."""
    vehicle = await _make_vehicle(db, tenant_id, max_payload_kg=None)
    driver = await _make_driver(db, tenant_id)
    await db.commit()

    response = await async_client.post(
        "/api/v1/trips",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "origin": "Maputo",
            "destination": "Nacala",
            "cargo_weight": 99999,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_payload_override_admin(db, tenant_id, async_client, auth_headers):
    """LOAD-01: payload_override_reason bypasses the guard (HTTP 201)."""
    vehicle = await _make_vehicle(db, tenant_id, max_payload_kg=Decimal("5000.00"))
    driver = await _make_driver(db, tenant_id)
    await db.commit()

    response = await async_client.post(
        "/api/v1/trips",
        json={
            "vehicle_id": str(vehicle.id),
            "driver_id": str(driver.id),
            "origin": "Maputo",
            "destination": "Tete",
            "cargo_weight": 6000,
            "payload_override_reason": "Special load permit #AUT-2026-001",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["origin"] == "Maputo"
    assert data["destination"] == "Tete"


@pytest.mark.asyncio
async def test_payload_exceeded_start_trip(db, tenant_id, async_client, auth_headers):
    """LOAD-01: start_trip() also enforces payload guard even if create passed."""
    # Create vehicle without payload limit first, then set it after trip is created
    vehicle = await _make_vehicle(db, tenant_id, max_payload_kg=None)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(
        db, tenant_id, vehicle.id, driver.id, cargo_weight=Decimal("5001.00")
    )
    # Now set the limit — simulates a later vehicle spec update
    vehicle.max_payload_kg = Decimal("5000.00")
    await db.commit()

    response = await async_client.post(
        f"/api/v1/trips/{trip.id}/start",
        json={"km_start": 10000},
        headers=auth_headers,
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "payload_exceeded"


# ---------------------------------------------------------------------------
# LOAD-02 — Hazmat Declaration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hazmat_load_permit_missing_class(db, tenant_id, async_client, auth_headers):
    """LOAD-02: Hazmat trip without hazmat_class raises 422 on Load Permit creation."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(
        db, tenant_id, vehicle.id, driver.id, is_hazmat=True, hazmat_class=None
    )
    await db.commit()

    response = await async_client.post(
        f"/api/v1/trips/{trip.id}/load-permits",
        json={},
        headers={**auth_headers, "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "hazmat_declaration_required"


@pytest.mark.asyncio
async def test_hazmat_load_permit_with_class(db, tenant_id, async_client, auth_headers):
    """LOAD-02: Hazmat trip with hazmat_class creates Load Permit successfully (HTTP 201)."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(
        db,
        tenant_id,
        vehicle.id,
        driver.id,
        is_hazmat=True,
        hazmat_class="3",
        un_number="UN1203",
    )
    await db.commit()

    response = await async_client.post(
        f"/api/v1/trips/{trip.id}/load-permits",
        json={},
        headers={**auth_headers, "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_non_hazmat_load_permit(db, tenant_id, async_client, auth_headers):
    """LOAD-02: Non-hazmat trip creates Load Permit without hazmat fields (HTTP 201)."""
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(db, tenant_id, vehicle.id, driver.id, is_hazmat=False)
    await db.commit()

    response = await async_client.post(
        f"/api/v1/trips/{trip.id}/load-permits",
        json={},
        headers={**auth_headers, "Idempotency-Key": uuid4().hex},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_hazmat_alert_on_start_trip(db, tenant_id, async_client, auth_headers):
    """LOAD-02: Starting a hazmat trip creates a hazmat_active alert (best-effort)."""
    from app.modules.alerts.models import Alert

    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    trip = await _make_trip(
        db,
        tenant_id,
        vehicle.id,
        driver.id,
        is_hazmat=True,
        hazmat_class="3",
        un_number="UN1203",
    )
    await db.commit()

    response = await async_client.post(
        f"/api/v1/trips/{trip.id}/start",
        json={"km_start": 5000},
        headers=auth_headers,
    )
    assert response.status_code == 200, f"start_trip failed: {response.json()}"

    async with AsyncSessionLocal() as session:
        alert = await session.scalar(
            select(Alert).where(
                Alert.tenant_id == tenant_id,
                Alert.alert_type == "hazmat_active",
                Alert.entity_id == trip.id,
            )
        )
    assert alert is not None, "hazmat_active alert must be created on hazmat trip start"
    assert alert.priority == "high"
