---
phase: 18-analytics-insurance
plan: "01"
subsystem: backend
tags: [analytics, kpis, redis-cache, dashboard]
key_files:
  modified:
    - backend/app/modules/analytics/service.py
    - backend/app/modules/analytics/router.py
  created:
    - backend/tests/test_analytics_extended.py
metrics:
  completed_date: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 7
  tests_green: 7
---

# Phase 18 Plan 01: Extended Analytics Dashboard KPIs — Summary

## One-liner

Four new KPI query functions composited into `GET /api/v1/analytics/dashboard` with 300-second Redis cache.

## What Was Built

### New service functions (analytics/service.py)

- `get_route_profitability(db, tenant_id, period_start, period_end)` — top-10 routes by avg cost, closed trips only
- `get_contract_margins(db, tenant_id, period_start, period_end)` — gross margin per billing document (revenue - cost), LIMIT 20
- `get_delivery_nps(db, tenant_id, period_start, period_end)` — intact deliveries * 100.0 / total deliveries; 0.0 if no proofs
- `get_top_drivers_by_score(db, tenant_id, period_start, period_end)` — top-5 drivers by trip_count DESC
- `get_analytics_dashboard(db, tenant_id, period_start, period_end, redis=None)` — composes all 4 new + existing `get_fleet_kpis()`; checks Redis cache key `analytics:dashboard:{tenant_id}:{period_start}:{period_end}` (TTL 300s)

### New endpoint (analytics/router.py)

`GET /api/v1/analytics/dashboard?period_start=...&period_end=...` — requires FLEET_READ; injects `redis` from `request.app.state`; returns all 8 top-level keys.

### Tests (test_analytics_extended.py)

7 tests: route_profitability_empty, returns_origin_destination, delivery_nps_all_intact, delivery_nps_mixed, top_drivers_max_5, dashboard_endpoint_returns_all_blocks, dashboard_cross_tenant_isolation. All GREEN.

## Verification

- 7 new tests GREEN + 3 existing analytics tests GREEN (10 total)
- GET /kpis endpoint unchanged — no regression
- ruff: All checks passed
