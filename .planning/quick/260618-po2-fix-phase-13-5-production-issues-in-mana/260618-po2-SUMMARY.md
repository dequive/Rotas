---
phase: quick
plan: 260618-po2
subsystem: manager-frontend
tags: [bugfix, auth, settings, alerts, workshop, kpi]
key-files:
  created:
    - apps/manager/app/settings/actions.ts
    - apps/manager/app/manutencao/error.tsx
    - apps/manager/app/alertas/error.tsx
  modified:
    - apps/manager/app/alertas/AlertsClient.tsx
    - apps/manager/app/alertas/page.tsx
    - apps/manager/app/settings/SettingsClient.tsx
    - apps/manager/app/settings/page.tsx
    - apps/manager/app/lib/workshop-api.ts
    - apps/manager/app/lib/alerts-api.ts
    - apps/manager/app/manutencao/page.tsx
decisions:
  - "Settings profile update uses Server Action (actions.ts) — apiFetch requires server context (reads HttpOnly cookies); raw client fetch cannot access them"
  - "Error boundaries added for manutencao and alertas — loadAlerts/loadWorkOrders now throw instead of returning [], so Next.js error.tsx catches failures visually"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-18"
  tasks: 3
  files: 10
---

# Quick Task 260618-po2: Fix Phase 13.5 Production Issues in Manager

**One-liner:** Fixed 8 confirmed production bugs — unauthenticated raw fetch calls replaced with apiFetch/Server Actions, hardcoded test email removed, KPI counts deduplicated, and API errors now surface via error boundaries instead of silent empty arrays.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Fix critical auth header bugs and NEXT_PUBLIC env var misuse | 6a9e18b | AlertsClient.tsx, alertas/page.tsx, settings/actions.ts, SettingsClient.tsx |
| 2 | Fix silent error swallowing and workshop data accuracy | dff234a | workshop-api.ts, alerts-api.ts, manutencao/page.tsx, error.tsx x2 |
| 3 | Fix hardcoded email fallback and misleading stub tabs | 8b5c000 | settings/page.tsx, SettingsClient.tsx |

## Bugs Fixed

### Bug 1 — AlertsClient.tsx: raw fetch() with no auth headers
`handleResolveAlert` called `fetch(/api/v1/alerts/${alertId}/status)` with no `Authorization` or `X-Tenant-Id` headers. Replaced with `updateAlertStatus(alertId, "resolved")` from `alerts-api.ts` which uses `apiFetch` (server-side with proper headers injected from HttpOnly cookies).

### Bug 2 — SettingsClient.tsx: raw fetch() with no auth headers
`handleSaveProfile` called raw `fetch(/api/v1/users/${userId})` from a client component — cannot access HttpOnly cookies. Created `settings/actions.ts` with `"use server"` directive, implemented `updateUserProfile` using `apiFetch`. SettingsClient now calls the server action.

### Bug 3 — alertas/page.tsx: NEXT_PUBLIC_API_URL and manual cookie reading
`getDocumentExpiry` used `process.env.NEXT_PUBLIC_API_URL` (wrong env var category for a server component) and manually read `cookies()` to build auth headers. Replaced with `apiFetch<ExpiryAlert[]>(...)` which handles both transparently. Removed `cookies` and `NEXT_PUBLIC_API_URL` completely.

### Bug 4 — Silent error swallowing in workshop-api.ts and alerts-api.ts
`loadWorkOrders`, `loadMaintenanceRequests`, and `loadAlerts` all had `try/catch { return [] }` that silently hid backend failures. Removed the catch blocks so errors propagate to Next.js error boundaries. Added `error.tsx` files for both `manutencao/` and `alertas/` routes.

### Bug 5 — Viaturas em Oficina KPI counted orders not unique vehicles
`inProgressOrders = workOrders.filter(wo => wo.status === "in_progress").length` counted work orders. If one vehicle had 3 active work orders, it counted as 3. Fixed to `new Set(...map(wo => wo.vehicle_id)).size`.

### Bug 6 — workshop-api.ts limit=100 truncates large fleets
`loadWorkOrders` and `loadMaintenanceRequests` used `limit=100`. Increased to `limit=500` (combined with Bug 4 fix).

### Bug 7 — Hardcoded fallback email `admin@tms.com` in settings/page.tsx
`initialEmail={currentUser?.email ?? "admin@tms.com"}` would populate the profile form with a test address if the user was not found in the users list. Changed fallback to `""`. The `required` attribute on the email input prevents saving an empty value. Also removed the unused `cookies` import.

### Bug 8 — Stub tabs showing misleading placeholder text
"Gestão de Acessos" and "Preferências" tabs showed descriptive text implying the features existed. Replaced with dashed-border coming-soon containers (icon + "Em breve" + context sentence), consistent with DESIGN.md minimal decoration guidelines.

## Deviations from Plan

None — plan executed exactly as written. The unused `cookies` import removal in `settings/page.tsx` was applied as a Rule 2 auto-fix (would have caused a TypeScript hint and is a pre-existing issue introduced by the main bug fix).

## Known Stubs

None — all bugs are fully fixed. The "Em breve" tabs are intentional coming-soon states, not stubs that block this plan's goal.

## Self-Check: PASSED

- `apps/manager/app/settings/actions.ts` — exists, `"use server"` on line 1
- `apps/manager/app/manutencao/error.tsx` — exists
- `apps/manager/app/alertas/error.tsx` — exists
- `admin@tms.com` — 0 matches in `apps/manager/app/`
- `fetch(` in AlertsClient.tsx — 0 matches
- `fetch(` in SettingsClient.tsx — 0 matches
- `new Set(` in manutencao/page.tsx — 1 match (line 40)
- `try {` in workshop-api.ts — 0 matches
- TypeScript: `tsc --noEmit` exits 0 (clean)
- Commits: 6a9e18b, dff234a, 8b5c000 — all verified in git log
