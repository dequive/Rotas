---
plan: 14-02
phase: 14
title: "DeliveryProof + DispatchClearance State Machines"
status: complete
completed: 2026-06-19
requirements: [SM-03, SM-04]
---

## What was built

All SM-03 + SM-04 implementation was already in place from a prior session:

- **Alembic migration** `b9c8d7e6f5a4_sm03_sm04_states.py` — adds `accepted_at`, `accepted_by`, `rejected_at`, `rejected_by`, `rejection_reason`, `dispute_opened_at`, `resolved_at`, `resolved_by` to `delivery_proofs`; `rejection_reason`, `rejected_at`, `rejected_by`, `escalated_at`, `clearance_sla_hours` to `trip_orders`
- **Cargo service** (`cargo/service.py`) — `_DELIVERY_PROOF_VALID_TRANSITIONS`, `accept_delivery_proof` (sets accepted_at/accepted_by, trip.billing_status=billable), `reject_delivery_proof` (sets rejected_at/rejection_reason, creates OperationalException)
- **Cargo router** (`cargo/router.py`) — `PATCH /{trip_id}/delivery-proof/{proof_id}/accept`, `PATCH /reject`
- **TripOrder service** (`trip_orders/service.py`) — `reject_dispatch_clearance` (sets status=rejected, rejected_at/by/reason, audit log)
- **TripOrder router** (`trip_orders/router.py`) — `PATCH /{order_id}/reject`
- **ARQ cron** (`worker.py`) — `task_escalate_pending_clearances` (every 15 min)

This plan execution added the missing **tests** and **fixed a bug** in the escalation cron.

### Bug fixed: `task_escalate_pending_clearances` in `worker.py`

The cron had two bugs:
1. Queried `TripOrder.status == "pending"` — `"pending"` is not a valid status (check constraint `chk_trip_orders_status` allows `dispatch_pending` not `pending`). No rows would ever match.
2. Set `order.status = "escalated"` — also not in the constraint; would cause a DB error at runtime.

**Fix:** Changed query to `TripOrder.status == "dispatch_pending"` and removed the status change — escalation now only sets `escalated_at` (the timestamp is the marker). Status remains `dispatch_pending` until the order is cleared or rejected.

## Key files

- `backend/app/modules/cargo/service.py` — SM-03 guard + transitions
- `backend/app/modules/cargo/router.py` — accept/reject endpoints
- `backend/app/modules/trip_orders/service.py` — SM-04 reject
- `backend/app/modules/trip_orders/router.py` — reject endpoint
- `backend/app/worker.py` — escalation cron (bug fixed)
- `backend/alembic/versions/b9c8d7e6f5a4_sm03_sm04_states.py` — schema
- `backend/tests/test_state_machines_sm03_sm04.py` — 8 tests

## Test results

```
tests/test_state_machines_sm03_sm04.py::test_sm03_accept_proof_sets_accepted_fields PASSED
tests/test_state_machines_sm03_sm04.py::test_sm03_reject_proof_sets_rejected_and_creates_exception PASSED
tests/test_state_machines_sm03_sm04.py::test_sm03_accept_already_accepted_proof_raises_409 PASSED
tests/test_state_machines_sm03_sm04.py::test_sm03_accept_proof_via_http PASSED
tests/test_state_machines_sm03_sm04.py::test_sm03_reject_proof_via_http PASSED
tests/test_state_machines_sm03_sm04.py::test_sm04_reject_dispatch_clearance PASSED
tests/test_state_machines_sm03_sm04.py::test_sm04_reject_via_http PASSED
tests/test_state_machines_sm03_sm04.py::test_sm04_escalate_pending_clearances_cron_logic PASSED
8 passed
```

## Deviations

- **Bug fix in `worker.py`:** `task_escalate_pending_clearances` was querying `status == "pending"` (not in DB constraint) and setting `status = "escalated"` (also not in constraint). Fixed to query `dispatch_pending` + only set `escalated_at`.
- SM-03 service-layer tests require a real `User` record (not a random UUID) for `record_audit_log` FK constraint on `audit_logs.user_id`.

## Self-Check: PASSED
