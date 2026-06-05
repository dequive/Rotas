---
phase: 02-pwa-offline-first-completion
plan: "03"
subsystem: auth
tags: [auth, token-refresh, manager, driver-pwa, offline]
dependency_graph:
  requires: [02-01]
  provides: [AUTH-01, AUTH-02]
  affects: [apps/manager/app/lib/auth.ts, apps/manager/app/lib/api.ts, apps/driver/src/api.ts]
tech_stack:
  added: []
  patterns:
    - "In-memory lock (Promise deduplication) for concurrent token refresh races"
    - "HttpOnly cookie rotation for manager refresh tokens"
    - "localStorage-based refresh token for driver PWA"
    - "401 retry loop with single refresh attempt before propagating error"
key_files:
  created: []
  modified:
    - apps/manager/app/lib/auth.ts
    - apps/manager/app/lib/api.ts
    - apps/driver/src/api.ts
decisions:
  - "Store rotas_refresh_token in HttpOnly cookie (not sessionStorage) on manager — matches existing session cookie security model"
  - "In-memory _refreshPromise lock in driver api.ts prevents token rotation collision on parallel offline-flush requests"
  - "driver-access-revoked and session-expired dispatched as CustomEvents — no immediate Dexie wipe, UI listens and decides"
metrics:
  duration: "8 minutes"
  completed_date: "2026-06-05T11:06:02Z"
  tasks_completed: 2
  files_modified: 3
---

# Phase 02 Plan 03: Silent Token Refresh (AUTH-01 + AUTH-02) Summary

**One-liner:** JWT refresh rotation for manager (HttpOnly cookies + server action) and driver PWA (localStorage + in-memory race lock), enabling sessions that survive the 15-min access token TTL without user-visible logouts.

---

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Manager AUTH-01: store refresh_token cookie, add refreshAccessToken(), 401 retry in apiFetch() | bce91b3 | apps/manager/app/lib/auth.ts, apps/manager/app/lib/api.ts |
| 2 | Driver AUTH-02: pairDevice() stores refresh_token, refreshAccessToken() with lock, 401 retry in request() | 94a690f | apps/driver/src/api.ts |

---

## What Was Built

### Manager (AUTH-01)

**`apps/manager/app/lib/auth.ts`**
- `login()` now includes `refresh_token` in its type assertion and stores it in a separate HttpOnly cookie (`rotas_refresh_token`) with 30-day maxAge
- New exported `refreshAccessToken()` server action: reads the `rotas_refresh_token` cookie, POSTs to `POST /api/v1/auth/refresh`, rotates both cookies on success, deletes the refresh cookie on failure (prevents infinite retry)
- `logout()` now explicitly deletes `rotas_refresh_token`

**`apps/manager/app/lib/api.ts`**
- `apiFetch()` imports `refreshAccessToken` from auth
- On `res.status === 401`: calls `refreshAccessToken()`, if a new token is returned retries the original request once with the refreshed token; if refresh fails, propagates the error (next navigation will trigger `requireSession()` redirect to `/login`)

### Driver PWA (AUTH-02)

**`apps/driver/src/api.ts`**
- `pairDevice()`: response type now includes `refresh_token`; after `setAuth(auth)`, stores `data.refresh_token` in `localStorage['rotas_refresh_token']`
- `clearAuth()`: now removes `rotas_refresh_token` alongside the other session keys
- New `refreshAccessToken()` with module-level `_refreshPromise` lock: concurrent calls reuse the same in-flight Promise (token rotation safety); dispatches `driver-access-revoked` CustomEvent on backend revocation, `session-expired` on expired/absent token; rotates `rotas_refresh_token` in localStorage after successful refresh
- `request()`: on `res.status === 401`, calls `refreshAccessToken()` and retries once with the new token before throwing

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Store refresh_token in HttpOnly cookie (manager) | Matches existing session cookie security model from SEC-04; HttpOnly prevents XSS token theft |
| In-memory _refreshPromise lock (driver) | Token rotation invalidates the old refresh_token on first use — parallel refreshes would cause all-but-first to fail with invalid_refresh_token |
| CustomEvents (not direct logout) on driver refresh failure | Driver may be offline — dispatching an event lets the UI decide (show banner, redirect) without destroying IndexedDB sync queue prematurely |
| Single retry (not loop) on 401 | Prevents infinite loops if the backend returns 401 for reasons other than token expiry |

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None — all wired to real backend endpoints (`POST /api/v1/auth/refresh`).

---

## Verification Results

- `grep -c "rotas_refresh_token" apps/manager/app/lib/auth.ts` → 5 (required: ≥3) PASS
- `grep -c "refreshAccessToken" apps/manager/app/lib/auth.ts` → 1 (required: ≥1) PASS
- `grep -c "refreshAccessToken" apps/manager/app/lib/api.ts` → 3 (required: ≥1) PASS
- `grep -c "status === 401" apps/manager/app/lib/api.ts` → 1 (required: ≥1) PASS
- `grep -c "rotas_refresh_token" apps/driver/src/api.ts` → 5 (required: ≥4) PASS
- `grep -c "_refreshPromise" apps/driver/src/api.ts` → 5 (required: ≥2) PASS
- `grep -c "driver-access-revoked" apps/driver/src/api.ts` → 1 (required: ≥1) PASS
- `grep -c "session-expired" apps/driver/src/api.ts` → 2 (required: ≥1) PASS
- `grep -c "status === 401" apps/driver/src/api.ts` → 1 (required: ≥1) PASS
- TypeScript check manager: 0 errors PASS
- TypeScript check driver: 0 errors PASS
- `python -m pytest tests/test_token_refresh.py -x -q` → 4 passed PASS
- Full regression `python -m pytest -x -q`: 53 passed, 1 pre-existing failure in `test_sync_update.py::test_sync_update_trip_returns_processed` (confirmed pre-existing, not caused by this plan)

---

## Deferred Items

- `tests/test_sync_update.py::test_sync_update_trip_returns_processed` — pre-existing failure (returns `failed` instead of `processed`), not introduced by this plan. Logged to deferred-items for Phase 02 investigation.

---

## Self-Check: PASSED

- `apps/manager/app/lib/auth.ts` — EXISTS
- `apps/manager/app/lib/api.ts` — EXISTS
- `apps/driver/src/api.ts` — EXISTS
- Commit `bce91b3` — EXISTS (git log confirms)
- Commit `94a690f` — EXISTS (git log confirms)
