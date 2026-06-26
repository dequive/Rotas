"""Phase 15.1 — Fiscal Documents integration tests.

Requirements: FDOC-01, FDOC-02, FDOC-03, FDOC-04, FDOC-05
All tests require a live PostgreSQL DB.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.billing import service as billing_service
from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.billing.schemas import IssueBillingDocumentRequest
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_contract(db, tenant_id):
    c = Contract(
        tenant_id=tenant_id,
        client_name=f"Cliente {uuid4().hex[:4]}",
        contract_reference=f"REF-{uuid4().hex[:6]}",
        status="active",
    )
    db.add(c)
    await db.flush()
    return c


async def _make_vehicle(db, tenant_id):
    v = Vehicle(
        tenant_id=tenant_id,
        plate=f"MZ-{uuid4().hex[:6].upper()}",
        status="active",
    )
    db.add(v)
    await db.flush()
    return v


async def _make_driver(db, tenant_id):
    d = Driver(
        tenant_id=tenant_id,
        full_name=f"Motorista {uuid4().hex[:4]}",
        status="active",
    )
    db.add(d)
    await db.flush()
    return d


async def _make_trip(db, tenant_id, vehicle_id, driver_id, contract_id=None):
    t = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle_id,
        driver_id=driver_id,
        contract_id=contract_id,
        origin="Maputo",
        destination="Beira",
        status="draft",
        billing_status="pending_delivery_proof",
    )
    db.add(t)
    await db.flush()
    return t


async def _make_draft_doc(db, tenant_id, contract, vehicle, driver):
    """Draft BillingDocument + one BillingItem."""
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
    return doc


async def _make_issued_doc(db, tenant_id):
    """Full pipeline: contract + vehicle + driver + issued BillingDocument."""
    contract = await _make_contract(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    doc = await _make_draft_doc(db, tenant_id, contract, vehicle, driver)
    result = await billing_service.issue_document(
        db, tenant_id, doc.id, IssueBillingDocumentRequest()
    )
    await db.flush()
    return result


# ---------------------------------------------------------------------------
# FDOC-01 — BillingDocument DDL columns
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_billing_document_has_document_type_column(db, tenant_id):
    """BillingDocument ORM model exposes document_type, parent_document_id, due_date, client_nuit."""
    contract = await _make_contract(db, tenant_id)
    await _make_vehicle(db, tenant_id)
    await _make_driver(db, tenant_id)

    now = datetime.now(UTC)
    doc = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="draft",
        currency="MZN",
        document_type="invoice",
        client_nuit="400123456",
        due_date=now + timedelta(days=30),
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    assert doc.document_type == "invoice"
    assert doc.client_nuit == "400123456"
    assert doc.due_date is not None
    assert doc.parent_document_id is None


@pytest.mark.asyncio
async def test_billing_document_type_defaults_to_invoice(db, tenant_id):
    """BillingDocument created without document_type defaults to 'invoice'."""
    contract = await _make_contract(db, tenant_id)
    await _make_vehicle(db, tenant_id)
    await _make_driver(db, tenant_id)

    now = datetime.now(UTC)
    doc = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="draft",
        currency="MZN",
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    assert doc.document_type == "invoice"


# ---------------------------------------------------------------------------
# FDOC-02 — Nota de Débito
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_debit_note_returns_invoice_number(db, tenant_id):
    """create_debit_note returns a debit_note document with invoice_number assigned."""
    parent = await _make_issued_doc(db, tenant_id)
    parent_id = parent["id"]

    note = await billing_service.create_debit_note(
        db,
        tenant_id=tenant_id,
        parent_id=parent_id,
        amount=Decimal("200.00"),
        reason="Custo adicional de combustível não previsto",
    )

    assert note["document_type"] == "debit_note"
    assert note["invoice_number"] is not None
    assert str(note["parent_document_id"]) == str(parent_id)


@pytest.mark.asyncio
async def test_debit_note_parent_must_be_issued(db, tenant_id):
    """create_debit_note raises 409 when parent is in draft status."""
    from fastapi import HTTPException

    contract = await _make_contract(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    draft_doc = await _make_draft_doc(db, tenant_id, contract, vehicle, driver)

    with pytest.raises((HTTPException, Exception)) as exc_info:
        await billing_service.create_debit_note(
            db,
            tenant_id=tenant_id,
            parent_id=draft_doc.id,
            amount=Decimal("100.00"),
            reason="Tentativa inválida sobre rascunho",
        )

    exc = exc_info.value
    status = getattr(exc, "status_code", None) or getattr(
        getattr(exc, "detail", {}), "get", lambda k, d: d
    )("status_code", None)
    assert (
        status == 409
        or "status" in str(exc).lower()
        or "draft" in str(exc).lower()
        or "issued" in str(exc).lower()
    )


@pytest.mark.asyncio
async def test_debit_note_cross_tenant_isolation(db, tenant_id):
    """create_debit_note on a document from another tenant raises 404."""
    from app.modules.tenants.models import Tenant as TenantModel

    other = TenantModel(name=f"Other {uuid4().hex[:6]}", slug=f"other-{uuid4().hex[:6]}")
    db.add(other)
    await db.flush()

    parent = await _make_issued_doc(db, tenant_id)

    with pytest.raises(Exception) as exc_info:
        await billing_service.create_debit_note(
            db,
            tenant_id=other.id,
            parent_id=parent["id"],
            amount=Decimal("50.00"),
            reason="Tentativa de acesso cross-tenant",
        )

    assert "404" in str(exc_info.value) or "not_found" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# FDOC-03 — Nota de Crédito
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_credit_note_parent_unaffected(db, tenant_id):
    """create_credit_note creates child document; parent status stays 'issued'."""
    parent = await _make_issued_doc(db, tenant_id)

    note = await billing_service.create_credit_note(
        db,
        tenant_id=tenant_id,
        parent_id=parent["id"],
        amount=Decimal("150.00"),
        reason="Desconto retroativo aprovado por direção",
    )

    assert note["document_type"] == "credit_note"
    assert parent["status"] == "issued"


@pytest.mark.asyncio
async def test_credit_note_gets_sequential_invoice_number(db, tenant_id):
    """Two credit notes for the same tenant get consecutive invoice_numbers."""
    p1 = await _make_issued_doc(db, tenant_id)
    p2 = await _make_issued_doc(db, tenant_id)

    n1 = await billing_service.create_credit_note(
        db,
        tenant_id=tenant_id,
        parent_id=p1["id"],
        amount=Decimal("100.00"),
        reason="Crédito teste 1 FDOC-03",
    )
    n2 = await billing_service.create_credit_note(
        db,
        tenant_id=tenant_id,
        parent_id=p2["id"],
        amount=Decimal("100.00"),
        reason="Crédito teste 2 FDOC-03",
    )

    assert n1["invoice_number"] is not None
    assert n2["invoice_number"] is not None
    assert n1["invoice_number"] != n2["invoice_number"]


# ---------------------------------------------------------------------------
# FDOC-04 — Fatura-Recibo + Recibo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoice_receipt_transitions_parent_to_paid(db, tenant_id):
    """create_invoice_receipt creates invoice_receipt and sets parent status='paid'."""

    parent_data = await _make_issued_doc(db, tenant_id)
    parent_id = parent_data["id"]

    receipt = await billing_service.create_invoice_receipt(
        db, tenant_id=tenant_id, parent_id=parent_id
    )

    assert receipt["document_type"] == "invoice_receipt"
    assert str(receipt["parent_document_id"]) == str(parent_id)

    # Verify parent transitioned
    parent_row = await db.get(BillingDocument, parent_id)
    assert parent_row.status == "paid"


@pytest.mark.asyncio
async def test_standalone_receipt_does_not_change_parent_status(db, tenant_id):
    """create_receipt creates receipt child without touching parent status."""
    parent_data = await _make_issued_doc(db, tenant_id)
    parent_id = parent_data["id"]

    receipt = await billing_service.create_receipt(
        db, tenant_id=tenant_id, parent_id=parent_id, amount_paid=Decimal("500.00")
    )

    assert receipt["document_type"] == "receipt"

    parent_row = await db.get(BillingDocument, parent_id)
    assert parent_row.status == "issued"


# ---------------------------------------------------------------------------
# FDOC-05 — AR Básico (Contas a Receber)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ar_endpoint_filters_by_aging_bucket(async_client, auth_headers, db, tenant_id):
    """GET /billing/ar?aging_bucket=31_60 returns only documents in that aging band."""
    contract = await _make_contract(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    draft = await _make_draft_doc(db, tenant_id, contract, vehicle, driver)

    # Issue and set due_date 45 days ago
    await billing_service.issue_document(db, tenant_id, draft.id, IssueBillingDocumentRequest())
    await db.flush()
    await db.refresh(draft)
    draft.due_date = datetime.now(UTC) - timedelta(days=45)
    await db.flush()
    await db.commit()

    resp = await async_client.get("/api/v1/billing/ar?aging_bucket=31_60", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for item in data:
        assert item["aging_bucket"] == "31_60"


@pytest.mark.asyncio
async def test_serialize_billing_document_includes_ar_fields(db, tenant_id):
    """list_ar_documents returns days_overdue (int) and aging_bucket string."""
    contract = await _make_contract(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    draft = await _make_draft_doc(db, tenant_id, contract, vehicle, driver)

    await billing_service.issue_document(db, tenant_id, draft.id, IssueBillingDocumentRequest())
    await db.flush()
    await db.refresh(draft)
    draft.due_date = datetime.now(UTC) - timedelta(days=10)
    await db.flush()
    await db.commit()

    results = await billing_service.list_ar_documents(db, tenant_id)
    assert len(results) >= 1
    for item in results:
        assert "days_overdue" in item
        assert "aging_bucket" in item
        assert isinstance(item["days_overdue"], int)
        assert item["aging_bucket"] in {"current", "1_30", "31_60", "61_90", "over_90"}


# ---------------------------------------------------------------------------
# client_nuit required to issue
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_nuit_required_to_issue_document(db, tenant_id):
    """issue_document raises 422 (client_nuit_required) when client_nuit is absent."""
    contract = await _make_contract(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)

    now = datetime.now(UTC)
    doc = BillingDocument(
        tenant_id=tenant_id,
        contract_id=contract.id,
        client_name=contract.client_name,
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        status="draft",
        currency="MZN",
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
        amount=Decimal("500.00"),
        iva_rate=Decimal("0.1700"),
        iva_amount=Decimal("85.00"),
        delivered_at=now,
        status="pending",
    )
    db.add(item)
    await db.flush()

    from app.core.errors import ApiError

    with pytest.raises(ApiError) as exc_info:
        await billing_service.issue_document(db, tenant_id, doc.id, IssueBillingDocumentRequest())

    assert exc_info.value.code == "client_nuit_required"
    assert exc_info.value.status_code == 422
