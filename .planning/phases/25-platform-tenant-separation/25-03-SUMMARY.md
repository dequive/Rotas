---
phase: 25-platform-tenant-separation
plan: "03"
subsystem: backend/platform
tags: [platform, rbac, tenants, guard, multitenancy, security]
requirements: [PLAT-07, PLAT-08]

dependency_graph:
  requires:
    - "25-01: PlatformUser models, require_platform_role(), platform auth"
    - "25-02: Platform management API endpoints, get_session_raw pattern"
  provides:
    - "require_own_tenant_or_platform() combined RBAC guard in rbac.py"
    - "GET /api/v1/tenants/me?tenant_id= accessible to platform_admin"
    - "PATCH /api/v1/tenants/me?tenant_id= accessible to platform_admin"
    - "GET/PUT /api/v1/tenants/me/driver-despacho-table?tenant_id= accessible to platform_admin"
    - "8 isolation tests covering scope separation and combined guard"
  affects:
    - "backend/app/modules/tenants/router.py (four /me routes restructured)"
    - "backend/app/core/rbac.py (new combined guard function)"

tech_stack:
  added: []
  patterns:
    - "JWT scope peeking (base64 decode without crypto verify) to choose auth path in combined guard"
    - "Singleton _combined_guard = require_own_tenant_or_platform() at module level for FastAPI dedup"
    - "Inline AsyncSessionLocal() in combined-guard routes avoids double get_current_principal() call"
    - "set_rls_tenant() called in route handler (not via get_session dependency) for tenant path"

key_files:
  created: []
  modified:
    - backend/app/core/rbac.py
    - backend/app/modules/tenants/router.py
    - backend/tests/test_platform_scope_isolation.py

decisions:
  - "Use JWT scope peeking (base64 decode, no crypto) to choose platform vs tenant auth path — full cryptographic validation still happens inside the delegated function (no security shortcut)"
  - "Singleton _combined_guard at module level so FastAPI dependency deduplication cache recognises the same callable across the four /me routes — avoids double auth evaluation per request"
  - "Combined-guard routes open AsyncSessionLocal directly instead of using Depends(get_session) — get_session from core.deps has get_current_principal baked in as sub-dependency which fails for platform tokens (platform JWT has no tenant_id claim)"
  - "platform_support and platform_billing rejected at /tenants/me endpoints with 403 — they already have read access via /platform/tenants/{id}; duplicating write access would violate least-privilege"
  - "/tenants/me/limits stays on require_permission(ADMIN_USERS) + Depends(get_session) — tenant-only endpoint, platform admin uses /platform/tenants/{id} for equivalent data"

metrics:
  duration_seconds: 900
  completed_date: "2026-06-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 0
  files_modified: 3
  tests_added: 2
  tests_total: 373
---

# Phase 25 Plan 03: Combined Guard + Tenant Router Wiring Summary

**One-liner:** require_own_tenant_or_platform() combined guard wired to four /tenants/me routes, letting platform_admin inspect any tenant via ?tenant_id= query param while preserving existing tenant-admin behaviour.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Combined guard + tenants/router.py wired | cbbab3f | rbac.py, tenants/router.py |
| 2 | 2 isolation tests + ruff clean | e04ed3b | test_platform_scope_isolation.py |

## What Was Built

### Combined Guard (`backend/app/core/rbac.py`)

`require_own_tenant_or_platform(tenant_permission=ADMIN_USERS)` — a FastAPI dependency factory that:

1. Reads `Authorization` header from `Request` object (not `Header()` annotations, which fail inside closure-returned dependencies).
2. Base64-decodes the JWT payload to peek at the `scope` claim (no crypto — full validation is delegated).
3. **Platform path** (`scope="platform"`): calls `get_current_platform_principal()`, then enforces `role == PLATFORM_ADMIN`. Other platform roles (support, billing) get 403 with a message directing them to `/platform/tenants/{id}`.
4. **Tenant path** (any other scope): calls `get_current_principal()`, then checks `has_any_permission({tenant_permission})`. Missing permission → 403.

### Router Wiring (`backend/app/modules/tenants/router.py`)

Four routes updated: `GET /me`, `PATCH /me`, `GET /me/driver-despacho-table`, `PUT /me/driver-despacho-table`.

Key structural change: the routes no longer use `Depends(get_session)` — the `get_session` from `app.core.deps` has `get_current_principal` baked in as a sub-dependency, which would be called a second time for platform tokens and fail (platform JWT has no `tenant_id` claim → `invalid_token` 401).

Instead, the routes:
- Accept `principal` from the shared `_combined_guard` singleton.
- Call `set_rls_tenant(str(effective_tenant_id))` directly when the scope is dashboard.
- Open `AsyncSessionLocal()` inline, passing the session to the service layer.
- Call `set_rls_tenant(None)` in a `finally` block to clean up.

The `_combined_guard` singleton is defined at module level so FastAPI's dependency deduplication cache treats it as the same callable across all four routes within a single request.

`/tenants/me/limits` is unchanged — it uses `require_permission(ADMIN_USERS)` and `Depends(get_session)` (tenant-only, no platform path needed).

### Isolation Tests (8 total — `backend/tests/test_platform_scope_isolation.py`)

Two tests added (tests 7 and 8):

- `test_platform_admin_can_access_tenant_me_with_query_param`: creates a real tenant + platform_admin user, logs in via `/platform/auth/login`, calls `GET /api/v1/tenants/me?tenant_id={uuid}` — asserts 200 and `"id"` in response matching the tenant UUID.
- `test_platform_support_cannot_access_tenant_me`: same setup with platform_support role — asserts 403 with `error.code == "forbidden"`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `get_session` double-invokes `get_current_principal` for platform tokens**
- **Found during:** Task 1 verification (test_platform_admin_can_access_tenant_me_with_query_param failing with 401 `invalid_token`)
- **Issue:** `app.core.deps.get_session` has `Depends(get_current_principal)` baked in as a sub-dependency. When a platform token reaches `GET /tenants/me`, FastAPI resolves `get_session`'s sub-dependency independently — it calls `get_current_principal` with the platform JWT, which fails because the platform JWT has no `tenant_id` claim.
- **Fix:** Replaced `Depends(get_session)` on the four combined-guard routes with inline `AsyncSessionLocal()` + `set_rls_tenant()` called directly in the handler. Kept `_combined_guard` as a module-level singleton so FastAPI deduplicates the guard across routes in the same request.
- **Files modified:** `backend/app/modules/tenants/router.py`
- **Commit:** cbbab3f

## Verification Results

```
backend $ python -m pytest tests/test_platform_scope_isolation.py -v
8 passed in 6.05s

backend $ python -m pytest tests/ -x --tb=short -q --ignore=tests/test_rate_limiting.py
373 passed, 2 skipped in 183.60s

backend $ python -m ruff check app/core/auth.py app/core/tokens.py app/core/rbac.py \
    app/modules/platform/ app/modules/tenants/router.py
All checks passed!

python -c "from app.main import app; ..."
all expected routes present
```

## Security Invariants Confirmed

- `platform_admin` JWT → GET /tenants/me?tenant_id= → 200 (combined guard platform path)
- `platform_support` JWT → GET /tenants/me?tenant_id= → 403 (combined guard rejects non-admin)
- `platform_billing` JWT → GET /tenants/me?tenant_id= → 403 (combined guard rejects non-admin)
- tenant `admin` JWT → GET /tenants/me → 200 (existing behaviour unchanged)
- tenant `viewer` JWT → GET /tenants/me → 403 (lacks admin.users permission)
- Platform JWT → GET /api/v1/trips → 401/403 (platform scope rejected by tenant endpoints — existing)

## Known Stubs

None — all combined-guard endpoints are fully wired with auth, session management, and service logic.

## Self-Check: PASSED
