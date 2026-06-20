---
phase: 16-hours-of-service-availability
plan: "03"
subsystem: backend/availability
tags: [availability, redis, caching, fleet-status, fastapi]
dependency_graph:
  requires: [16-01]
  provides: [AVAIL-01, AVAIL-02]
  affects: [backend/app/modules/availability/router.py]
tech_stack:
  added: []
  patterns:
    - Redis cache-aside with NX stampede lock (30s TTL) — mirrors control_tower pattern
    - Full-fleet fetch + Python-side filter+paginate (avoids DB pagination before filter)
    - Per-entity try/except in list computation — single error skips entity, not list
key_files:
  created:
    - backend/tests/test_availability_endpoints.py
  modified:
    - backend/app/modules/availability/router.py
decisions:
  - Fetch full fleet from DB (no LIMIT on query) so filter+paginate is correct — total reflects filtered count not raw DB page
  - driver item exposes both `status` (DB field: active/inactive) and `availability_status` (derived: available/hos_warning/hos_violation/unavailable) to avoid naming collision
  - vehicle item exposes both `status` and `computed_status` (same value) for API consumer convenience
  - HOS enrichment reads `summary.get("hos", {})` — defaults to ok status so endpoint works before plan 16-02 merges
metrics:
  duration: "~15 minutes"
  completed: "2026-06-20T17:46:28Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 2
---

# Phase 16 Plan 03: Availability Endpoints with Redis Cache Summary

One-liner: GET /availability/drivers and GET /availability/vehicles with Redis cache-aside (30s TTL), status filter, and correct per-entity blocker-derived status computation.

## What Was Built

Replaced the stub router.py scaffold from plan 16-01 with a production-quality implementation:

**GET /api/v1/availability/drivers**
- Queries all `status="active"` drivers for the tenant (no DB-level pagination — full fleet fetch)
- Calls `availability_service.driver_availability_summary()` per driver with per-entity error handling
- Derives `availability_status` from blockers + HOS: `available` | `hos_warning` | `hos_violation` | `unavailable`
- Reads `summary.get("hos", {})` for HOS enrichment — forwards-compatible with plan 16-02
- Caches full list as JSON in Redis key `av:drivers:{tenant_id}` with 30s TTL + NX stampede lock (5s)
- Status filter applied in Python after cache; pagination (offset+limit) applied after filter
- Falls back to DB compute when Redis is None

**GET /api/v1/availability/vehicles**
- Queries all vehicles for the tenant (includes inactive for full fleet picture)
- Derives `computed_status` from blocker codes: `available` | `in_trip` | `in_maintenance` | `unavailable`
- Extracts `active_work_order_id` from the `vehicle_workshop_blocked` blocker entry
- Same Redis cache-aside pattern: `av:vehicles:{tenant_id}`
- Status filter uses `computed_status` field

**Response shape (both endpoints):**
```json
{"items": [...], "total": 10, "limit": 50, "offset": 0}
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect driver status filter**
- **Found during:** Task 1 analysis — existing router.py from 16-01 filtered by `i["status"]` (DB field: "active"/"inactive") instead of the availability-derived status
- **Fix:** Added `_driver_availability_status()` helper and `availability_status` field to each driver item; `_filter_drivers()` uses the plan's exact filter logic (available/hos_warning/hos_violation/unavailable)
- **Files modified:** backend/app/modules/availability/router.py

**2. [Rule 1 - Bug] Fixed incorrect vehicle status filter**
- **Found during:** Task 1 analysis — existing code filtered by `i["status"]` but should filter by `computed_status`
- **Fix:** Vehicle items now expose `computed_status` as an explicit key; `_filter_vehicles()` reads `computed_status`

**3. [Rule 1 - Bug] Fixed pagination total incorrectly reflecting page size**
- **Found during:** Task 1 analysis — original code computed `total = len(items)` AFTER slicing, so total was always <= limit
- **Fix:** Filter first (`filtered = _filter_drivers(all_items, status)`), then `total = len(filtered)`, then slice for page

**4. [Rule 2 - Missing] Added per-entity error handling**
- **Found during:** Plan spec review — plan explicitly requires catching ApiError per entity
- **Fix:** Wrapped each `driver_availability_summary()` / `vehicle_availability_summary()` call in `try/except Exception` with log warning; single entity errors skip that entity rather than failing the entire list

**5. [Rule 1 - Bug] Fixed `hos_status` hardcoded to "pending"**
- **Found during:** Task 1 analysis — stub router set `"hos_status": "pending"` unconditionally
- **Fix:** Reads `summary.get("hos", {}).get("status", "ok")` — returns "ok" until plan 16-02 merges HOS computation

## Known Stubs

None — all response fields are computed from real DB data.

## Self-Check: PASSED

Files verified:
- FOUND: backend/app/modules/availability/router.py
- FOUND: backend/tests/test_availability_endpoints.py
- FOUND commit 5e4c0f8 in git log
