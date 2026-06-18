"""Phase 15.1 — Fiscal Documents integration tests.

Requirements: FDOC-01, FDOC-02, FDOC-03, FDOC-04, FDOC-05
All tests require a live PostgreSQL DB.
"""
import pytest


# FDOC-01 ─────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="FDOC-01: billing_documents DDL not yet applied")
async def test_billing_document_has_document_type_column(db, tenant_id):
    """BillingDocument ORM model must expose document_type, parent_document_id,
    due_date, client_nuit fields after DDL migration."""
    ...

@pytest.mark.skip(reason="FDOC-01: billing_documents DDL not yet applied")
async def test_billing_document_type_defaults_to_invoice(db, tenant_id):
    """Existing billing documents default to document_type='invoice'."""
    ...


# FDOC-02 ─────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="FDOC-02: create_debit_note not yet implemented")
async def test_create_debit_note_returns_invoice_number(db, tenant_id):
    """POST /billing/documents/{id}/debit-note returns 201 with invoice_number
    and parent_invoice_number populated."""
    ...

@pytest.mark.skip(reason="FDOC-02: create_debit_note not yet implemented")
async def test_debit_note_parent_must_be_issued(db, tenant_id):
    """create_debit_note raises 409 when parent document is in draft status."""
    ...

@pytest.mark.skip(reason="FDOC-02: create_debit_note not yet implemented")
async def test_debit_note_cross_tenant_isolation(db, tenant_id):
    """Cannot create debit note for a document belonging to another tenant."""
    ...


# FDOC-03 ─────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="FDOC-03: create_credit_note not yet implemented")
async def test_create_credit_note_parent_unaffected(db, tenant_id):
    """POST /billing/documents/{id}/credit-note creates credit_note document;
    parent document status remains unchanged."""
    ...

@pytest.mark.skip(reason="FDOC-03: create_credit_note not yet implemented")
async def test_credit_note_gets_sequential_invoice_number(db, tenant_id):
    """credit_note document receives invoice_number from the same per-tenant
    per-year SEQUENCE as regular invoices."""
    ...


# FDOC-04 ─────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="FDOC-04: create_invoice_receipt not yet implemented")
async def test_invoice_receipt_transitions_parent_to_paid(db, tenant_id):
    """POST /billing/documents/{id}/invoice-receipt sets parent status=paid
    and creates invoice_receipt document."""
    ...

@pytest.mark.skip(reason="FDOC-04: create_receipt not yet implemented")
async def test_standalone_receipt_does_not_change_parent_status(db, tenant_id):
    """POST /billing/documents/{id}/receipt creates receipt document without
    changing parent status (partial payment scenario)."""
    ...


# FDOC-05 ─────────────────────────────────────────────────────────────────────

@pytest.mark.skip(reason="FDOC-05: AR endpoint not yet implemented")
async def test_ar_endpoint_filters_by_aging_bucket(async_client, auth_headers):
    """GET /billing/ar?aging_bucket=31_60 returns only documents with
    days_overdue between 31 and 60."""
    ...

@pytest.mark.skip(reason="FDOC-05: days_overdue computation not yet implemented")
async def test_serialize_billing_document_includes_ar_fields(db, tenant_id):
    """serialize_billing_document returns days_overdue (int >= 0) and
    aging_bucket (one of: current, 1_30, 31_60, 61_90, over_90)."""
    ...
