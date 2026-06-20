---
phase: 13-frontend-completeness
plan: "02"
subsystem: manager-settings
tags: [frontend, settings, user-management, tenant-settings, typescript]
dependency_graph:
  requires: []
  provides: [settings-acessos-wired, settings-preferencias-wired]
  affects: [apps/manager/app/settings]
tech_stack:
  added: []
  patterns:
    - Next.js server actions for POST/PATCH mutations
    - Server component data loading with Promise.all
    - Client component state for multi-tab form interactions
key_files:
  created: []
  modified:
    - apps/manager/app/settings/actions.ts
    - apps/manager/app/settings/page.tsx
    - apps/manager/app/settings/SettingsClient.tsx
decisions:
  - "StatusBadge used with label override for driver statuses (active/inactive/suspended) since StatusBadge keys use Portuguese (activo/inactivo) but API returns English values"
  - "WhatsApp field initialises empty (not pre-populated from tenant data) because GET /tenants/me does not return whatsapp_number in its current response shape"
  - "Role-change select disabled for the logged-in user's own row to prevent self-demotion"
  - "Invite form restricted to owner/admin roles via userRole prop check"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  files_modified: 3
---

# Phase 13 Plan 02: Settings Page Wiring Summary

JWT auth with refresh rotation using jose library — **Wire /settings page: replace Em breve stubs in Acessos (user management) and Preferências (tenant settings + driver roster) tabs with real functionality.**

## What Was Built

Three-file change set that replaces the "Em breve" placeholder stubs in `/settings` with fully wired UI:

**actions.ts** — Three new server actions added alongside existing `updateUserProfile`:
- `inviteUser` — POST /api/v1/users (email, full_name, role, phone?)
- `changeUserRole` — PATCH /api/v1/users/{id} with `{ role }` only
- `updateTenantSettings` — PATCH /api/v1/tenants/me with timezone/currency/whatsapp_number

**page.tsx** — Server component updated to load four data sources in parallel:
- `getTenantLimits()` (existing)
- `getUsers()` (existing)
- `getTenant()` — new, GET /api/v1/tenants/me
- `getDrivers()` — new, GET /api/v1/drivers?limit=100
- Passes `users`, `tenant`, `drivers` as new props to SettingsClient

**SettingsClient.tsx** — Client component rewritten with full tab implementations:
- Perfil tab: unchanged
- Acessos tab: user list with inline role-change select (disabled for own row), invite form (visible to owner/admin only) with success/error banners
- Preferências tab: tenant settings form (timezone, currency, WhatsApp) wired to PATCH /tenants/me, driver roster table with StatusBadge per driver

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | b955a3c | Add inviteUser, changeUserRole, updateTenantSettings server actions |
| 2 | 4744243 | Load tenant and drivers in settings page for server-side props |
| 3 | 055d2e5 | Wire Acessos and Preferencias tabs in SettingsClient |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all three tabs are fully wired to real backend endpoints. The driver roster reads live data from GET /api/v1/drivers. The tenant form saves to PATCH /api/v1/tenants/me. The user list and invite form call /api/v1/users.

## Self-Check: PASSED

- `apps/manager/app/settings/actions.ts` — exports 4 functions: updateUserProfile, inviteUser, changeUserRole, updateTenantSettings
- `apps/manager/app/settings/page.tsx` — loads limits/users/tenant/drivers in parallel Promise.all
- `apps/manager/app/settings/SettingsClient.tsx` — no "Em breve" strings found
- TypeScript: `cd apps/manager && npx tsc --noEmit` — 0 errors
- Commits b955a3c, 4744243, 055d2e5 verified in git log
