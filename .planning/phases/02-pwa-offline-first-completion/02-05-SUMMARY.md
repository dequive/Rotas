---
phase: 02-pwa-offline-first-completion
plan: "05"
subsystem: driver-pwa
tags:
  - service-worker
  - workbox
  - pwa
  - background-sync
  - vite-plugin-pwa
dependency_graph:
  requires:
    - 02-02
    - 02-03
    - 02-04
  provides:
    - apps/driver/src/sw.ts (PWA service worker with precaching + background sync)
    - apps/driver/vite.config.mjs (VitePWA injectManifest build pipeline)
    - apps/driver/src/main.tsx (Workbox registration with sw-update-available dispatch)
  affects:
    - PWA-01
    - PWA-03
tech_stack:
  added:
    - vite-plugin-pwa@1.3.0 (devDependency — Vite build plugin for PWA output)
    - workbox-window@7.4.1 (devDependency — SW registration lifecycle management)
    - workbox-build@7.4.1 (devDependency — manifest injection at build time)
    - workbox-precaching@7.4.1 (runtime — precacheAndRoute in sw.ts)
    - workbox-routing@7.4.1 (runtime — registerRoute in sw.ts)
    - workbox-strategies@7.4.1 (runtime — NetworkFirst, CacheFirst in sw.ts)
    - workbox-background-sync@7.4.1 (runtime — BackgroundSyncPlugin for rotas-sync-queue)
    - workbox-core@7.4.1 (runtime — clientsClaim in sw.ts)
  patterns:
    - injectManifest strategy — sw.ts is authored source compiled and injected with precache manifest by vite-plugin-pwa
    - prompt registerType — driver controls SW activation via SKIP_WAITING message; never unconditional skipWaiting
    - Cache-Control: no-store on SW file — enforced in dev server headers; production Vercel header required separately
    - BackgroundSyncPlugin on POST /api/v1/sync/batch — second-tier retry for when fetch throws (fully offline)
    - NetworkFirst for GET /api/v1/* (10s timeout) — stale financial data is worse than no data
    - CacheFirst for static assets (content-hashed, never stale)
key_files:
  created:
    - apps/driver/src/sw.ts
    - apps/driver/package.json
    - apps/driver/vite.config.mjs
    - apps/driver/tsconfig.json
    - apps/driver/src/main.tsx
  modified: []
decisions:
  - "registerType: prompt not autoUpdate — autoUpdate calls skipWaiting unconditionally and would reload mid-trip"
  - "BackgroundSyncPlugin handles fetch exceptions only (fully offline); Dexie syncQueue handles HTTP 4xx/5xx retries"
  - "Cache-Control: no-store in vite server headers — a cached broken SW is unrecoverable on low-cost Android"
  - "sw-update-available CustomEvent dispatched from main.tsx — SyncStatusBanner useSyncStatus hook listens for this"
metrics:
  duration: "< 5m"
  completed_date: "2026-06-05"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 0
---

# Phase 02 Plan 05: Service Worker + PWA Build Pipeline Summary

**One-liner:** Workbox injectManifest service worker with network-first API caching and BackgroundSync retry for POST /api/v1/sync/batch, registered via workbox-window with prompt-for-update lifecycle control.

---

## What Was Built

The PWA service worker layer for the ROTAS Motorista driver app. Before this plan, the app had Dexie-based offline storage and sync logic but no service worker — meaning it was not installable and background sync (retrying failed POSTs when connectivity returns) did not work.

**Task 1: PWA build infrastructure**
- `vite-plugin-pwa@1.3.0` added to devDependencies with `injectManifest` strategy pointing at `src/sw.ts`
- `vite.config.mjs` updated: VitePWA plugin with `registerType: "prompt"`, `injectRegister: false`, `devOptions.enabled: true`, and `Cache-Control: no-store` in dev server headers
- `tsconfig.json` updated: `"WebWorker"` added to `lib` array for `ServiceWorkerGlobalScope` types
- All workbox runtime packages (precaching, routing, strategies, background-sync, core) added as production dependencies

**Task 2: Service worker source and registration**
- `src/sw.ts` created with injectManifest pattern: `precacheAndRoute(self.__WB_MANIFEST)`, `BackgroundSyncPlugin` on `rotas-sync-queue` (24h retention), `NetworkFirst` for all API calls, `CacheFirst` for static assets
- `src/main.tsx` updated: `Workbox` class import from `workbox-window`, registration with `waiting` event listener that dispatches `sw-update-available` CustomEvent for the SyncStatusBanner update button

**Build output:** `npx vite build` succeeds, generates `dist/sw.js` with 4 precached entries (284.73 KiB). TypeScript passes with `tsc --noEmit`.

---

## Deviations from Plan

None — plan executed exactly as written. All target files were already in the final state (implementation done prior to this execution run), verified with a full build + TypeScript check, and committed atomically per task.

---

## Known Stubs

None. The sw.ts is fully wired: `self.__WB_MANIFEST` is injected by vite-plugin-pwa at build time (not a stub — confirmed by `dist/sw.js` containing workbox precache calls). The `sw-update-available` CustomEvent in main.tsx is consumed by the `useSyncStatus` hook implemented in plan 02-03.

---

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1 | bd1b6b4 | feat(02-05): install PWA packages and configure vite-plugin-pwa with injectManifest |
| Task 2 | 68bd477 | feat(02-05): create sw.ts service worker and register via workbox-window in main.tsx |

---

## Self-Check: PASSED

- `apps/driver/src/sw.ts` — FOUND
- `apps/driver/vite.config.mjs` — FOUND
- `apps/driver/src/main.tsx` — FOUND
- `apps/driver/tsconfig.json` — FOUND
- `apps/driver/package.json` — FOUND
- commit bd1b6b4 — FOUND
- commit 68bd477 — FOUND
- `dist/sw.js` generated by build — CONFIRMED
- TypeScript `tsc --noEmit` — PASSED (no errors)
