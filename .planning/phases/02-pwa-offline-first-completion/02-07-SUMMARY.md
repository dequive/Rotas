---
phase: 02-pwa-offline-first-completion
plan: "07"
subsystem: driver-pwa
tags: [pwa, offline, sync, banner, ui]
dependency_graph:
  requires: [02-02, 02-03, 02-04]
  provides: [SyncStatusBanner, useNetworkStatus, useSyncStatus]
  affects: [apps/driver/src/App.tsx]
tech_stack:
  added: []
  patterns: [custom-event-bus, dexie-polling, react-state-machine]
key_files:
  created:
    - apps/driver/src/hooks/useNetworkStatus.ts
    - apps/driver/src/hooks/useSyncStatus.ts
    - apps/driver/src/components/SyncStatusBanner.tsx
  modified:
    - apps/driver/src/styles.css
    - apps/driver/src/App.tsx
decisions:
  - "Banner always mounted, display:none in idle state — prevents layout shift between state transitions"
  - "syncing state from App.tsx syncNow() reused as isSyncing signal — no new state required"
  - "pendingCount/lastMessage state kept in App.tsx for backward compat with FuelPanel.latestStatus"
metrics:
  duration: "2m"
  completed: "2026-06-05"
  tasks: 2
  files: 5
---

# Phase 2 Plan 07: SyncStatusBanner Implementation Summary

SyncStatusBanner with 7-state machine (idle/offline/syncing/error/session_expired/access_revoked/update_available) using useNetworkStatus + useSyncStatus hooks and Dexie syncQueue polling.

---

## What Was Built

The driver PWA now has a persistent ambient status banner replacing the static `.offline-bar` footer. The banner gives drivers real-time feedback about data safety — the core UX requirement for a financial-grade offline-first app.

**Hook: `useNetworkStatus`** — returns `{ isOnline: boolean }` by listening to browser `online`/`offline` events with `navigator.onLine` as initial value.

**Hook: `useSyncStatus`** — aggregates all signals into a single `BannerState` state machine:
- Polls `db.syncQueue` every 5 seconds for `pendingCount` (local_only + retrying) and `errorCount` (conflict)
- Listens for `session-expired`, `driver-access-revoked`, `sw-update-available` custom window events from `api.ts`
- Priority order: `access_revoked > session_expired > offline > syncing > error > update_available > idle`

**Component: `SyncStatusBanner`** — renders correct Portuguese message for all 7 states per UI-SPEC.md copywriting contract. The `update_available` state renders a "Verificar atualizações" button that posts `SKIP_WAITING` to the waiting service worker and reloads the page.

**App.tsx** — replaced `<footer className="offline-bar">` with `<SyncStatusBanner status={syncStatus} />`. Added `useNetworkStatus` and `useSyncStatus` hooks. The existing `syncing` state (from `syncNow()`) is reused as `isSyncing` signal.

**styles.css** — added `.sync-banner` base class + 6 state modifier classes following the existing CSS variable system (no new design tooling).

---

## Deviations from Plan

None - plan executed exactly as written.

---

## Known Stubs

None — all 7 banner states render real data from Dexie queries and live event listeners.

---

## Self-Check

Checking files exist:

- `apps/driver/src/hooks/useNetworkStatus.ts` — FOUND
- `apps/driver/src/hooks/useSyncStatus.ts` — FOUND
- `apps/driver/src/components/SyncStatusBanner.tsx` — FOUND
- Commits `6c15902` and `c2d89e8` — FOUND

## Self-Check: PASSED
