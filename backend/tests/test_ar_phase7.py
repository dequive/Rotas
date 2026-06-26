"""Phase 7 AR correctness tests — bucket assignment, outstanding calculation, PDF generation.

These tests verify the AR service logic introduced in Phase 7:
  - Aging bucket assignment via get_ar_summary (as_of parameter)
  - Draft exclusion from AR summary
  - Cross-tenant isolation
  - Client statement outstanding calculation (total_invoiced, total_paid, balance)
  - Statement PDF generation (depends on 07-01 completing generate_client_statement_pdf)

Dependency note: test_client_statement_pdf_returns_bytes depends on 07-01 adding
generate_client_statement_pdf to billing/service.py. If 07-01 is not yet complete,
that test will be skipped automatically via importorskip guard.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import import_all_models
from app.modules.billing.models import BillingDocument, ClientPayment, PaymentAllocation
from app.modules.billing.service import get_ar_summary, get_client_statement
from app.modules.clients.models import Client
from app.modules.tenants.models import Tenant
from app.modules.users.models import User

import_all_models()


# ── Local fixtures (tenant and owner are not in conftest — defined here) ──────


@pytest.fixture
async def tenant(db: AsyncSession) -> Tenant:
    """Create an isolated test tenant for each AR test."""
    suffix = uuid4().hex[:8]
    t = Tenant(name=f"AR Test Tenant {suffix}", slug=f"ar-test-{suffix}")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@pytest.fixture
async def owner(db: AsyncSession, tenant: Tenant) -> User:
    """Create an owner user for tests that need created_by."""
    suffix = uuid4().hex[:8]
    u = User(
        tenant_id=tenant.id,
        email=f"ar-owner-{suffix}@test.local",
        password_hash="$argon2id$test",
        full_name="AR Test Owner",
        role="owner",
        is_active=True,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_client(
    db: AsyncSession,
    tenant_id,
    name: str = "Test Client",
    nuit: str | None = None,
) -> Client:
    """Create a minimal Client row. nuit is unique per tenant, so we randomise it."""
    nuit_val = nuit or f"{uuid4().int % 900000000 + 100000000}"  # 9-digit number
    c = Client(
        tenant_id=tenant_id,
        trading_name=name,
        nuit=nuit_val,
        is_active=True,
    )
    db.add(c)
    await db.flush()
    return c


def _make_invoice(
    tenant_id,
    client_id,
    total_amount: Decimal,
    due_days_ago: int,
    issued_days_ago: int = 60,
    status: str = "issued",
    document_type: str = "invoice",
) -> BillingDocument:
    """Build a BillingDocument ORM object (not yet added to session)."""
    now = datetime.now(UTC)
    return BillingDocument(
        tenant_id=tenant_id,
        client_id=client_id,
        client_name="Test Client",
        contract_reference=f"REF-{uuid4().hex[:6]}",
        billing_period_start=now - timedelta(days=90),
        billing_period_end=now - timedelta(days=60),
        currency="MZN",
        subtotal=total_amount,
        tax_amount=Decimal("0.00"),
        total_amount=total_amount,
        status=status,
        document_type=document_type,
        due_date=now - timedelta(days=due_days_ago),
        issued_at=now - timedelta(days=issued_days_ago),
        issuer_name="Test Issuer",
        iva_rate=Decimal("0.16"),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ar_summary_buckets_correct(db: AsyncSession, tenant: Tenant):
    """Invoice with due_date 45 days ago must appear in 31_60 bucket with correct amount."""
    client = await _make_client(db, tenant.id)
    invoice = _make_invoice(tenant.id, client.id, Decimal("1000.00"), due_days_ago=45)
    db.add(invoice)
    await db.commit()

    result = await get_ar_summary(db, tenant.id)

    assert result["31_60"] == Decimal("1000.00"), f"Expected 1000.00 in 31_60 bucket, got: {result}"
    assert result["current"] == Decimal("0.00"), f"current must be 0, got {result['current']}"
    assert result["1_30"] == Decimal("0.00"), f"1_30 must be 0, got {result['1_30']}"
    assert result["61_90"] == Decimal("0.00"), f"61_90 must be 0, got {result['61_90']}"
    assert result["over_90"] == Decimal("0.00"), f"over_90 must be 0, got {result['over_90']}"
    assert result["total_ar"] == Decimal("1000.00"), (
        f"total_ar must be 1000.00, got {result['total_ar']}"
    )
    assert "as_of" in result, "Response must include as_of field"


@pytest.mark.asyncio
async def test_ar_summary_as_of_param(db: AsyncSession, tenant: Tenant):
    """Invoice issued today must be excluded when as_of=yesterday, included when as_of=today."""
    client = await _make_client(db, tenant.id)
    now = datetime.now(UTC)

    # Invoice issued today, not yet overdue (due in 30 days) — falls in 'current' when visible
    invoice = BillingDocument(
        tenant_id=tenant.id,
        client_id=client.id,
        client_name="Test Client",
        contract_reference=f"REF-{uuid4().hex[:6]}",
        billing_period_start=now - timedelta(days=30),
        billing_period_end=now,
        currency="MZN",
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("500.00"),
        status="issued",
        document_type="invoice",
        due_date=now + timedelta(days=30),  # not yet due — 'current' bucket
        issued_at=now,  # issued today
        issuer_name="Test Issuer",
        iva_rate=Decimal("0.16"),
    )
    db.add(invoice)
    await db.commit()

    # as_of=yesterday — invoice issued today should be excluded
    yesterday = (now - timedelta(days=1)).date()
    result_yesterday = await get_ar_summary(db, tenant.id, as_of=yesterday)

    assert result_yesterday["total_ar"] == Decimal("0.00"), (
        f"Invoice issued today must be excluded when as_of=yesterday, got {result_yesterday}"
    )

    # as_of=today — invoice should be visible (in 'current' bucket, not overdue)
    today = now.date()
    result_today = await get_ar_summary(db, tenant.id, as_of=today)

    assert result_today["total_ar"] == Decimal("500.00"), (
        f"Invoice issued today must appear when as_of=today, got {result_today}"
    )


@pytest.mark.asyncio
async def test_ar_summary_excludes_drafts(db: AsyncSession, tenant: Tenant):
    """Draft documents must never appear in AR summary regardless of due_date."""
    client = await _make_client(db, tenant.id)
    draft_invoice = _make_invoice(
        tenant.id, client.id, Decimal("2000.00"), due_days_ago=10, status="draft"
    )
    db.add(draft_invoice)
    await db.commit()

    result = await get_ar_summary(db, tenant.id)

    assert result["total_ar"] == Decimal("0.00"), (
        f"Draft invoice must not appear in AR summary, got total_ar={result['total_ar']}"
    )
    assert result["current"] == Decimal("0.00")
    assert result["1_30"] == Decimal("0.00")
    assert result["31_60"] == Decimal("0.00")
    assert result["61_90"] == Decimal("0.00")
    assert result["over_90"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_client_statement_outstanding_correct(db: AsyncSession, tenant: Tenant, owner: User):
    """Invoice 1000 MZN with 400 MZN confirmed payment allocated → balance == 600.00."""
    client = await _make_client(db, tenant.id)
    invoice = _make_invoice(tenant.id, client.id, Decimal("1000.00"), due_days_ago=15)
    db.add(invoice)
    await db.flush()

    payment = ClientPayment(
        tenant_id=tenant.id,
        client_id=client.id,
        amount=Decimal("400.00"),
        currency="MZN",
        value_date=datetime.now(UTC),
        payment_method="transfer",
        status="confirmed",
        created_by=owner.id,
    )
    db.add(payment)
    await db.flush()

    allocation = PaymentAllocation(
        tenant_id=tenant.id,
        payment_id=payment.id,
        billing_document_id=invoice.id,
        amount_applied=Decimal("400.00"),
    )
    db.add(allocation)
    await db.commit()

    result = await get_client_statement(db, tenant.id, client.id)

    assert result["total_invoiced"] == Decimal("1000.00"), (
        f"total_invoiced must be 1000.00, got {result['total_invoiced']}"
    )
    assert result["total_paid"] == Decimal("400.00"), (
        f"total_paid must be 400.00, got {result['total_paid']}"
    )
    assert result["balance"] == Decimal("600.00"), (
        f"balance (total_invoiced - total_paid) must be 600.00, got {result['balance']}"
    )

    # Verify the document appears in the documents list
    docs = result["documents"]
    assert len(docs) >= 1, "Statement must include at least one document"
    doc_ids = [str(d.get("id")) for d in docs]
    assert str(invoice.id) in doc_ids, (
        f"Invoice {invoice.id} not found in statement documents: {doc_ids}"
    )


@pytest.mark.asyncio
async def test_client_statement_pdf_returns_bytes(db: AsyncSession, tenant: Tenant, owner: User):
    """generate_client_statement_pdf returns PDF bytes with magic header and len > 1000.

    This test depends on 07-01 adding generate_client_statement_pdf to billing/service.py.
    If 07-01 is not complete, the test is skipped automatically.
    """
    try:
        from app.modules.billing.service import generate_client_statement_pdf
    except ImportError:
        pytest.skip("generate_client_statement_pdf not yet available — requires 07-01 to complete")

    client = await _make_client(db, tenant.id, "Cliente Moçambicano Ção")
    invoice = _make_invoice(tenant.id, client.id, Decimal("750.00"), due_days_ago=20)
    db.add(invoice)
    await db.commit()

    pdf_bytes = await generate_client_statement_pdf(db, tenant.id, client.id)

    assert isinstance(pdf_bytes, bytes), (
        f"generate_client_statement_pdf must return bytes, got {type(pdf_bytes)}"
    )
    assert len(pdf_bytes) > 1000, f"PDF too small — expected > 1000 bytes, got {len(pdf_bytes)}"
    assert pdf_bytes[:4] == b"%PDF", (
        f"Response is not a valid PDF (missing %PDF magic bytes); starts with {pdf_bytes[:8]!r}"
    )


@pytest.mark.asyncio
async def test_ar_cross_tenant(db: AsyncSession, tenant: Tenant):
    """Tenant A invoices must not appear in Tenant B AR summary — strict isolation."""
    # Create tenant B
    suffix = uuid4().hex[:8]
    tenant_b = Tenant(name=f"Tenant B {suffix}", slug=f"tenant-b-{suffix}")
    db.add(tenant_b)
    await db.flush()

    # Create invoice for tenant A
    client_a = await _make_client(db, tenant.id, "Client A")
    invoice_a = _make_invoice(tenant.id, client_a.id, Decimal("3000.00"), due_days_ago=50)
    db.add(invoice_a)
    await db.commit()

    # Query from tenant B — should see nothing
    result_b = await get_ar_summary(db, tenant_b.id)

    assert result_b["total_ar"] == Decimal("0.00"), (
        f"Tenant B must not see Tenant A invoices; got total_ar={result_b['total_ar']}"
    )
    assert result_b["31_60"] == Decimal("0.00"), (
        f"Tenant B 31_60 bucket must be 0; got {result_b['31_60']}"
    )
