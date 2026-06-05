---
phase: 04-production-hardening-scale-preparation
plan: "01"
subsystem: backend
tags: [dependencies, test-stubs, arq, redis, gunicorn, tdd, maintenance-scheduler, rls, indexes]
dependency_graph:
  requires: []
  provides: [arq-installed, redis-asyncio-installed, gunicorn-installed, test-stubs-maintenance-scheduler, test-stubs-driver-scorecard, test-stubs-composite-indexes, test-stubs-rls]
  affects: [04-02-PLAN, 04-03-PLAN, 04-04-PLAN, 04-06-PLAN, 04-08-PLAN]
tech_stack:
  added: [arq>=0.26, redis[asyncio]>=5.0, gunicorn>=22.0]
  patterns: [pytest.mark.skip stubs for TDD RED state]
key_files:
  created:
    - backend/tests/test_maintenance_scheduler.py
    - backend/tests/test_driver_scorecard.py
    - backend/tests/test_composite_indexes.py
    - backend/tests/test_rls.py
  modified:
    - backend/pyproject.toml
decisions:
  - "Use pytest.mark.skip (not xfail) for stubs — skip exits 0 cleanly; xfail would count as expected failure and obscure regressions"
  - "arq 0.28.0 + redis 5.3.1 + gunicorn 26.0.0 installed (within >=0.26, >=5.0, >=22.0 constraints)"
metrics:
  duration: "5 minutes"
  completed_date: "2026-06-05"
  tasks_completed: 2
  files_changed: 5
---

# Phase 4 Plan 01: Wave 0 — Dependencies and Test Stubs Summary

Wave 0 bootstrap for Phase 4: installed arq/redis/gunicorn background job infrastructure and created 16 failing test stubs across 4 files covering MAINT-01 preventive maintenance, driver scorecard, composite indexes, and PostgreSQL RLS.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add arq, gunicorn, redis[asyncio] to pyproject.toml and install | 1e4ed25 | backend/pyproject.toml |
| 2 | Create failing test stubs for MAINT-01, scorecard, indexes, and RLS | 4a220e1 | backend/tests/test_maintenance_scheduler.py, test_driver_scorecard.py, test_composite_indexes.py, test_rls.py |

## Verification Results

- `python -c "import arq; import gunicorn; import redis.asyncio; print('OK')"` → OK
- `pytest --collect-only` on all 4 stub files → 16 tests collected, 0 errors
- `pytest` on all 4 stub files → 16 skipped, 0 failed, exit 0

## Stubs Created

### test_maintenance_scheduler.py (6 stubs)
| Test | Target Plan | Behavior |
|------|-------------|----------|
| test_scheduler_creates_work_order_on_km_trigger | 04-02 | km-based maintenance trigger creates WorkOrder draft |
| test_scheduler_creates_work_order_on_date_trigger | 04-02 | date-based maintenance trigger creates WorkOrder draft |
| test_scheduler_skips_duplicate_work_order | 04-02 | open WorkOrder prevents duplicate creation |
| test_next_cycle_schedule_created_after_trigger | 04-02 | next cycle schedule row created after trigger |
| test_odometer_event_enqueues_arq_task | 04-03 | fuel log odometer update enqueues ARQ task |
| test_imminent_maintenance_alerts | 04-02 | API returns vehicles due within 30 days or 500 km |

### test_driver_scorecard.py (4 stubs)
| Test | Target Plan | Behavior |
|------|-------------|----------|
| test_scorecard_score_range | 04-04 | score 0-100, tier verde/amarelo/vermelho/insuficiente |
| test_scorecard_insufficient_data | 04-04 | <3 trips returns score=None, tier=insuficiente |
| test_scorecard_no_division_by_zero | 04-04 | 0 trips returns None, not ZeroDivisionError |
| test_scorecard_api_endpoint_returns_200 | 04-04 | GET /drivers/{id}/scorecard returns 200 for manager |

### test_composite_indexes.py (3 stubs)
| Test | Target Plan | Behavior |
|------|-------------|----------|
| test_trips_composite_indexes_exist | 04-06 | 4 composite indexes on trips table after migration |
| test_fuel_logs_composite_indexes_exist | 04-06 | 2 composite indexes on fuel_logs table |
| test_maintenance_composite_indexes_exist | 04-06 | 2 composite indexes on maintenance tables |

### test_rls.py (3 stubs)
| Test | Target Plan | Behavior |
|------|-------------|----------|
| test_rls_blocks_cross_tenant_trip_access | 04-08 | DB-level RLS blocks cross-tenant trip reads |
| test_rls_set_local_scoped_to_transaction | 04-08 | SET LOCAL scoped to transaction, not connection |
| test_rls_tenant_isolation_policy_exists | 04-08 | pg_policies shows tenant_isolation policy on trips |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

All test files are intentional stubs tracked for implementation in later plans:
- `backend/tests/test_maintenance_scheduler.py` — 6 stubs pending 04-02 and 04-03
- `backend/tests/test_driver_scorecard.py` — 4 stubs pending 04-04
- `backend/tests/test_composite_indexes.py` — 3 stubs pending 04-06
- `backend/tests/test_rls.py` — 3 stubs pending 04-08

These stubs are the intended output of this plan (RED state). They will be turned GREEN in their respective implementation plans.

## Self-Check: PASSED

- backend/pyproject.toml: contains arq>=0.26, redis[asyncio]>=5.0, gunicorn>=22.0
- backend/tests/test_maintenance_scheduler.py: exists, 6 tests
- backend/tests/test_driver_scorecard.py: exists, 4 tests
- backend/tests/test_composite_indexes.py: exists, 3 tests
- backend/tests/test_rls.py: exists, 3 tests
- Commit 1e4ed25: pyproject.toml dependencies
- Commit 4a220e1: 4 test stub files, 175 insertions
