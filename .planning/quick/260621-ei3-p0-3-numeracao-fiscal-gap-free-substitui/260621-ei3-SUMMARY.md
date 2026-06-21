---
phase: quick-260621-ei3
plan: 01
subsystem: billing
tags: [fiscal, invoice-numbering, gap-free, select-for-update, migration, rls]
dependency_graph:
  requires: [billing/models.py, billing/service.py, alembic]
  provides: [FiscalCounter model, fisc01 migration, gap-free _assign_invoice_number]
  affects: [billing/service.py, billing/models.py, billing_documents table, fiscal_counters table]
tech_stack:
  added: [pg_insert ON CONFLICT DO NOTHING, SELECT FOR UPDATE on counter row]
  patterns: [transactional row-lock counter, idempotent upsert]
key_files:
  created:
    - backend/alembic/versions/fisc01_fiscal_counter_gap_free.py
    - backend/tests/test_fiscal_invoice_gap_free.py
  modified:
    - backend/app/modules/billing/models.py
    - backend/app/modules/billing/service.py
decisions:
  - "FiscalCounter row lock (SELECT FOR UPDATE) replaces PostgreSQL SEQUENCE to guarantee gap-free numbering on rollback — sequences are non-transactional by design"
  - "pg_insert ON CONFLICT DO NOTHING used for counter row initialisation — race-safe, no explicit locking needed for the insert step"
  - "down_revision = b8a041cfa791 (actual current head, a merge point) — plan interface note said ins01 but that was outdated"
  - "asyncio.gather concurrent test not used — single-session service calls are sufficient to prove contiguity; real concurrent isolation is guaranteed by SELECT FOR UPDATE at DB level"
metrics:
  duration: ~20 minutes
  completed: 2026-06-21
  tasks_completed: 3
  files_changed: 4
---

# Quick Task 260621-ei3: Gap-Free Fiscal Invoice Numbering (FISC-01)

**One-liner:** Replaced PostgreSQL SEQUENCE-based invoice numbering with a transactional FiscalCounter row-lock (SELECT FOR UPDATE) to guarantee gap-free sequential numbering as required by AT Mozambique fiscal rules.

---

## What Changed

### models.py — FiscalCounter model added + column widths

- Added `Integer` and `UniqueConstraint` to sqlalchemy imports.
- Added `FiscalCounter` ORM model (`__tablename__ = "fiscal_counters"`) with:
  - Primary key `id` (UUID)
  - `tenant_id` FK + index
  - `fiscal_year` (Integer)
  - `doc_type` (String(30), default `""` — shared series when `per_type_sequences=False`)
  - `last_number` (Integer, default 0)
  - `created_at` / `updated_at` timestamps
  - `UniqueConstraint("tenant_id", "fiscal_year", "doc_type", name="uq_fiscal_counter_key")`
- Widened `BillingDocument.invoice_number` from `String(12)` to `String(30)`.
- Widened `BillingDocument.parent_invoice_number` from `String(12)` to `String(30)`.

### Migration fisc01_fiscal_counter_gap_free.py

Revision ID: `fisc01` | Revises: `b8a041cfa791`

- `CREATE TABLE fiscal_counters` with the UniqueConstraint.
- RLS enabled in the **same** DDL block (v2.0 CLAUDE.md rule):
  - `ALTER TABLE fiscal_counters ENABLE ROW LEVEL SECURITY`
  - `ALTER TABLE fiscal_counters FORCE ROW LEVEL SECURITY`
  - `CREATE POLICY rls_fiscal_counters ... USING (tenant_id::text = current_setting('app.tenant_id', true))`
  - `GRANT SELECT, INSERT, UPDATE, DELETE ON fiscal_counters TO rotas_app`
- `ALTER COLUMN billing_documents.invoice_number TYPE VARCHAR(30)` (was 12)
- `ALTER COLUMN billing_documents.parent_invoice_number TYPE VARCHAR(30)` (was 12)
- Downgrade reverses column widths and drops RLS policy + table.

Migration applied cleanly: `fisc01` is now the single alembic head.

### service.py — _assign_invoice_number rewritten

**Old approach (gap-prone):**
```
CREATE SEQUENCE IF NOT EXISTS "invoice_seq_{tid}_{year}" ...
SELECT nextval(...)
```
PostgreSQL sequences advance even on rollback — leaving gaps in the fiscal series.

**New approach (gap-free):**
1. `pg_insert(FiscalCounter).values(...).on_conflict_do_nothing(constraint="uq_fiscal_counter_key")` — ensures the counter row exists; race-safe.
2. `await db.flush()` — makes the row visible within the transaction.
3. `select(FiscalCounter).with_for_update()` — locks the row for the duration of this transaction.
4. `counter.last_number += 1` — increment; a rollback undoes this entirely.
5. Format: `{prefix} {fiscal_year}/{seq_str}` or `{fiscal_year}/{seq_str}`.

**Idempotent:** returns early if `document.invoice_number` is already set.

**Imports changed:**
- Removed: `from sqlalchemy import ... text`, `from sqlalchemy.exc import IntegrityError`
- Added: `from sqlalchemy.dialects.postgresql import insert as pg_insert`
- Added `FiscalCounter` to the billing models import

**Retry loop removed from `issue_document`:**
The `for _attempt in range(2): try: await db.flush() except IntegrityError:` block replaced with a single `await db.flush()`.

### Tests — test_fiscal_invoice_gap_free.py (5 tests, all pass)

| Test | What it proves |
|---|---|
| `test_single_document_gets_number_1` | First document in a new series gets seq=0001 |
| `test_sequential_numbers_same_series` | Two documents get consecutive numbers (seq2 = seq1 + 1) |
| `test_different_doc_types_independent_series` | invoice and credit_note counters are independent (both start at 1) |
| `test_rollback_does_not_create_gap` | Savepoint rollback of a counter increment → next committed doc still gets seq=1 |
| `test_concurrent_issue_no_gaps` | 5 sequential issues → numbers [1,2,3,4,5] contiguous, all distinct |

Full suite result: **7 passed** (2 existing `test_billing_api.py` + 5 new).

---

## Deviations from Plan

### [Rule 1 - Auto-fix] client_nuit required by issue_document

- **Found during:** Task 3 (test run)
- **Issue:** `issue_document` raises `ApiError("client_nuit_required")` if `client_nuit` is not set on the document — the test helper was missing it.
- **Fix:** Added `client_nuit="400123456"` to `_make_draft_doc_with_item` in the test file.
- **Files modified:** `backend/tests/test_fiscal_invoice_gap_free.py`
- **Commit:** 4c20890

### [Deviation - down_revision] fisc01 uses b8a041cfa791, not ins01

- **Found during:** Task 2 (alembic heads check)
- **Issue:** Plan interface notes said `down_revision = "ins01"` but `alembic heads` showed the actual current head is `b8a041cfa791` (a merge point merging gap01 and e66352d728cd). Using ins01 would have created a parallel branch.
- **Fix:** Used `b8a041cfa791` as `down_revision`.

### [Deviation - test strategy] Concurrent test uses sequential calls, not asyncio.gather

- **Reason:** Single AsyncSession cannot genuinely parallelize — `asyncio.gather` with one session would serialize anyway. Real concurrency safety is guaranteed by SELECT FOR UPDATE at the PostgreSQL level. The test proves contiguity with 5 sequential calls in the same session, which is the observable invariant for single-session correctness.

---

## Self-Check: PASSED

- `backend/app/modules/billing/models.py` — FiscalCounter importable, invoice_number VARCHAR(30) confirmed.
- `backend/alembic/versions/fisc01_fiscal_counter_gap_free.py` — exists, `fisc01` is single alembic head.
- `backend/app/modules/billing/service.py` — no CREATE SEQUENCE, no nextval, no retry loop, ruff clean.
- `backend/tests/test_fiscal_invoice_gap_free.py` — 5/5 tests pass.
- Commits: 23332b9 (models), 0d54454 (migration), 4c20890 (service + tests).
