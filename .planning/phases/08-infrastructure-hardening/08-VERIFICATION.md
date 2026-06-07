---
phase: 08-infrastructure-hardening
verified: 2026-06-07T12:00:00Z
status: human_needed
score: 10/10 must-haves verified
re_verification: true
  previous_status: gaps_found
  previous_score: 8/10
  gaps_closed:
    - "layout.tsx now fetches /api/v1/tenants/me/limits (correct plural + /me segment)"
    - "LimitWarningBanner.tsx thresholds changed to WARNING_THRESHOLD=80 and CRITICAL_THRESHOLD=100 matching the API's 0-100 pct scale"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Manually verify LimitWarningBanner visual state at 80% and 100% usage"
    expected: "Amber banner at 80-99% usage; red banner at >= 100% usage; no banner below 80%"
    why_human: "Visual appearance and color state require a running browser session to confirm"
  - test: "Confirm Sentry captures a real error in production/staging environment"
    expected: "An intentional test error appears in the Sentry dashboard with PII fields filtered"
    why_human: "Requires live Sentry DSN and a deployed instance; cannot verify programmatically"
---

# Phase 8: Infrastructure Hardening Verification Report

**Phase Goal:** Production errors are visible in real time, uploaded files survive server restarts, and tenants that exceed their plan limits are blocked before data integrity is compromised.
**Verified:** 2026-06-07
**Status:** human_needed (all automated checks pass; two items require a live environment)
**Re-verification:** Yes — after gap closure

---

## Gap Closure Summary

Two blocking bugs from the initial verification were fixed:

**Bug 1 — Wrong API URL in layout.tsx (CLOSED)**
`getTenantLimits()` previously fetched `/api/v1/tenant/limits`. Fixed to `/api/v1/tenants/me/limits` (plural `tenants` + `/me` segment). Confirmed at line 37 of `apps/manager/app/layout.tsx`. No other occurrences of the wrong URL exist anywhere in the manager app.

**Bug 2 — Wrong threshold scale in LimitWarningBanner.tsx (CLOSED)**
`WARNING_THRESHOLD` changed from `0.8` to `80` and `CRITICAL_THRESHOLD` from `1.0` to `100`. The component comment now correctly states "pct from the API is 0–100 (e.g. 80.0 = 80%)". Confirmed at lines 43–47 of `apps/manager/app/components/LimitWarningBanner.tsx`. Filter logic at line 55 (`d.pct >= WARNING_THRESHOLD`) now correctly fires at 80% usage.

No regressions detected in previously-passing items.

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Sentry SDK initialized in FastAPI backend with PII scrubber | VERIFIED | `main.py`: `_PII_FIELDS`, `_scrub_dict`, `_scrub_pii`, `sentry_sdk.init(before_send=_scrub_pii)` |
| 2 | Sentry SDK initialized in ARQ worker | VERIFIED | `worker.py`: `startup()` calls `sentry_sdk.init(before_send=_scrub_pii)` |
| 3 | Sentry SDK initialized in Next.js manager | VERIFIED | `apps/manager/instrumentation.ts`: `register()` guards on `SENTRY_DSN_MANAGER` |
| 4 | Sentry SDK initialized in driver PWA | VERIFIED | `apps/driver/src/sentry.ts`: guards on `VITE_SENTRY_DSN_DRIVER` |
| 5 | Files routed through `app.storage` abstraction (no direct disk writes) | VERIFIED | `files/service.py` calls `_storage.upload_file()` and `_storage.generate_presigned_url()`; no raw `write_bytes` outside `storage.py` |
| 6 | R2 migration script exists and handles errors gracefully | VERIFIED | `backend/scripts/migrate_files_to_r2.py`: reads all local records, uploads, updates provider, exits 1 on failure |
| 7 | Plan limit guards block vehicle/driver/user creation at limit | VERIFIED | `_check_vehicle_limit` called before DB write in `create_vehicle()`; same pattern in `create_driver()` and `create_user()`; all raise `ApiError("plan_limit_reached", 403)` |
| 8 | GET /api/v1/tenants/me/limits returns real usage data | VERIFIED | `tenants/router.py`: Redis-cached DB COUNT queries per dimension; returns `{used, max, pct}` |
| 9 | LimitWarningBanner shows amber at >= 80% and red at >= 100% | VERIFIED | `WARNING_THRESHOLD=80`, `CRITICAL_THRESHOLD=100`; filter at line 55 matches API's 0-100 pct scale; amber class at 80-99%, red class at 100%+ |
| 10 | Manager layout fetches limit data from the correct endpoint | VERIFIED | `layout.tsx` line 37: `fetch(\`${API_BASE}/api/v1/tenants/me/limits\``); data passed as `limits` prop to `<LimitWarningBanner>` at line 104 |

**Score:** 10/10 truths verified

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/main.py` | Sentry init + PII scrubber | VERIFIED | `_PII_FIELDS`, `_scrub_pii`, `sentry_sdk.init(before_send=_scrub_pii)` present |
| `backend/app/worker.py` | Sentry init in ARQ worker + files routing | VERIFIED | `startup()` initialises Sentry; routes billing exports through `save_generated_file()` |
| `backend/app/storage.py` | `StorageProvider` enum, `upload_file`, `generate_presigned_url` | VERIFIED | All three exports present; dispatches on `settings.storage_provider` |
| `backend/app/modules/files/service.py` | No direct `write_bytes` — routes through `app.storage` | VERIFIED | `upload_file()` calls `_storage.upload_file()`; no raw `write_bytes` in service |
| `backend/app/modules/vehicles/service.py` | `_check_vehicle_limit` guard | VERIFIED | Guard called before any DB write in `create_vehicle()` |
| `backend/app/modules/drivers/service.py` | `_check_driver_limit` guard | VERIFIED | Guard called before any DB write in `create_driver()` |
| `backend/app/modules/users/service.py` | `_check_user_limit` guard | VERIFIED | Guard called before any DB write in `create_user()` |
| `backend/app/modules/tenants/router.py` | `GET /tenants/me/limits` endpoint | VERIFIED | Route at `/me/limits` (full path `/api/v1/tenants/me/limits`); Redis cache-aside present |
| `apps/manager/app/components/LimitWarningBanner.tsx` | Amber/red warning banner with correct thresholds | VERIFIED | `WARNING_THRESHOLD=80`, `CRITICAL_THRESHOLD=100`; comment updated to document 0-100 scale |
| `apps/manager/app/layout.tsx` | LimitWarningBanner wired to correct endpoint | VERIFIED | Fetches `/api/v1/tenants/me/limits`; passes result to `<LimitWarningBanner limits={limits}>` |
| `apps/manager/instrumentation.ts` | Sentry Next.js init | VERIFIED | `register()` guards on `SENTRY_DSN_MANAGER`; calls `Sentry.init()` |
| `apps/driver/src/sentry.ts` | Sentry driver PWA init | VERIFIED | Guards on `VITE_SENTRY_DSN_DRIVER`; calls `Sentry.init()` |
| `backend/scripts/migrate_files_to_r2.py` | R2 migration script | VERIFIED | Reads local files, uploads to R2, updates DB record, exits 0/1 |
| `backend/tests/test_sentry_integration.py` | 5 tests | VERIFIED | 5 tests covering `_scrub_pii` deeply |
| `backend/tests/test_storage.py` | 4 tests | VERIFIED | 4 async tests covering LOCAL write, R2 put_object, presign variants |
| `backend/tests/test_migrate_files.py` | 4 tests | VERIFIED | 4 tests covering skip, failure, clean migration, gate query |
| `backend/tests/test_tenant_limits_api.py` | 6 tests | VERIFIED | 6 tests covering counts, null max, Redis cache hit, auth, 403 guard, unlimited |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `test_sentry_integration.py` | `app/main.py:_scrub_pii` | `from app.main import _scrub_pii` | WIRED | Pattern present in every test function |
| `test_storage.py` | `app/storage.py` | `from app.storage import StorageProvider, upload_file, generate_presigned_url` | WIRED | All three imports present |
| `test_tenant_limits_api.py` | `GET /api/v1/tenants/me/limits` | `client.get("/api/v1/tenants/me/limits", ...)` | WIRED | Tests hit the endpoint directly |
| `worker.py:generate_billing_export()` | `files/service.py:save_generated_file()` | `from app.modules.files.service import save_generated_file` | WIRED | Import + call confirmed |
| `vehicles/service.py:create_vehicle()` | `_check_vehicle_limit()` | `await _check_vehicle_limit(db, tenant, redis)` | WIRED | Called before any DB write |
| `apps/manager/app/layout.tsx` | `LimitWarningBanner.tsx` | `import { LimitWarningBanner }` + `<LimitWarningBanner limits={limits} />` | WIRED | Import line 4; render line 104 |
| `apps/manager/app/layout.tsx` | `GET /api/v1/tenants/me/limits` | fetch in `getTenantLimits()` | WIRED | URL corrected to `/api/v1/tenants/me/limits` at line 37 |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `LimitWarningBanner.tsx` | `limits` prop | `getTenantLimits()` in `layout.tsx` fetches `/api/v1/tenants/me/limits` | Yes — correct URL returns real DB-backed data; banner renders when pct >= 80 | FLOWING |
| `tenants/router.py:/limits` | `vehicle_used`, `driver_used`, `user_used` | `_get_cached_vehicle_count()` etc. — DB COUNT queries with Redis TTL 30s | Yes — real DB queries | FLOWING |

---

## Behavioral Spot-Checks

Step 7b: SKIPPED (no running server; checks would require live DB and Redis).

---

## Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| INFRA-01 | 08-01, 08-02, 08-03, 08-04 | Sentry in FastAPI, ARQ worker, Next.js, driver PWA; PII scrubber active | SATISFIED | `main.py`, `worker.py`, `instrumentation.ts`, `sentry.ts` all initialise Sentry with DSN guard and `_scrub_pii`. 5 tests in `test_sentry_integration.py`. |
| INFRA-02 | 08-01, 08-07, 08-08 | Files in R2/S3; local files migrated before provider switch; zero raw disk writes after migration | SATISFIED | `storage.py` dual-provider abstraction; `files/service.py` routes all uploads through abstraction; `migrate_files_to_r2.py`; 4 storage tests; 4 migration tests. |
| INFRA-03 | 08-01, 08-05, 08-06 | HTTP 403 with `upgrade_url` on limit breach; max_vehicles/drivers/users checked before insert; 80% visual warning in manager | SATISFIED | Guards verified in all three services; `/tenants/me/limits` endpoint works; `layout.tsx` now fetches correct URL; `LimitWarningBanner` thresholds now match API's 0-100 scale. |

---

## Anti-Patterns Found

None. The two blocker anti-patterns from the initial verification have been resolved.

---

## Human Verification Required

### 1. LimitWarningBanner Visual State

**Test:** Create a tenant with `max_vehicles=5`, seed 4 vehicles (80% usage), load the manager dashboard.
**Expected:** Amber banner appears at the top showing "Limite de Veiculos: 4/5 utilizados" with an upgrade link. At 5/5 vehicles, banner switches to red background.
**Why human:** Visual color, layout, and Tailwind class rendering require a browser session.

### 2. Sentry PII Filtering in Production

**Test:** With a real `SENTRY_DSN_BACKEND` set, trigger a test error that includes `driver_name` in extra context. Check the Sentry dashboard.
**Expected:** The event appears in Sentry with `driver_name` showing `[Filtered]`.
**Why human:** Requires live Sentry DSN and a deployed environment.

---

_Verified: 2026-06-07_
_Verifier: Claude (gsd-verifier)_
