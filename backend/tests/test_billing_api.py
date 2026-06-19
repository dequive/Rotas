"""Phase 05 Plan 05 — CLI-05: invoice_number format and display tests.

Requirement: CLI-05 — Issued BillingDocument has invoice_number in AAAA/NNNN format.

The backend implementation (_assign_invoice_number) was completed in Phase 15.
This file adds a concise end-to-end confirmation test using the service layer directly,
consistent with the pattern established in test_fiscal_compliance.py.
"""
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.modules.billing.models import BillingDocument, BillingItem
from app.modules.billing import service as billing_service
from app.modules.billing.schemas import IssueBillingDocumentRequest
from app.modules.contracts.models import Contract
from app.modules.drivers.models import Driver
from app.modules.tenants.models import Tenant
from app.modules.trips.models import Trip
from app.modules.vehicles.models import Vehicle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_contract(db, tenant_id):
    c = Contract(
        tenant_id=tenant_id,
        client_name=f"CLI-05 Client {uuid4().hex[:6]}",
        contract_reference=f"CLI05-{uuid4().hex[:6]}",
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
        full_name=f"Driver {uuid4().hex[:6]}",
        status="active",
    )
    db.add(d)
    await db.flush()
    return d


async def _make_draft_doc_with_item(db, tenant_id, contract, vehicle, driver):
    """Draft BillingDocument with one BillingItem — ready for issue_document()."""
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

    trip = Trip(
        tenant_id=tenant_id,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
        contract_id=contract.id,
        origin="Maputo",
        destination="Beira",
        status="draft",
        billing_status="pending_delivery_proof",
    )
    db.add(trip)
    await db.flush()

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


# ---------------------------------------------------------------------------
# CLI-05 — Invoice Number Format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoice_number_format(db, tenant_id):
    """CLI-05: Issued BillingDocument has invoice_number in AAAA/NNNN format.

    _assign_invoice_number() is implemented in billing/service.py (Phase 15).
    This test confirms the feature works end-to-end — no new backend code needed.
    """
    contract = await _make_contract(db, tenant_id)
    vehicle = await _make_vehicle(db, tenant_id)
    driver = await _make_driver(db, tenant_id)
    doc = await _make_draft_doc_with_item(db, tenant_id, contract, vehicle, driver)

    result = await billing_service.issue_document(
        db, tenant_id, doc.id, IssueBillingDocumentRequest()
    )

    assert result.get("invoice_number") is not None, (
        "invoice_number must be populated after issue_document()"
    )
    year = datetime.now(UTC).year
    assert re.match(rf"^\d{{4}}/\d{{4}}$", result["invoice_number"]), (
        f"invoice_number '{result['invoice_number']}' must match AAAA/NNNN format"
    )
    assert result["invoice_number"].startswith(str(year)), (
        f"invoice_number year must be {year}, got '{result['invoice_number']}'"
    )


@pytest.mark.asyncio
async def test_invoice_number_increments(db, tenant_id):
    """CLI-05: Second issued document for same tenant gets a higher invoice number."""
    contract = await _make_contract(db, tenant_id)
    v1 = await _make_vehicle(db, tenant_id)
    d1 = await _make_driver(db, tenant_id)
    v2 = await _make_vehicle(db, tenant_id)
    d2 = await _make_driver(db, tenant_id)

    doc1 = await _make_draft_doc_with_item(db, tenant_id, contract, v1, d1)
    doc2 = await _make_draft_doc_with_item(db, tenant_id, contract, v2, d2)

    result1 = await billing_service.issue_document(
        db, tenant_id, doc1.id, IssueBillingDocumentRequest()
    )
    result2 = await billing_service.issue_document(
        db, tenant_id, doc2.id, IssueBillingDocumentRequest()
    )

    num1 = result1["invoice_number"]
    num2 = result2["invoice_number"]
    assert num1 != num2, "Two distinct documents must get distinct invoice numbers"

    # Extract sequence values and confirm the second is higher
    seq1 = int(num1.split("/")[1])
    seq2 = int(num2.split("/")[1])
    assert seq2 > seq1, (
        f"Second invoice number sequence ({seq2}) must be greater than first ({seq1})"
    )
