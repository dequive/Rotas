---
phase: 04-production-hardening-scale-preparation
plan: "04"
subsystem: drivers
tags: [scorecard, analytics, drivers, aggregation, rbac]
dependency_graph:
  requires: [04-01]
  provides: [driver-scorecard-api]
  affects: [drivers-module, trips-module, sync-module, cargo-module]
tech_stack:
  added: []
  patterns: [sql-aggregation, composite-score, rolling-window, rbac-roles]
key_files:
  created:
    - backend/tests/test_driver_scorecard.py
  modified:
    - backend/app/modules/drivers/service.py
    - backend/app/modules/drivers/router.py
decisions:
  - "require_roles(*DASHBOARD_ROLES) used for scorecard endpoint — driver tokens rejected at dependency level, no manual scope check needed"
  - "Local now_utc() helper defined in service.py (pattern used in trips, cargo, workshop modules)"
  - "SyncEvent has driver_id column — direct filter without join used for sync discipline metric"
  - "Composite score uses 0.40/0.25/0.20/0.15 weights per D-08 spec"
metrics:
  duration: "8m"
  completed_date: "2026-06-05"
  tasks: 2
  files: 3
---

# Phase 04 Plan 04: Driver Scorecard API Summary

**One-liner:** Composite driver scorecard (0–100) aggregating delivery proof rate, sync discipline, distance, and stop efficiency from existing trip/sync/cargo data, with tier labels and manager-only RBAC.

## What Was Built

Implemented the driver scorecard feature (D-08 through D-11) as a pure read aggregation over existing data — no new tables, no new data collection.

**`get_driver_scorecard()` in `backend/app/modules/drivers/service.py`:**
- Accepts `db`, `tenant_id`, `driver_id`, `days=30`
- Returns `insuficiente` tier with `score=None` when driver has fewer than 3 completed trips in the window (division-by-zero protection)
- Formula: 40% delivery proof rate + 25% sync discipline + 20% distance + 15% stop efficiency
- All aggregations are SQL-only (no Python-level row iteration)
- Returns plain dict per project service layer convention

**`GET /api/v1/drivers/{driver_id}/scorecard` in `backend/app/modules/drivers/router.py`:**
- Query param: `days` (7–90, default 30)
- Protected by `require_roles(*DASHBOARD_ROLES)` — driver tokens (role=None) are rejected with 403
- Delegates entirely to `service.get_driver_scorecard()`

**Score tiers (D-09):**
- `verde`: score >= 80
- `amarelo`: score 60–79
- `vermelho`: score < 60
- `insuficiente`: fewer than 3 completed trips in window (score = None)

## Tests

4 integration tests in `backend/tests/test_driver_scorecard.py` — all 4 green, replacing skip stubs:
- `test_scorecard_score_range` — valid tier and 0–100 score range
- `test_scorecard_insufficient_data` — driver with 0 trips returns `score=None`, `tier=insuficiente`
- `test_scorecard_no_division_by_zero` — 0-trip driver returns 200, not 500
- `test_scorecard_api_endpoint_returns_200` — endpoint returns 200 with correct `driver_id`

## Deviations from Plan

None — plan executed exactly as written. The `require_roles(*DASHBOARD_ROLES)` pattern from existing endpoints was used directly instead of a manual `principal.scope` check, which is cleaner and consistent with the rest of the router.

## Self-Check: PASSED

- FOUND: backend/app/modules/drivers/service.py
- FOUND: backend/app/modules/drivers/router.py
- FOUND: backend/tests/test_driver_scorecard.py
- FOUND: commit 8ca68c4 (feat(04-04): add get_driver_scorecard())
- FOUND: commit 85bc36f (feat(04-04): add scorecard endpoint + green tests)
