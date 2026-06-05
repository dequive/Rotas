---
phase: 02-pwa-offline-first-completion
plan: "04"
subsystem: backend-auth
tags: [auth, driver, error-codes, d-08]
dependency_graph:
  requires: [02-01]
  provides: [driver_access_revoked error code in auth.py]
  affects: [apps/driver/src/api.ts — refreshAccessToken reads body.error === 'driver_access_revoked']
tech_stack:
  added: []
  patterns: [staged-auth-checks, specific-error-codes]
key_files:
  created: []
  modified:
    - backend/app/core/auth.py
    - backend/tests/test_driver_revocation.py
decisions:
  - "Revocation check placed before suspension check — if manager simultaneously deactivates device AND marks driver inactive, device revocation error takes precedence (permanent > temporary)"
  - "Device query without is_active filter to distinguish 'deactivated device' from 'device not found'"
metrics:
  duration: "8 minutes"
  completed: "2026-06-05"
  tasks_completed: 1
  files_modified: 2
---

# Phase 02 Plan 04: Driver Access Revocation Error Code — Summary

**One-liner:** Staged `get_current_principal` driver_app checks return `driver_access_revoked` (permanent revocation) vs `driver_inactive` (temporary suspension) so the PWA can show the correct message and preserve offline data.

## What Was Built

Single focused change to `backend/app/core/auth.py`: the `elif scope == "driver_app"` block was refactored from a single combined conditional into staged checks:

1. Driver not found / wrong tenant → `driver_inactive`
2. Device not found (device_id not in DB) → `driver_inactive`
3. Device found but `is_active=False` → `driver_access_revoked` (NEW)
4. Driver status != "active" → `driver_inactive`
5. Happy path (device active, driver active) → `Principal` returned normally

The key query change: device is now queried WITHOUT the `DriverDevice.is_active.is_(True)` filter, so that a deactivated device returns a record (allowing us to check its `is_active` field) rather than `None` (which was indistinguishable from "device not found").

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Split driver_inactive error code — distinguish device revocation from driver suspension | ad5c39c | backend/app/core/auth.py, backend/tests/test_driver_revocation.py |

## Test Results

- `test_deactivated_driver_device_returns_driver_access_revoked` — PASSED (was RED, now GREEN)
- `test_active_driver_device_succeeds` — PASSED (regression: happy path unchanged)
- `test_sync_auth.py` — 2 PASSED (regression: manager token rejection unchanged)
- Full suite: 53 passed, 1 pre-existing failure in `test_sync_update.py` (unrelated, tracked in that plan's deferred items)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test assertion using wrong error envelope path**
- **Found during:** RED phase verification — test was failing for two reasons, not one
- **Issue:** `test_driver_revocation.py` line 131 used `body.get("detail") or body.get("error") or body.get("error_code")`. The `body.get("error")` returns the nested dict `{"code": ..., "message": ..., "details": ..., "request_id": ...}` (truthy), not the code string. Comparison `dict == "driver_access_revoked"` would always fail even after fixing auth.py.
- **Fix:** Changed to `body["error"]["code"]` which matches the canonical pattern used across all other test files (e.g., `test_fuel_operations_api.py`, `test_vehicle_driver_api.py`)
- **Files modified:** `backend/tests/test_driver_revocation.py`
- **Commit:** ad5c39c

## Known Stubs

None — this plan makes no stubs. The error code is wired end-to-end: auth.py raises `driver_access_revoked`, the test verifies the HTTP response body contains that code.

## Self-Check: PASSED
