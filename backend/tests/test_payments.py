"""Phase 06 Plan 01 — PAY-01, PAY-02, PAY-03: Payment registration test scaffold.

RED phase: All 10 tests are skipped. They define the contract the service layer
must satisfy — implementation comes in Plan 02. Test names, fixtures, and import
structure are final; Plan 02 makes each test green without renaming anything.

Requirements covered:
  PAY-01 — Register payment (full, partial, idempotency, client mismatch, over-balance)
  PAY-02 — Advance payments and apply-to-invoice flow
  PAY-03 — Outstanding balance reflects payments immediately; void restores balance
"""
import pytest
from decimal import Decimal
from datetime import UTC, datetime
from uuid import uuid4

from app.modules.billing.models import BillingDocument, BillingItem, ClientPayment, PaymentAllocation
from app.modules.clients.models import Client
from app.modules.contracts.models import Contract


# ---------------------------------------------------------------------------
# Helper factories — same pattern as test_billing_api.py
# ---------------------------------------------------------------------------


async def _make_client(db, tenant_id) -> Client:
    """Create a Client with a unique NUIT for this test run."""
    nuit_digits = f"40{uuid4().int % 10**7:07d}"
    client = Client(
        tenant_id=tenant_id,
        trading_name=f"Test Client {uuid4().hex[:6]}",
        nuit=nuit_digits,
        payment_terms_days=30,
        credit_limit=Decimal("100000.00"),
        is_active=True,
    )
    db.add(client)
    await db.flush()
    return client


async def _make_billing_document(
    db,
    tenant_id,
    client_id,
    total_amount: Decimal = Decimal("5000.00"),
    status: str = "issued",
) -> BillingDocument:
    """Create a BillingDocument for the given client.

    billing_period_start/end and due_date are fixed to 2026-01 for determinism.
    """
    doc = BillingDocument(
        tenant_id=tenant_id,
        client_id=client_id,
        client_name=f"Test Client Doc {uuid4().hex[:6]}",
        total_amount=total_amount,
        status=status,
        billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
        due_date=datetime(2026, 2, 28, tzinfo=UTC),
        currency="MZN",
    )
    db.add(doc)
    await db.flush()
    return doc


async def _make_payment(
    db,
    tenant_id,
    client_id,
    amount: Decimal,
    billing_document_id=None,
    status: str = "confirmed",
) -> ClientPayment:
    """Create a ClientPayment row directly (bypasses service — for setup only)."""
    payment = ClientPayment(
        tenant_id=tenant_id,
        client_id=client_id,
        billing_document_id=billing_document_id,
        amount=amount,
        currency="MZN",
        value_date=datetime.now(UTC),
        payment_method="bank_transfer",
        status=status,
    )
    db.add(payment)
    await db.flush()
    return payment


# ---------------------------------------------------------------------------
# PAY-01: Register a payment
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="PAY-01 Phase 6 Plan 02: register_payment() service not yet implemented")
@pytest.mark.asyncio
async def test_register_full_payment(db, tenant_id):
    """PAY-01: Registering a payment equal to the invoice total marks the invoice as 'paid'.

    Steps once implemented:
      1. Create client + issued billing_document (total_amount=5000.00)
      2. Call register_payment(db, tenant_id, user_id, payload) with amount=5000.00
      3. Assert returned dict has status="confirmed"
      4. Assert a PaymentAllocation row exists linking payment → billing_document
      5. Assert billing_document.status == "paid" and paid_at is not None
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("5000.00"))

    # Placeholder — service does not exist yet
    assert False, "PAY-01: register_payment() not implemented"


@pytest.mark.skip(reason="PAY-01 Phase 6 Plan 02: register_payment() service not yet implemented")
@pytest.mark.asyncio
async def test_register_partial_payment(db, tenant_id):
    """PAY-01: A partial payment reduces outstanding balance but invoice stays 'issued'.

    Steps once implemented:
      1. Create client + issued billing_document (total_amount=5000.00)
      2. Call register_payment(..., amount=2000.00)
      3. Assert billing_document.status == "issued" (not paid)
      4. Assert _get_outstanding_balance(db, client.id, tenant_id) == 3000.00
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("5000.00"))

    assert False, "PAY-01: register_payment() not implemented"


@pytest.mark.skip(reason="PAY-01 Phase 6 Plan 02: register_payment() idempotency not yet implemented")
@pytest.mark.asyncio
async def test_payment_idempotency(db, tenant_id):
    """PAY-01: Sending the same Idempotency-Key twice returns cached response; only one payment row.

    Steps once implemented:
      1. Create client + issued billing_document
      2. Call register_payment(...) with idempotency_key="idem-key-1"
      3. Call register_payment(...) again with the same idempotency_key
      4. Assert both calls return the same payment id
      5. Assert only one ClientPayment row exists in the DB for this client
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("5000.00"))

    assert False, "PAY-01: idempotent register_payment() not implemented"


@pytest.mark.skip(reason="PAY-01 Phase 6 Plan 02: register_payment() client mismatch guard not yet implemented")
@pytest.mark.asyncio
async def test_payment_client_mismatch(db, tenant_id):
    """PAY-01: Payment for client A applied to billing_document belonging to client B → HTTP 409.

    Steps once implemented:
      1. Create client_a and client_b under same tenant
      2. Create billing_document belonging to client_b
      3. Call register_payment(..., client_id=client_a.id, billing_document_id=doc_b.id)
      4. Assert ApiError with code "payment_client_mismatch" and status_code=409
    """
    client_a = await _make_client(db, tenant_id)
    client_b = await _make_client(db, tenant_id)
    doc_b = await _make_billing_document(db, tenant_id, client_b.id)

    assert False, "PAY-01: payment_client_mismatch guard not implemented"


@pytest.mark.skip(reason="PAY-01 Phase 6 Plan 02: register_payment() over-allocation guard not yet implemented")
@pytest.mark.asyncio
async def test_payment_exceeds_balance(db, tenant_id):
    """PAY-01: Payment amount > remaining invoice balance → HTTP 409.

    Steps once implemented:
      1. Create client + issued billing_document (total_amount=1000.00)
      2. Call register_payment(..., amount=1500.00)
      3. Assert ApiError with code "payment_exceeds_invoice_balance" and status_code=409
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("1000.00"))

    assert False, "PAY-01: over-allocation guard not implemented"


# ---------------------------------------------------------------------------
# PAY-02: Advance payments and apply-to-invoice flow
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="PAY-02 Phase 6 Plan 02: register_payment() advance flow not yet implemented")
@pytest.mark.asyncio
async def test_advance_payment(db, tenant_id):
    """PAY-02: Registering payment with billing_document_id=None creates advance with no allocations.

    Steps once implemented:
      1. Create client (no billing document)
      2. Call register_payment(..., billing_document_id=None, amount=3000.00)
      3. Assert returned payment has status="confirmed" and billing_document_id is None
      4. Assert zero PaymentAllocation rows exist for this payment
    """
    client = await _make_client(db, tenant_id)

    assert False, "PAY-02: advance payment not implemented"


@pytest.mark.skip(reason="PAY-02 Phase 6 Plan 02: apply_advance_to_invoice() not yet implemented")
@pytest.mark.asyncio
async def test_apply_advance(db, tenant_id):
    """PAY-02: Applying an advance to an invoice creates an allocation and reduces outstanding balance.

    Steps once implemented:
      1. Create client + advance payment (amount=3000.00, billing_document_id=None)
      2. Create issued billing_document (total_amount=2000.00)
      3. Call apply_advance_to_invoice(db, tenant_id, payment.id, billing_document_id=doc.id, amount_applied=2000.00)
      4. Assert a PaymentAllocation row is created
      5. Assert billing_document.status == "paid" (fully covered)
      6. Assert _get_outstanding_balance returns 0 for this client
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("2000.00"))

    assert False, "PAY-02: apply_advance_to_invoice() not implemented"


@pytest.mark.skip(reason="PAY-02 Phase 6 Plan 02: apply_advance_to_invoice() over-apply guard not yet implemented")
@pytest.mark.asyncio
async def test_advance_over_applied(db, tenant_id):
    """PAY-02: Applying advance with amount_applied > unallocated remainder → HTTP 409.

    Steps once implemented:
      1. Create client + advance payment (amount=500.00)
      2. Create issued billing_document (total_amount=2000.00)
      3. Call apply_advance_to_invoice(..., amount_applied=750.00)  # > payment.amount
      4. Assert ApiError with status_code=409
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("2000.00"))

    assert False, "PAY-02: advance over-apply guard not implemented"


# ---------------------------------------------------------------------------
# PAY-03: Outstanding balance reflects payments; void restores balance
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="PAY-03 Phase 6 Plan 02: _get_outstanding_balance() allocation subtraction not yet implemented")
@pytest.mark.asyncio
async def test_balance_updated_after_payment(db, tenant_id):
    """PAY-03: After registering a payment, _get_outstanding_balance returns reduced balance.

    Steps once implemented:
      1. Create client + issued billing_document (total_amount=5000.00)
      2. Record outstanding_balance_before = _get_outstanding_balance(db, client.id, tenant_id)
      3. Call register_payment(..., amount=2000.00)
      4. Record outstanding_balance_after = _get_outstanding_balance(db, client.id, tenant_id)
      5. Assert outstanding_balance_after == outstanding_balance_before - Decimal("2000.00")
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("5000.00"))

    assert False, "PAY-03: _get_outstanding_balance allocation subtraction not implemented"


@pytest.mark.skip(reason="PAY-03 Phase 6 Plan 02: void_payment() and balance restoration not yet implemented")
@pytest.mark.asyncio
async def test_void_restores_balance(db, tenant_id):
    """PAY-03: Voiding a payment restores the invoice balance and reverts status to 'issued'.

    Steps once implemented:
      1. Create client + issued billing_document (total_amount=5000.00)
      2. Call register_payment(..., amount=5000.00) — invoice transitions to "paid"
      3. Assert billing_document.status == "paid"
      4. Call void_payment(db, tenant_id, user_id, payment.id, void_reason="Test void")
      5. Assert payment.status == "voided"
      6. Assert billing_document.status == "issued" (reverted — no longer fully covered)
      7. Assert _get_outstanding_balance == 5000.00 (fully restored)
    """
    client = await _make_client(db, tenant_id)
    doc = await _make_billing_document(db, tenant_id, client.id, total_amount=Decimal("5000.00"))

    assert False, "PAY-03: void_payment() balance restoration not implemented"
