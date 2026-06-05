---
phase: "03"
plan: "05"
subsystem: backend/analytics
tags: [analytics, kpi, reporting, multitenant, document-expiry]
one_liner: "New analytics module with KPI aggregation (RPT-01) and document expiry severity alerts (RPT-02), both tenant-isolated"

dependency_graph:
  requires: ["03-01"]
  provides: ["GET /api/v1/analytics/kpis", "GET /api/v1/analytics/document-expiry"]
  affects: ["backend/app/main.py", "backend/app/modules/analytics/"]

tech_stack:
  added: []
  patterns:
    - "SQLAlchemy async aggregation queries with func.count / func.sum / func.coalesce"
    - "Sync compliance warning helpers from availability.service called inside async service"
    - "km computed as km_end - km_start (no distance_km column on Trip)"
    - "FuelLog.fuel_date for period filtering (not created_at)"

key_files:
  created:
    - backend/app/modules/analytics/__init__.py
    - backend/app/modules/analytics/service.py
    - backend/app/modules/analytics/router.py
    - backend/tests/test_analytics_api.py
  modified:
    - backend/app/main.py

decisions:
  - "Used FuelLog (external refuels) for L/100km calculation — VehicleRefuel exists but FuelLog.fuel_date provides the correct date field for period filtering"
  - "Trip distance computed as km_end - km_start — Trip model has no distance_km column"
  - "driver_compliance_warnings and vehicle_compliance_warnings are sync functions — called without await"
  - "Driver.full_name used directly — no first_name/last_name split on Driver model"

metrics:
  duration_minutes: 12
  completed_date: "2026-06-05"
  tasks_completed: 2
  files_created: 4
  files_modified: 1
  tests_added: 3
  tests_passing: 3
---

# Phase 03 Plan 05: Analytics Module Summary

New analytics module with KPI aggregation (RPT-01) and document expiry severity alerts (RPT-02), both tenant-isolated.

## What Was Built

### Task 1: KPI Endpoint (RPT-01)

`GET /api/v1/analytics/kpis` accepts `period_start`, `period_end`, optional `vehicle_id` and `driver_id` filters. Returns:

- `cost_per_km` — list of per-vehicle `{vehicle_id, total_km, total_cost, cost_per_km}`
- `fleet_utilization` — float 0–100, active trips / active vehicles
- `l_per_100km` — float or null, from FuelLog liters / trip km * 100
- `trips_completed` — count of closed trips in period
- `driver_summary` — list of per-driver `{driver_id, trip_count, total_km, total_cost}`

All 5 aggregation queries carry `.where(Trip.tenant_id == tenant_id)` or equivalent model filter — 12 occurrences of `tenant_id` in service.py confirmed.

### Task 2: Document Expiry Endpoint (RPT-02)

`GET /api/v1/analytics/document-expiry` accepts optional `horizon_days` (7–90, default 30). Returns a list sorted by urgency:

- `entity_type` — `"vehicle"` or `"driver"`
- `entity_id`, `entity_name`, `document_type`, `expires_at`, `days_remaining`
- `severity` — `"critical"` (≤7d), `"urgent"` (≤15d), `"warning"` (≤30d)

Calls `vehicle_compliance_warnings()` and `driver_compliance_warnings()` from `availability.service` (sync helpers, no await). Queries vehicles and drivers with `WHERE tenant_id = ? AND status = 'active'`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected Trip distance calculation**
- **Found during:** Task 1 implementation
- **Issue:** Plan spec referenced `Trip.distance_km` but the Trip model has no such column — distance must be computed as `km_end - km_start`
- **Fix:** Used `func.sum(Trip.km_end - Trip.km_start)` in all distance aggregations
- **Files modified:** backend/app/modules/analytics/service.py

**2. [Rule 1 - Bug] Correct fuel date field**
- **Found during:** Task 1 implementation
- **Issue:** Plan spec referenced `VehicleRefuel.created_at` for period filtering; FuelLog is the correct model (external refuels) and uses `FuelLog.fuel_date`
- **Fix:** Used `FuelLog` with `FuelLog.fuel_date >= period_start` filter
- **Files modified:** backend/app/modules/analytics/service.py

**3. [Rule 1 - Bug] Sync vs async compliance helpers**
- **Found during:** Task 2 implementation
- **Issue:** Plan spec showed `await vehicle_compliance_warnings(db, vehicle)` — but the availability service functions are synchronous (no db parameter, no async)
- **Fix:** Called without `await`; also used correct key names from actual return shape (`valid_until`, `days_until_expiry`, `document_type`)
- **Files modified:** backend/app/modules/analytics/service.py

**4. [Rule 1 - Bug] Driver name field**
- **Found during:** Task 2 implementation
- **Issue:** Plan spec used `f"{driver.first_name} {driver.last_name}"` but Driver model has `full_name` only
- **Fix:** Used `driver.full_name` directly
- **Files modified:** backend/app/modules/analytics/service.py

## Test Results

```
tests/test_analytics_api.py::test_kpi_endpoint_returns_expected_fields PASSED
tests/test_analytics_api.py::test_kpi_filters_by_tenant PASSED
tests/test_analytics_api.py::test_document_expiry_returns_severity_levels PASSED
tests/test_cross_tenant_isolation.py (3 tests) PASSED
Full suite: 96 previously passing tests still pass — 0 regressions
```

## Known Stubs

None — all endpoints are fully wired with real database queries.

## Self-Check: PASSED
