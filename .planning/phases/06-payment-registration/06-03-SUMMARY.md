---
phase: 06-payment-registration
plan: "03"
subsystem: billing/clients HTTP layer
tags: [payments, billing, clients, router, fastapi]
dependency_graph:
  requires: ["06-02"]
  provides: ["06-04"]
  affects: [billing, clients]
tech_stack:
  added: []
  patterns: [execute_http_idempotent, require_roles, ADMIN_ROLES/WRITE_ROLES]
key_files:
  modified:
    - backend/app/modules/billing/router.py
    - backend/app/modules/clients/router.py
decisions:
  - "GET /billing/payments skipped — list_payments service function not implemented in 06-02; only the 3 POST endpoints from the task spec were added"
  - "Payment routes inserted before /ar catch-all to preserve correct FastAPI route ordering"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-19"
  tasks_completed: 2
  files_modified: 2
---

# Phase 06 Plan 03: Payment HTTP Endpoints Summary

Wire the payment service layer (from Plan 02) into FastAPI HTTP endpoints — router-only changes, no service logic added.

## What Was Built

Four new HTTP endpoints across two routers:

**`backend/app/modules/billing/router.py` — 3 new endpoints:**

| Method | Path | Roles | Pattern |
|--------|------|-------|---------|
| POST | `/api/v1/billing/payments` | WRITE_ROLES | `execute_http_idempotent` |
| POST | `/api/v1/billing/payments/{payment_id}/void` | ADMIN_ROLES | direct service call |
| POST | `/api/v1/billing/payments/{payment_id}/apply` | WRITE_ROLES | direct service call |

**`backend/app/modules/clients/router.py` — 1 new endpoint:**

| Method | Path | Roles | Pattern |
|--------|------|-------|---------|
| GET | `/api/v1/clients/{client_id}/statement` | any authenticated | direct service call |

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
tests/test_billing_api.py::test_invoice_number_format    PASSED
tests/test_billing_api.py::test_invoice_number_increments PASSED

12 passed in 5.72s
```

## Deviations from Plan

**1. [Rule 1 - Missing Function] GET /billing/payments not added**
- **Found during:** Task 1 pre-check
- **Issue:** The plan description mentioned `GET /api/v1/billing/payments → list_payments` but no `list_payments` function exists in `billing/service.py`. The task spec itself only listed 3 POST endpoints.
- **Fix:** Skipped the GET endpoint — task spec took precedence over plan description. Listing payments can be added in a future plan once the service function exists.
- **Impact:** No test coverage for this endpoint was expected (test_payments.py had 10 tests, all passing against the 3 service functions that do exist).

## Known Stubs

None. All 4 endpoints wire directly to real service implementations with full DB-backed logic.

## Self-Check: PASSED

- `backend/app/modules/billing/router.py` — modified, payment routes present
- `backend/app/modules/clients/router.py` — modified, statement route present
- Commit `9d2d823` exists and contains both files
- 12/12 tests pass
