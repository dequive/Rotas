---
phase: quick-260621-f5i
plan: 01
subsystem: billing, trips, cargo
tags: [audit-log, billing, state-machine, patch, compliance]
key-decisions:
  - "BILLABLE_PROOF_STATUSES defined in cargo/service.py and imported into billing/service.py (Option A — no circular import)"
  - "user_id=None passed to record_audit_log in patch functions — no user context available at that call site"
  - "km_end guard added to list_billable_trips with Trip.km_end.is_not(None)"
  - "complete_trip added to existing API integration tests to satisfy km_end guard (regression fix)"
  - "User created in SM-03 test to satisfy accepted_by FK constraint on delivery_proofs"
key-files:
  modified:
    - backend/app/modules/trips/service.py
    - backend/app/modules/cargo/service.py
    - backend/app/modules/billing/service.py
    - backend/tests/test_cargo_billing_flow.py
metrics:
  duration: "~25 minutes"
  completed_date: "2026-06-21"
  tasks: 3
  files: 4
---

# Quick Task 260621-f5i: P0.6 Audit Log em Mutações Financeiras + P0.1 Pipeline Billable BILLABLE_PROOF_STATUSES

**One-liner:** Patch audit trail for trip/stop/proof mutations + BILLABLE_PROOF_STATUSES constant closes SM-03 dead-end + km_end guard on list_billable_trips prevents incomplete trips entering billing.

## What Was Done

### Task 1 — Audit logs in patch_trip, patch_stop, patch_delivery_proof

Three surgical edits to `backend/app/modules/trips/service.py` and `backend/app/modules/cargo/service.py`:

- `patch_trip`: capture `old_values` dict before setattr loop, add `db.flush()`, call `record_audit_log(action="trip.patched")`, then `db.commit()`
- `patch_stop`: same pattern, `action="trip_stop.patched"`, `entity_type="trip_stop"`
- `patch_delivery_proof`: same pattern with `applied` dict (only patchable fields), `action="delivery_proof.patched"`

All three pass `user_id=None` — no user context is available in these service functions.

**Commit:** `5305e1a`

### Task 2 — BILLABLE_PROOF_STATUSES + create_document fix + km_end guard

- Added `BILLABLE_PROOF_STATUSES: frozenset[str] = frozenset({"validated", "verified", "accepted"})` to `cargo/service.py` after `_DELIVERY_PROOF_VALID_TRANSITIONS`
- Imported it in `billing/service.py`: `from app.modules.cargo.service import BILLABLE_PROOF_STATUSES`
- Replaced hardcoded `DeliveryProof.status.in_(("validated", "verified"))` with `DeliveryProof.status.in_(BILLABLE_PROOF_STATUSES)` in `create_document`
- Added `.where(Trip.km_end.is_not(None))` to `list_billable_trips` query
- Updated `test_trip_first_flow_reaches_billing_document` to call `complete_trip` before `list_billable_trips` (sets km_end)

**Commit:** `6716124`

### Task 3 — Three new tests + regression fixes

Three new test functions appended to `backend/tests/test_cargo_billing_flow.py`:

1. `test_sm03_accept_delivery_proof_reaches_billing` — full SM-03 accept path reaches `create_document` without `delivery_proof_required` error
2. `test_list_billable_trips_excludes_trips_without_km_end` — trip with `billing_status=billable` but `km_end=None` absent from candidates; appears after setting km_end
3. `test_patch_trip_and_stop_produce_audit_logs` — patch mutations produce AuditLog rows with correct old_values/new_values

Also fixed existing API integration tests (`test_api_trip_first_flow_respects_billing_issue_boundary`, `test_delivery_proof_dispute_blocks_validation_and_billing`) to add `start_trip` + `complete_trip` calls before `create_delivery_proof` — required now that `list_billable_trips` guards on `km_end IS NOT NULL`.

**Commit:** `4c521ee`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing API tests broken by km_end guard**
- **Found during:** Task 3 (full test suite run)
- **Issue:** Two existing API integration tests called `create_delivery_proof` without `start_trip`/`complete_trip` first, so `km_end` was always null. After the km_end guard was added, `list_billable_trips` returned empty — breaking assertions.
- **Fix:** Added `/start` and `/complete` API calls in both tests before delivery proof creation.
- **Files modified:** `backend/tests/test_cargo_billing_flow.py`

**2. [Rule 1 - Bug] accepted_by FK constraint in SM-03 test**
- **Found during:** Task 3 (first test run)
- **Issue:** `accept_delivery_proof` stores `user_id` as `accepted_by` which has a FK to `users.id`. Passing `uuid4()` violated the constraint.
- **Fix:** Created a real `User` row in the test before calling `accept_delivery_proof`.

**3. [Rule 1 - Bug] UUID(trip["id"]) fails — trip["id"] is already a UUID**
- **Found during:** Task 3 (third test run)
- **Issue:** `serialize_trip` returns `trip.id` as a Python `UUID` object. Wrapping it in `UUID(...)` fails since the constructor expects a string.
- **Fix:** Used `trip["id"]` directly in all AuditLog filter queries and TripStop model instantiation.

**4. [Rule 1 - Bug] TripStop.location is JSON, not string**
- **Found during:** Task 3 (TripStop insert failure)
- **Issue:** `TripStop.location` is `Mapped[dict | None]` (JSON column). Also `stopped_at` is NOT NULL with no server default.
- **Fix:** Changed test to use `location={"name": "Inchope"}` dict and added `stopped_at=dt(...)`.

## Test Results

```
420 passed, 2 skipped in 154.44s
```

All 6 tests in `test_cargo_billing_flow.py` pass. No regressions across the full test suite.

## Known Stubs

None — all code paths are fully wired.

## Self-Check: PASSED

- `backend/app/modules/cargo/service.py` contains `BILLABLE_PROOF_STATUSES` — confirmed
- `backend/app/modules/billing/service.py` imports and uses `BILLABLE_PROOF_STATUSES` — confirmed
- `backend/app/modules/trips/service.py` contains `record_audit_log` calls in `patch_trip` and `patch_stop` — confirmed
- Commits `5305e1a`, `6716124`, `4c521ee` — all present in `git log`
- 420 passed, 0 failures
