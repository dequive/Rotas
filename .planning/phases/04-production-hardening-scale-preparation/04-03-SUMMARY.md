---
phase: 04-production-hardening-scale-preparation
plan: "03"
subsystem: backend-jobs
tags: [arq, maintenance, background-jobs, odometer, fuel]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [arq-worker-package, odometer-event-trigger]
  affects: [backend/app/jobs/, backend/app/modules/fuel/service.py, backend/app/config.py]
tech_stack:
  added: [arq>=0.26 (already in pyproject.toml), RedisSettings, create_pool]
  patterns: [ARQ WorkerSettings, cron_jobs, on_startup/on_shutdown lifecycle, try/except non-fatal enqueue]
key_files:
  created:
    - backend/app/jobs/__init__.py
    - backend/app/jobs/worker.py
    - backend/app/jobs/tasks/__init__.py
    - backend/app/jobs/tasks/maintenance.py
  modified:
    - backend/app/config.py
    - backend/app/modules/fuel/service.py
    - backend/tests/test_maintenance_scheduler.py
decisions:
  - create_pool imported at module level in fuel/service.py to allow patch("...create_pool") mocking in tests
  - redis_settings set as direct class attribute on WorkerSettings (not property) for arq 0.26 compatibility
  - ARQ enqueue inside odometer update guard (only fires when km actually advances) — not on every fuel log
  - Fuel log creation remains non-fatal when Redis unavailable (try/except + warning log)
metrics:
  duration: 13m
  completed: "2026-06-05"
  tasks: 2
  files: 7
requirements_closed: [MAINT-01]
---

# Phase 04 Plan 03: ARQ Worker — Maintenance Scheduler and Odometer Trigger Summary

ARQ background jobs package created with WorkerSettings, daily cron, and per-vehicle odometer trigger; fuel service wired to enqueue `check_vehicle_maintenance` when km advances; all 6 MAINT-01 tests pass.

## What Was Built

### Task 1: ARQ Jobs Package (commit `5f9f432`)

Created `backend/app/jobs/` package with:

- **`backend/app/jobs/worker.py`** — `WorkerSettings` class with:
  - `functions = [check_maintenance_schedules, check_vehicle_maintenance]`
  - `cron_jobs = [cron(check_maintenance_schedules, hour={2}, minute=0)]` — daily at 02:00 UTC
  - `on_startup` — creates async DB engine from `resolved_admin_database_url`, stores `session_factory` in `ctx`
  - `on_shutdown` — disposes DB engine
  - `redis_settings = RedisSettings(host=..., port=...)` from `get_settings()`
- **`backend/app/jobs/tasks/maintenance.py`** — two ARQ tasks:
  - `check_maintenance_schedules(ctx)` — daily cron path, calls `evaluate_maintenance_schedule_all_tenants`
  - `check_vehicle_maintenance(ctx, vehicle_id, tenant_id, current_km)` — per-vehicle path, calls `evaluate_maintenance_schedule` for the specific tenant

Config additions to `backend/app/config.py`:
- `admin_database_url` (ADMIN_DATABASE_URL env var, default `""`)
- `redis_host` (REDIS_HOST env var, default `"localhost"`)
- `redis_port` (REDIS_PORT env var, default `6381`)
- `resolved_admin_database_url` property — falls back to `database_url` if `admin_database_url` is empty

### Task 2: Odometer Event Trigger in Fuel Service (commit `f0ca814`)

Wired ARQ enqueue in `backend/app/modules/fuel/service.py`:
- `create_pool` and `RedisSettings` imported at module level (required for `patch()` mock in tests)
- After the `vehicle.odometer_updated_from_fuel` audit log (when `old_km != new_km`), enqueues `check_vehicle_maintenance` with `vehicle_id`, `tenant_id`, `current_km`
- Wrapped in `try/except Exception` — Redis failure logs a warning but does NOT break fuel log creation

Test `test_odometer_event_enqueues_arq_task` in `backend/tests/test_maintenance_scheduler.py`:
- Removed `@pytest.mark.skip`
- Seeds tenant + vehicle (current_km=0) + driver
- Patches `app.modules.fuel.service.create_pool` with `AsyncMock`
- POSTs fuel log with `km_at_refuel=50000`
- Asserts `enqueue_job` called once with `check_vehicle_maintenance`, correct `vehicle_id`, `tenant_id`, `current_km`

## Test Results

```
tests/test_maintenance_scheduler.py ......  6 passed
tests/ -k "fuel"                        8 passed
```

All 6 MAINT-01 scheduler tests green. All 8 fuel tests green. No regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] create_pool lazy import prevented mock patching**
- **Found during:** Task 2 GREEN phase
- **Issue:** Plan spec placed ARQ imports inside `try` block (lazy). `patch("app.modules.fuel.service.create_pool")` fails with `AttributeError` when `create_pool` is not a module-level attribute
- **Fix:** Moved `create_pool` and `RedisSettings` to module-level imports; removed duplicate lazy imports from `try` block; `get_settings` also moved to module level
- **Files modified:** `backend/app/modules/fuel/service.py`
- **Commit:** `f0ca814`

**2. [Rule 1 - Bug] Wrong API endpoint in test (`/api/v1/fuel-logs` vs `/api/v1/fuel`)**
- **Found during:** Task 2 GREEN phase
- **Issue:** Plan spec used `/api/v1/fuel-logs` but actual router prefix is `/api/v1/fuel` (verified in `fuel/router.py` line 14: `prefix="/fuel"`)
- **Fix:** Corrected endpoint URL in `test_odometer_event_enqueues_arq_task`
- **Files modified:** `backend/tests/test_maintenance_scheduler.py`
- **Commit:** `f0ca814`

**3. [Rule 3 - Blocking] Test re-imported already-imported modules inside function**
- **Found during:** Task 2, test refactor
- **Issue:** Test was re-importing `app.database`, `app.main`, `Driver`, `Tenant`, `Vehicle` inside the function body (leftover from plan spec). Simplified by moving all imports to file top-level
- **Fix:** Added `httpx`, `Driver`, `app.main`, `AsyncMock`, `patch` to top-level imports; removed redundant inner function imports
- **Files modified:** `backend/tests/test_maintenance_scheduler.py`
- **Commit:** `f0ca814`

## Known Stubs

None — all functionality is fully wired and tested.

## Deferred Items

**Pre-existing failures** (not introduced by this plan, confirmed by baseline check):
- `test_tool_checkout_return_and_critical_calibration_controls` — control tower `tool_checkouts_overdue` returns 0
- `test_preventive_maintenance_evaluation_is_idempotent` — control tower `maintenance_overdue` returns 0

These are control tower aggregation bugs predating 04-03, logged to `deferred-items.md`.

## Self-Check: PASSED
