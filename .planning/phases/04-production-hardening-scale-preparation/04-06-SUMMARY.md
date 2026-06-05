---
phase: 04-production-hardening-scale-preparation
plan: "06"
subsystem: database
tags: [indexes, performance, postgresql, alembic, migrations]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [composite-indexes-d14]
  affects: [trips, fuel_logs, maintenance_plans, maintenance_schedule, sync_events, trip_stops]
tech_stack:
  added: []
  patterns: [CREATE INDEX CONCURRENTLY, isolation_level=AUTOCOMMIT in alembic env, transaction_per_migration=False]
key_files:
  created:
    - backend/alembic/versions/b19ec4f5d607_add_composite_indexes.py
  modified:
    - backend/alembic/env.py
    - backend/tests/test_composite_indexes.py
decisions:
  - isolation_level=AUTOCOMMIT on connection required for CONCURRENTLY — transaction_per_migration=False alone is not sufficient with psycopg3
  - Migration down_revision points to 7b6acddf4ab0 (actual DB head) not a1b2c3d4e5f6 (parallel branch)
metrics:
  duration: "10m"
  completed: "2026-06-05"
  tasks: 2
  files: 3
---

# Phase 4 Plan 6: Composite Index Audit (D-14) Summary

**One-liner:** 10 tenant_id-leading composite indexes on trips/fuel_logs/maintenance/sync_events/trip_stops using CREATE INDEX CONCURRENTLY with AUTOCOMMIT env.py pattern.

---

## What Was Built

Alembic migration `b19ec4f5d607_add_composite_indexes.py` creates 10 composite indexes on high-traffic tables with `tenant_id` as the leading column. All indexes use `CREATE INDEX CONCURRENTLY IF NOT EXISTS` to avoid table locks during production deployments. The migration is fully reversible via `DROP INDEX CONCURRENTLY IF EXISTS` in `downgrade()`.

**Indexes created:**

| Index Name | Table | Columns |
|---|---|---|
| ix_trips_tenant_status | trips | (tenant_id, status) |
| ix_trips_tenant_driver_status | trips | (tenant_id, driver_id, status) |
| ix_trips_tenant_vehicle_status | trips | (tenant_id, vehicle_id, status) |
| ix_trips_tenant_actual_departure | trips | (tenant_id, actual_departure) |
| ix_fuel_logs_tenant_vehicle | fuel_logs | (tenant_id, vehicle_id) |
| ix_fuel_logs_tenant_created_at | fuel_logs | (tenant_id, created_at) |
| ix_maintenance_plans_tenant_status_km | maintenance_plans | (tenant_id, status, next_due_km) |
| ix_maintenance_schedule_tenant_status | maintenance_schedule | (tenant_id, status) |
| ix_sync_events_tenant_driver | sync_events | (tenant_id, driver_id) |
| ix_trip_stops_tenant_trip | trip_stops | (tenant_id, trip_id) |

---

## Commits

| Task | Commit | Description |
|---|---|---|
| Task 1: Migration + env.py | 7e33c33 | feat(04-06): add 10 composite indexes with CONCURRENTLY via Alembic migration |
| Task 2: Tests green | fd9d306 | test(04-06): turn composite index test stubs green — 3 tests pass |

---

## Verification

```
cd backend && python -m pytest tests/test_composite_indexes.py -x -q
3 passed in 0.33s
```

Migration roundtrip verified: `upgrade b19ec4f5d607` → `downgrade -1` → `upgrade b19ec4f5d607` all exit 0.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] isolation_level=AUTOCOMMIT required in addition to transaction_per_migration=False**

- **Found during:** Task 1 — first migration run attempt
- **Issue:** `transaction_per_migration=False` alone does not prevent psycopg3 from wrapping statements in a transaction. PostgreSQL raises `CREATE INDEX CONCURRENTLY cannot run inside a transaction block`.
- **Fix:** Added `connection = connection.execution_options(isolation_level="AUTOCOMMIT")` in `run_migrations_online()` before `context.configure(...)`. Also removed the `with context.begin_transaction():` wrapper that was redundant with autocommit.
- **Files modified:** `backend/alembic/env.py`
- **Commit:** 7e33c33

**2. [Rule 1 - Bug] Migration down_revision corrected from a1b2c3d4e5f6 to 7b6acddf4ab0**

- **Found during:** Task 1 — alembic heads check
- **Issue:** `a1b2c3d4e5f6` is a parallel branch head not yet applied to the DB. The actual DB head is `7b6acddf4ab0`. Using `a1b2c3d4e5f6` as down_revision created a split-head situation that prevented `alembic upgrade head`.
- **Fix:** Updated `down_revision` in migration file to point to `7b6acddf4ab0`.
- **Files modified:** `backend/alembic/versions/b19ec4f5d607_add_composite_indexes.py`
- **Commit:** 7e33c33

---

## Known Stubs

None — all functionality is fully wired. Tests query real PostgreSQL `pg_indexes` view.

---

## Self-Check: PASSED

- [x] `backend/alembic/versions/b19ec4f5d607_add_composite_indexes.py` exists
- [x] `backend/alembic/env.py` contains `transaction_per_migration=False`
- [x] `backend/alembic/env.py` contains `isolation_level="AUTOCOMMIT"`
- [x] `backend/tests/test_composite_indexes.py` has 0 `@pytest.mark.skip`
- [x] Commit 7e33c33 exists
- [x] Commit fd9d306 exists
- [x] 3 tests pass, 0 skipped
