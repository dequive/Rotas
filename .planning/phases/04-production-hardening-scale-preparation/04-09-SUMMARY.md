---
phase: 04-production-hardening-scale-preparation
plan: 09
subsystem: manager-dashboard
tags: [ui-panels, driver-scorecard, maintenance-alerts, control-tower]
dependency_graph:
  requires: [04-04, 04-02]
  provides: [DriverScorecardPanel, MaintenanceImminentPanel, loadDriverScorecard, loadImminentMaintenanceAlerts]
  affects: [apps/manager/app/motoristas/page.tsx, apps/manager/app/page.tsx]
tech_stack:
  added: []
  patterns: [server-component data fetch + client component, fleet-compliance-panel CSS pattern, transport-kpis grid]
key_files:
  created:
    - apps/manager/app/components/DriverScorecardPanel.tsx
    - apps/manager/app/components/MaintenanceImminentPanel.tsx
  modified:
    - apps/manager/app/lib/drivers-api.ts
    - apps/manager/app/lib/control-tower-api.ts
    - apps/manager/app/motoristas/page.tsx
    - apps/manager/app/page.tsx
    - backend/app/modules/workshop/router.py
decisions:
  - Backend endpoint /api/v1/workshop/imminent-alerts added (service existed but router was missing)
  - useEffect used for initial scorecard load to avoid SSR issues in client component
  - MaintenanceImminentPanel placed after FleetComplianceBoard in Control Tower main section
metrics:
  duration: 15m
  completed: 2026-06-05
  tasks_completed: 2
  files_changed: 7
---

# Phase 04 Plan 09: Driver Scorecard + Maintenance Imminent Panels Summary

Two UI panels integrated into the manager dashboard: driver scorecard with composite score tier badge, and maintenance imminence panel with color-coded trigger markers.

## What Was Built

**DriverScorecardPanel** (`apps/manager/app/components/DriverScorecardPanel.tsx`)
- Client component with driver selector dropdown
- 5 KPI cards: composite score (with tier badge), proof de entrega, disciplina de sync, quilómetros, eficiência de paradas
- Tier badges: Verde (green), Amarelo (orange), Vermelho (red), Dados insuficientes (default)
- Loading skeleton using `--line` CSS var; `useEffect` for initial load; error state
- Portuguese pt-MZ copy throughout (UI-SPEC.md compliant)

**MaintenanceImminentPanel** (`apps/manager/app/components/MaintenanceImminentPanel.tsx`)
- Server-rendered (no "use client") — data passed as props
- Color-coded history markers: orange (calendar), cyan (odometer), red (overdue)
- Empty state: "Sem manutenções iminentes"
- Due date formatted as DD/MM/YYYY; due km formatted with pt-MZ locale

**API helpers added:**
- `loadDriverScorecard(driverId, days)` in `drivers-api.ts` — client-side fetch
- `loadImminentMaintenanceAlerts()` in `control-tower-api.ts` — server-side fetch
- `ScorecardData` and `ImminentAlert` interfaces exported

**Page integrations:**
- `/motoristas` — DriverScorecardPanel rendered below drivers table, receives driver list slimmed to `{id, full_name}`
- Control Tower `/` — imminentAlerts fetched server-side, MaintenanceImminentPanel rendered after FleetComplianceBoard

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing endpoint] Added GET /api/v1/workshop/imminent-alerts backend endpoint**
- **Found during:** Task 1 — plan referenced `/api/v1/maintenance/imminent-alerts` which does not exist
- **Issue:** `get_imminent_maintenance_alerts()` service function existed but had no router binding; workshop router prefix is `/workshop`, not `/maintenance`
- **Fix:** Added `@router.get("/imminent-alerts")` to `backend/app/modules/workshop/router.py`; updated frontend URL to `/api/v1/workshop/imminent-alerts`
- **Files modified:** `backend/app/modules/workshop/router.py`, `apps/manager/app/lib/control-tower-api.ts`
- **Commit:** 05d8725

**2. [Rule 1 - Bug] Replaced placeholder `if` block with proper `useEffect`**
- **Found during:** Task 1 — plan code contained a dead `if (typeof window !== "undefined" && ...)` block that did nothing
- **Fix:** Implemented proper `useEffect` with cancellation flag for the initial scorecard load
- **Files modified:** `apps/manager/app/components/DriverScorecardPanel.tsx`
- **Commit:** 05d8725

## Known Stubs

None — both panels render live data from API endpoints. Empty states are semantic (no data available), not placeholder stubs.

## Self-Check: PASSED

- FOUND: `apps/manager/app/components/DriverScorecardPanel.tsx`
- FOUND: `apps/manager/app/components/MaintenanceImminentPanel.tsx`
- FOUND: commit `05d8725` (Task 1)
- FOUND: commit `3c196d2` (Task 2)
