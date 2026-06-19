---
phase: 23-third-party-registry
plan: 04
subsystem: third_party
tags: [eligibility, domain-service, pure-function, tdd, drivers]
requirements: [TP-07]
dependency_graph:
  requires: []
  provides: [check_driver_eligibility, EligibilityResult]
  affects: [backend/app/modules/third_party/eligibility.py]
tech_stack:
  added: []
  patterns: [pure-function, dataclass-result, TYPE_CHECKING-import]
key_files:
  created:
    - backend/app/modules/third_party/__init__.py
    - backend/app/modules/third_party/eligibility.py
    - backend/tests/test_driver_eligibility.py
  modified:
    - .planning/phases/23-third-party-registry/23-04-PLAN.md
decisions:
  - "Used TYPE_CHECKING guard for Driver import to keep eligibility.py free of ORM load-time side effects"
  - "reference_date defaults to date.today() so callers can pass explicit dates in tests and scheduled checks"
  - "Field names in messages match plan spec exactly: driver_license, passport, bi"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-19"
  tasks: 2
  files: 3
---

# Phase 23 Plan 04: Operational Eligibility Service Summary

Pure-Python `check_driver_eligibility` function with `EligibilityResult` dataclass — reads existing Driver fields (status, license_valid_until, passport_valid_until, bi_valid_until) and returns blocking reasons + expiring-soon warnings, with 8 deterministic unit tests all passing.

## What Was Built

### `backend/app/modules/third_party/eligibility.py`

- `EXPIRY_WARNING_DAYS = 30` constant
- `EligibilityResult` dataclass: `is_eligible`, `blocking_reasons`, `expiring_soon`, `checked_at`
- `check_driver_eligibility(driver, reference_date=None) -> EligibilityResult`
  - Status check: blocks if `driver.status != "active"`
  - Date checks for `license_valid_until` → label `driver_license`, `passport_valid_until` → label `passport`, `bi_valid_until` → label `bi`
  - None date = not on file = no check (not blocking)
  - Expired: appended to `blocking_reasons`
  - Within 30 days: appended to `expiring_soon` (still eligible)
- `_check_date` private helper — keeps main function clean

### `backend/tests/test_driver_eligibility.py`

8 test cases with fixed `REF = date(2026, 6, 19)`:

| Test | Scenario | Assert |
|------|----------|--------|
| `test_all_clear_eligible` | Active, all docs 90 days out | `is_eligible=True`, both lists empty |
| `test_suspended_driver_not_eligible` | status="suspended" | `is_eligible=False`, "suspended" in blocking |
| `test_expired_license_not_eligible` | license -1 day | `is_eligible=False`, "driver_license" in blocking |
| `test_expired_bi_not_eligible` | bi -10 days | `is_eligible=False`, "bi" in blocking |
| `test_expired_passport_not_eligible` | passport -5 days | `is_eligible=False`, "passport" in blocking |
| `test_expiring_soon_warning` | license +15 days | `is_eligible=True`, "driver_license" in expiring_soon |
| `test_none_dates_skipped` | all dates None | `is_eligible=True`, both lists empty |
| `test_custom_reference_date` | license +10d relative REF, ref +20d | `is_eligible=False` (license expired relative to shifted ref) |

**Result:** 8/8 passed in 0.40s.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- `backend/app/modules/third_party/eligibility.py` — exists, confirmed
- `backend/tests/test_driver_eligibility.py` — exists, confirmed
- RED commit: `3762c09`
- GREEN commit: `3eaa9b5`
- All 8 tests pass, function is synchronous
