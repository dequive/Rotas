---
phase: quick-260620-cme
plan: 01
type: summary
subsystem: billing
tags: [billing, fiscal, IVA, PDF, XLSX, AR, payments, alembic, production-hardening]
dependency_graph:
  requires: []
  provides: [billing-production-hardened]
  affects: [billing, contracts, exporters, router]
tech_stack:
  added: []
  patterns:
    - DEFAULT_IVA_RATE constant for IVA fiscal correctness
    - Issuer identity snapshotted from Tenant at document creation (no JOIN on export)
    - parent_invoice_number denormalized on child documents for JOIN-free PDF/XLSX
    - Bulk IN query for waivers in list_billable_trips (eliminates N+1)
    - list_documents returns {items, total} pagination envelope
key_files:
  created:
    - backend/scripts/billing_iva_backfill.sql
    - backend/alembic/versions/b1c2d3e4f5a6_billing_issuer_parent_invoice_payment_terms.py
  modified:
    - backend/app/modules/billing/service.py
    - backend/app/modules/billing/schemas.py
    - backend/app/modules/billing/exporters.py
    - backend/app/modules/billing/router.py
    - backend/app/modules/billing/models.py
    - backend/app/modules/contracts/models.py
    - backend/tests/test_billing_export.py
    - backend/tests/test_cargo_billing_flow.py
decisions:
  - "Client model uses trading_name not name — used trading_name in get_client_statement response"
  - "isinstance() guards in XLSX exporter prevent MagicMock test objects from leaking into Excel cells when client_nuit/due_date are not set"
  - "list_documents return shape changed from list to {items, total} — updated 2 tests"
  - "Test row numbers updated: header row 8→7, data row 9→8 after Estado row removal (E3)"
metrics:
  duration: ~60 minutes
  completed_date: "2026-06-20"
  tasks_completed: 4
  files_modified: 10
---

# Quick Task 260620-CME: Billing Module Production Hardening — Summary

**One-liner:** Production-hardened billing module with IVA fiscal constant (16%), issuer identity from Tenant, N+1 waiver fix, state machine issued→cancelled block, 4 new endpoints (AR summary, client statement, payments list, list_documents filters), and professional PDF/XLSX fixes (invoice numbers, type labels, PROFORMA for drafts).

---

## What Was Done

### Wave A — IVA constant + model columns + Alembic migration (commit `6ceaf47`)

- **`billing_iva_backfill.sql`** — dry-run SQL script with audit COUNT, UPDATE blocks for pre-2023 (0.1700) and 2023+ (0.1600) documents, ROLLBACK safety comment.
- **`DEFAULT_IVA_RATE = Decimal("0.1600")`** added in `service.py` as single source-of-truth. All 3 literal occurrences of `Decimal("0.1700")` in `service.py` replaced; 2 occurrences in `schemas.py` replaced with `Decimal("0.1600")`.
- **`exporters.py`** — both PDF and XLSX `iva_pct` fallback `else 17` replaced with `raise ValueError("iva_rate is NULL...")`.
- **`BillingDocument` model** — added `issuer_name` (String 200), `issuer_nuit` (String 20), `parent_invoice_number` (String 12).
- **`Contract` model** — added `payment_terms_days` (Integer, server_default=30). Added `Integer` import.
- **Alembic migration `b1c2d3e4f5a6`** — `down_revision = restore_composite_indexes`. Applied cleanly.

### Wave B — Service layer fixes (commit `bfdefcc`)

9 fixes applied to `service.py`:

1. **Issuer from Tenant** — `create_document` fetches `Tenant` and sets `issuer_name`/`issuer_nuit` on the new `BillingDocument`.
2. **parent_invoice_number** — `create_debit_note`, `create_credit_note`, `create_invoice_receipt`, `create_receipt` all copy `parent.invoice_number` and `parent.issuer_name/issuer_nuit` to child document.
3. **due_date** — `issue_document` computes `due_date = issued_at + timedelta(days=contract.payment_terms_days)` (default 30).
4. **State machine** — `_BILLING_VALID_TRANSITIONS["issued"]` changed from `{"paid", "overdue", "cancelled"}` to `{"paid", "overdue"}`.
5. **FISC-01 comment** — comment added in `create_document` confirming invoice_number not assigned on draft.
6. **Audit logs** — `create_invoice_receipt` and `create_receipt` both emit `record_audit_log` before `db.commit()`.
7. **void_payment allocations** — return `serialize_payment(payment, allocations)` instead of `serialize_payment(payment, [])`.
8. **N+1 fix** — `list_billable_trips` replaced per-trip waiver `scalar()` with single bulk `IN` query + `waiver_map` dict.
9. **Invariant check** — `issue_document` raises `ApiError("billing_total_inconsistency", 422)` if `subtotal + tax_amount != total_amount` after FISC-02 recomputation.

### Wave C — Exporter fixes + router download (commit `e6c96c7`)

**exporters.py:**
- **E1** — `doc_number` uses `document.invoice_number` (fallback to UUID prefix).
- **E2** — `_DOC_TYPE_LABELS` dict + `_doc_type_label()` function; draft → "PROFORMA — SEM VALOR FISCAL"; issued → "FATURA", "NOTA DE DÉBITO", etc. `_RotasPDF` accepts `doc_type` param.
- **E3** — "Estado do documento" row removed from both PDF and XLSX metadata blocks.
- **E4** — `client_nuit` rendered in metadata when present (with `isinstance(str)` guard).
- **E5** — `render_billing_export()` signature simplified: derives `issuer_name`/`issuer_nuit` from `document.issuer_name`/`document.issuer_nuit` columns. No caller args needed.
- **E6** — `due_date` rendered in metadata when present (with `isinstance(datetime)` guard).
- **E7** — Filename changed to `fatura_{invoice_number}.pdf/.xlsx`.

**router.py:**
- **R1** — `download_job_file` uses `job.file_id` → `RedirectResponse(/api/v1/files/{id}/download)`. Legacy `file_path` disk fallback preserved for old jobs.

### Wave D — New endpoints + list_documents filters (commit `5bd9e4e`)

**service.py:**
- `list_documents` — added `document_type` and `client_id` filters; now returns `{items: [...], total: int}` instead of bare list.
- `get_ar_summary` — new function: fetches issued/overdue invoices, buckets by `_compute_aging()`, returns `{current, 1_30, 31_60, 61_90, over_90, total_ar, currency}`.
- `get_client_statement` — new function: queries total_invoiced and total_paid via PaymentAllocation JOIN, returns `{client_id, client_name, total_invoiced, total_paid, balance, currency, documents}`.
- `list_payments` — new function: paginated `ClientPayment` list with client_id/status/value_date filters; bulk-fetches allocations in one IN query.

**router.py:**
- `GET /billing/documents` — passes `document_type` and `client_id` query params.
- `GET /billing/ar/summary` — new endpoint.
- `GET /billing/clients/{client_id}/statement` — new endpoint.
- `GET /billing/payments` — new endpoint (separate from `POST /billing/payments`).

---

## Migration Revision ID

`b1c2d3e4f5a6` — `down_revision = restore_composite_indexes`

Columns added:
- `billing_documents.issuer_name` VARCHAR(200) NULL
- `billing_documents.issuer_nuit` VARCHAR(20) NULL
- `billing_documents.parent_invoice_number` VARCHAR(12) NULL
- `contracts.payment_terms_days` INTEGER NOT NULL DEFAULT 30

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] XLSX MagicMock cell corruption in tests**
- **Found during:** Wave D test run
- **Issue:** `if document.client_nuit:` and `if document.due_date:` were truthy for MagicMock objects in test suite, causing `ValueError: Cannot convert MagicMock to Excel`.
- **Fix:** Changed to `isinstance(document.client_nuit, str)` and `isinstance(document.due_date, datetime)` guards in both PDF and XLSX paths.
- **Files modified:** `backend/app/modules/billing/exporters.py`

**2. [Rule 1 - Bug] test_billing_export row number mismatch after E3 removal**
- **Found during:** Wave D test run
- **Issue:** Tests hardcoded row 8 (header) and row 9 (data). After removing the Estado row (E3), header shifted to row 7, data to row 8.
- **Fix:** Updated test assertions to row 7 (header) and row 8 (data).
- **Files modified:** `backend/tests/test_billing_export.py`

**3. [Rule 1 - Bug] test_cargo_billing_flow list_documents shape mismatch**
- **Found during:** Wave D test run
- **Issue:** `assert len(documents) == 1` failed because `list_documents` now returns `{items, total}` not a plain list.
- **Fix:** Updated test to use `documents_body["items"]` and added `assert documents_body["total"] == 1`.
- **Files modified:** `backend/tests/test_cargo_billing_flow.py`

**4. [Deviation] Client.name → Client.trading_name**
- **Found during:** Wave D implementation
- **Issue:** Plan spec referenced `client.name` but the Client model uses `trading_name`.
- **Fix:** Used `client.trading_name` in `get_client_statement` response.

---

## Ruff Results

```
ruff check app/modules/billing/ app/modules/contracts/models.py --select E,F,I,B
All checks passed!
```

## Pytest Results

```
319 passed, 2 skipped, 5 warnings
(2 pre-existing failures in test_rate_limiting.py — unrelated to billing)
```

## Self-Check: PASSED
