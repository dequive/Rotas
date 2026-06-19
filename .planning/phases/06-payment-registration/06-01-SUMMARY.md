---
phase: 06-payment-registration
plan: 01
subsystem: billing/payments
tags: [tdd, red-phase, payments, PAY-01, PAY-02, PAY-03]
dependency_graph:
  requires: []
  provides:
    - backend/tests/test_payments.py (10 named test stubs, RED phase)
  affects:
    - backend/app/modules/billing/service.py (Plan 02 must make tests green)
    - backend/app/modules/clients/service.py (Plan 02 must update _get_outstanding_balance)
tech_stack:
  added: []
  patterns:
    - pytest.mark.skip for RED-phase TDD stubs
    - Helper factory pattern (_make_client, _make_billing_document, _make_payment)
    - Direct ORM insertion in test helpers (same pattern as test_billing_api.py)
key_files:
  created:
    - backend/tests/test_payments.py
  modified:
    - .planning/phases/06-payment-registration/06-01-PLAN.md (status: complete added)
decisions:
  - Tests call service layer directly (not HTTP) — avoids need for auth_headers fixture in RED phase
  - assert False in test body (not just skip) to make intent clear while skip prevents collection failure
  - _make_payment helper bypasses service to allow isolated setup in future green-phase tests
metrics:
  duration: ~10 minutes
  completed: 2026-06-19
  tasks: 1
  files: 1
---

# Phase 06 Plan 01: Payment Registration Test Scaffold Summary

RED phase TDD scaffold for payment registration. 10 named test stubs created covering PAY-01 (register payment), PAY-02 (advance payments), and PAY-03 (balance consistency after payment and void). All tests skip cleanly — no collection errors, 0 failures.

## What Was Built

`backend/tests/test_payments.py` — 284 lines, 10 test functions, 3 helper factories.

### Helper Factories

| Function | Purpose |
|----------|---------|
| `_make_client(db, tenant_id)` | Creates Client with unique NUIT |
| `_make_billing_document(db, tenant_id, client_id, ...)` | Creates BillingDocument with 2026-01 period |
| `_make_payment(db, tenant_id, client_id, amount, ...)` | Creates ClientPayment row directly (for test setup) |

### Test Stubs

| Test Name | Requirement | What it will assert (Plan 02) |
|-----------|-------------|-------------------------------|
| `test_register_full_payment` | PAY-01 | Full payment → invoice.status="paid", allocation created |
| `test_register_partial_payment` | PAY-01 | Partial payment → invoice stays "issued", balance reduced |
| `test_payment_idempotency` | PAY-01 | Same Idempotency-Key → one payment row, same id returned |
| `test_payment_client_mismatch` | PAY-01 | Wrong client on invoice → 409 payment_client_mismatch |
| `test_payment_exceeds_balance` | PAY-01 | amount > remaining → 409 payment_exceeds_invoice_balance |
| `test_advance_payment` | PAY-02 | billing_document_id=None → payment confirmed, 0 allocations |
| `test_apply_advance` | PAY-02 | Apply advance → allocation created, invoice paid |
| `test_advance_over_applied` | PAY-02 | amount_applied > payment.amount → 409 |
| `test_balance_updated_after_payment` | PAY-03 | _get_outstanding_balance reflects payment deduction |
| `test_void_restores_balance` | PAY-03 | void_payment → invoice reverted to "issued", balance restored |

## Verification

```
$ python -m pytest tests/test_payments.py -v
10 skipped in 0.10s  ← all skip, 0 failed, 0 errors
```

```
$ python -m pytest tests/ -x -q --ignore=tests/test_payments.py
1 failed, 42 passed  ← pre-existing test_composite_indexes failure (unrelated)
```

## Deviations from Plan

None — plan executed exactly as written. The `test_composite_indexes.py` failure is pre-existing (missing DB index from a different phase, out of scope).

## Known Stubs

All 10 test bodies contain `assert False, "..."` stubs. This is intentional — Plan 02 will replace these with real assertions against the implemented service. The stub bodies are never reached because `@pytest.mark.skip` prevents execution.

## Self-Check: PASSED

- `backend/tests/test_payments.py` exists: FOUND
- Commit `29aa6a7` exists: FOUND
- 10 tests collected, 10 SKIPPED, 0 FAILED: VERIFIED
