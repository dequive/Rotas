---
phase: 06-payment-registration
plan: 02
subsystem: billing / clients
status: complete
completed_at: "2026-06-19"
duration_minutes: 45
tags: [payments, service-layer, tdd-green, allocation, void, balance]

dependency_graph:
  requires:
    - "06-01"  # RED phase test stubs
    - "05"     # client_payments + payment_allocations tables + RLS (migration a7b8c9d0e1f2)
  provides:
    - "register_payment() — billing/service.py"
    - "void_payment() — billing/service.py"
    - "apply_advance_to_invoice() — billing/service.py"
    - "_get_outstanding_balance() updated — clients/service.py"
    - "get_client_statement() — clients/service.py"
    - "ClientPaymentCreate, VoidPaymentRequest, ApplyAdvanceRequest schemas"
  affects:
    - "06-03"  # router endpoints (depends on these service functions)
    - "07"     # AR dashboard (uses get_client_statement + _get_outstanding_balance)

tech_stack:
  added: []
  patterns:
    - "flush → audit_log → commit → refresh (existing billing service pattern)"
    - "Decimal.quantize(Decimal('0.01')) for all monetary arithmetic"
    - "inline import to break circular dependency (billing.models in clients.service)"
    - "transition_billing_document() for paid/issued/overdue transitions — never direct status writes"
    - "void bypasses SM terminal guard (paid→issued reversal is exceptional financial path)"

key_files:
  created: []
  modified:
    - backend/app/modules/billing/schemas.py
    - backend/app/modules/billing/service.py
    - backend/app/modules/clients/service.py
    - backend/tests/test_payments.py

decisions:
  - "serialize_payment returns UUIDs as str() to match JSON serialization convention used by other serializers"
  - "void_payment bypasses transition_billing_document SM guard for paid→issued reversal — voiding is an exceptional path that must undo a terminal state; documented in code comment"
  - "created_by FK requires real users.id in tests — added _make_user() helper to test file"
  - "_get_outstanding_balance now includes 'overdue' status in addition to 'issued' — both represent outstanding receivables"
  - "get_client_statement placed in clients/service.py (keyed by client_id, returns client context) — consistent with plan recommendation; Phase 7 can extend without moving"

metrics:
  tasks_completed: 3
  tasks_total: 3
  tests_added: 10
  tests_passing: 10
  files_modified: 4
---

# Phase 06 Plan 02: Payment Service Layer Summary

Implements the complete payment service layer for ROTAS Phase 6. Three Pydantic schemas added, five service functions implemented, `_get_outstanding_balance` updated, all 10 RED-phase test stubs converted to passing GREEN tests.

## What Was Built

**Schemas added to `billing/schemas.py`:**
- `ClientPaymentCreate` — amount > 0, payment_method enum (bank_transfer|cheque|cash), billing_document_id nullable for advances
- `VoidPaymentRequest` — void_reason min 5 / max 500 chars
- `ApplyAdvanceRequest` — billing_document_id UUID + amount_applied > 0

**Service functions added to `billing/service.py`:**
- `_sum_confirmed_allocations(db, tenant_id, billing_document_id)` — private helper summing confirmed allocations
- `serialize_payment(payment, allocations)` — returns full payment dict with allocations list
- `register_payment(db, tenant_id, user_id, payload)` — full flow: client verify → doc verify → cross-client guard → over-allocation guard → create payment → create allocation → transition to "paid" if fully covered → audit log
- `void_payment(db, *, payment_id, tenant_id, user_id, void_reason)` — sets voided, reverses paid→issued/overdue transition if allocation sum drops below total_amount
- `apply_advance_to_invoice(db, *, payment_id, tenant_id, user_id, billing_document_id, amount_applied)` — verifies advance, guards both payment over-application and invoice over-allocation, creates allocation, transitions if fully covered

**Updated `_get_outstanding_balance` in `clients/service.py`:**
- Now subtracts confirmed `PaymentAllocation.amount_applied` from gross issued+overdue total
- Includes both "issued" and "overdue" documents (previously only "issued")

**Added `get_client_statement` to `clients/service.py`:**
- Returns `{client, documents, payments, summary}` computed synchronously from DB
- Per-document `amount_paid` and `outstanding_balance` from allocations
- `summary.advance_balance` = sum of unallocated confirmed advance payments

## Test Results

```
tests/test_payments.py::test_register_full_payment       PASSED
tests/test_payments.py::test_register_partial_payment    PASSED
tests/test_payments.py::test_payment_idempotency         PASSED
tests/test_payments.py::test_payment_client_mismatch     PASSED
tests/test_payments.py::test_payment_exceeds_balance     PASSED
tests/test_payments.py::test_advance_payment             PASSED
tests/test_payments.py::test_apply_advance               PASSED
tests/test_payments.py::test_advance_over_applied        PASSED
tests/test_payments.py::test_balance_updated_after_payment PASSED
tests/test_payments.py::test_void_restores_balance       PASSED

10 passed in 3.75s
```

Full suite: 293 passed, 4 failed (all pre-existing — composite index tests + rate limiter test unrelated to this plan).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FK violation: created_by references non-existent user**
- **Found during:** Task 2 first test run
- **Issue:** `client_payments.created_by` has a FK to `users.id`. Tests used `uuid4()` for `user_id` which doesn't exist in the DB.
- **Fix:** Added `_make_user(db, tenant_id)` helper to `test_payments.py` that creates a real `User` row. All tests now call `user = await _make_user(db, tenant_id)` and pass `user.id`.
- **Files modified:** `backend/tests/test_payments.py`
- **Commit:** 6c49b5e

**2. [Rule 1 - Bug] UUID vs str type mismatch in serialize_payment**
- **Found during:** Task 2 test run (advance/void tests)
- **Issue:** Tests called `UUID(result["id"])` expecting a string, but `serialize_payment` was returning native UUIDs. After linter intervention, `serialize_payment` was confirmed to return `str(payment.id)`.
- **Fix:** Updated tests to use `result["id"]` directly (not wrapped in `UUID(...)`) for `apply_advance_to_invoice` and `void_payment`. Updated `str(rows[0].id) == result1["id"]` for the idempotency assertion.
- **Files modified:** `backend/tests/test_payments.py`
- **Commit:** 6c49b5e

**3. [Rule 1 - Bug] void_payment bypasses SM terminal guard**
- **Found during:** Task 2 implementation analysis
- **Issue:** `transition_billing_document` treats "paid" as a terminal state with no valid outbound transitions. Voiding a full payment must revert "paid" → "issued"/"overdue", but the SM would raise 409.
- **Fix:** `void_payment` sets `billing_doc.status` directly (bypassing the SM guard) with explicit audit log for the reversal. Comment in code documents this as an intentional exceptional path.
- **Files modified:** `backend/app/modules/billing/service.py`
- **Commit:** 6c49b5e

## Known Stubs

None — all service functions are fully implemented. No placeholder data flows to UI at this stage (no router endpoints yet — those come in Plan 03).

## Self-Check: PASSED

Files exist:
- `backend/app/modules/billing/schemas.py` — ClientPaymentCreate present
- `backend/app/modules/billing/service.py` — register_payment, void_payment, apply_advance_to_invoice present
- `backend/app/modules/clients/service.py` — _get_outstanding_balance updated, get_client_statement present
- `backend/tests/test_payments.py` — 10 tests, all passing

Commits exist:
- 25ca794 — feat(06-02): schemas
- 6c49b5e — feat(06-02): service functions + test implementations
