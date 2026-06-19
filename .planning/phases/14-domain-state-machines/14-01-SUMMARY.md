---
plan: 14-01
phase: 14
title: "BillingDocument + Contract State Machines"
status: complete
completed: 2026-06-19
requirements: [SM-01, SM-02]
---

## What was built

All SM-01 + SM-02 implementation was already in place from a prior session:

- **Alembic migration** `e9f8d7c6b5a4_sm01_sm02_state_machine_fields.py` — adds `overdue_since_at`, `cancellation_reason` to `billing_documents`; `paused_at`, `terminated_at`, `termination_reason`, `renewed_at` to `contracts` (`paid_at` already existed)
- **BillingDocument service** (`billing/service.py`) — `_BILLING_VALID_TRANSITIONS`, `transition_billing_document`, `mark_billing_document_paid`, `cancel_billing_document`
- **Contract service** (`contracts/service.py`) — `_CONTRACT_VALID_TRANSITIONS`, `transition_contract`, `renew_contract`
- **Billing router** (`billing/router.py`) — `PATCH /documents/{id}/mark-paid`, `PATCH /documents/{id}/cancel`
- **Contracts router** (`contracts/router.py`) — `PATCH /{contract_id}/status` (activate/pause/resume/expire/terminate/renew)
- **ARQ crons** (`worker.py`) — `task_mark_overdue_billing_documents` (daily 23:00 UTC), `task_expire_contracts` (daily 22:30 UTC)

This plan execution added the missing **tests** (`tests/test_state_machines_sm01_sm02.py`) and fixed a bug in the escalation cron (see 14-02-SUMMARY).

## Key files

- `backend/app/modules/billing/service.py` — SM-01 guard + transitions
- `backend/app/modules/contracts/service.py` — SM-02 guard + transitions
- `backend/app/modules/billing/router.py` — mark-paid + cancel endpoints
- `backend/app/modules/contracts/router.py` — /status transition endpoint
- `backend/app/worker.py` — two daily crons
- `backend/alembic/versions/e9f8d7c6b5a4_sm01_sm02_state_machine_fields.py` — schema
- `backend/tests/test_state_machines_sm01_sm02.py` — 11 tests

## Test results

```
tests/test_state_machines_sm01_sm02.py::test_sm01_cron_marks_overdue PASSED
tests/test_state_machines_sm01_sm02.py::test_sm01_mark_paid_transitions_issued_to_paid PASSED
tests/test_state_machines_sm01_sm02.py::test_sm01_mark_paid_on_draft_returns_409 PASSED
tests/test_state_machines_sm01_sm02.py::test_sm01_invalid_transition_paid_to_issued_returns_409 PASSED
tests/test_state_machines_sm01_sm02.py::test_sm01_cancel_document PASSED
tests/test_state_machines_sm01_sm02.py::test_sm02_cron_expires_active_contract PASSED
tests/test_state_machines_sm01_sm02.py::test_sm02_renew_without_new_ends_at_returns_422 PASSED
tests/test_state_machines_sm01_sm02.py::test_sm02_terminate_without_reason_returns_422 PASSED
tests/test_state_machines_sm01_sm02.py::test_sm02_terminate_creates_audit_log PASSED
tests/test_state_machines_sm01_sm02.py::test_sm02_activate_draft_contract PASSED
tests/test_state_machines_sm01_sm02.py::test_sm02_invalid_transition_terminated_to_active_returns_409 PASSED
11 passed
```

## Deviations

None from plan intent. Tests were the missing artifact.
The test error-code assertions use `data["error"]["code"]` (not `data["code"]`) to match the ROTAS API error envelope `{"error": {"code": ..., "message": ..., "details": {}}}`.

## Self-Check: PASSED
