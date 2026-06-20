---
phase: 25-platform-tenant-separation
plan: "02"
subsystem: backend/platform
tags: [platform, rbac, api, tenants, audit, multitenancy, security]
requirements: [PLAT-04, PLAT-05, PLAT-06]

dependency_graph:
  requires:
    - "25-01: PlatformUser/PlatformAuditLog models, require_platform_role(), POST /platform/auth/login"
  provides:
    - "GET /api/v1/platform/tenants — cross-tenant list (admin, support, billing)"
    - "GET /api/v1/platform/tenants/{id} — tenant detail with support read-audit"
    - "PATCH /api/v1/platform/tenants/{id}/plan — plan change (admin only)"
    - "POST /api/v1/platform/tenants/{id}/suspend — suspend tenant (admin only)"
    - "POST /api/v1/platform/tenants/{id}/reactivate — reactivate tenant (admin only)"
    - "GET /api/v1/platform/tenants/{id}/audit-log — audit log (admin, support)"
    - "GET /api/v1/platform/platform-users — list platform users (admin only)"
    - "POST /api/v1/platform/platform-users — create platform user (admin only)"
  affects:
    - "backend/app/main.py (platform_router registered)"
    - "backend/app/modules/platform/schemas.py (two new request models)"

tech_stack:
  added: []
  patterns:
    - "SET LOCAL row_security = off for cross-tenant list scan (requires DB owner or BYPASSRLS)"
    - "SET LOCAL app.tenant_id = '{id}' before single-tenant reads through Tenant RLS"
    - "record_platform_audit() inside same session before db.commit() — atomic audit+mutation"
    - "get_session_raw (no RLS injection) for platform router — platform ops span all tenants"
    - "require_platform_role() Depends()-only RBAC guard on every endpoint"

key_files:
  created:
    - backend/app/modules/platform/service.py
    - backend/app/modules/platform/router.py
    - backend/tests/test_platform_management_api.py
  modified:
    - backend/app/modules/platform/schemas.py
    - backend/app/main.py

decisions:
  - "Use SET LOCAL row_security = off for list_tenants cross-tenant scan — requires DB owner in dev/test; production needs BYPASSRLS grant on tenants table for rotas_app"
  - "Use get_session_raw (not get_session from core.deps) for platform router — RLS injection is meaningless/harmful for cross-tenant platform operations"
  - "platform_support GET /tenants/{id} logs a platform_audit_logs row — cross-tenant reads by support staff are audited"
  - "GET /audit-log restricted to admin + support (not billing) — billing has no operational reason to see support activity logs"
  - "POST /platform-users returns 201 (not 200) — resource creation status code"

metrics:
  duration_seconds: 1200
  completed_date: "2026-06-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 2
  tests_added: 8
  tests_total: 373
---

# Phase 25 Plan 02: Platform Management API Summary

**One-liner:** 8 platform management endpoints (tenant list/suspend/reactivate/plan-change, audit log, platform-user CRUD) with atomic audit trail and role-gated access using SET LOCAL RLS bypass pattern.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Platform service layer | 628e657 | service.py, schemas.py |
| 2 | Platform router + 8 tests | b92b297, 276dd70 | router.py, main.py, test_platform_management_api.py |

## What Was Built

### Service Layer (`backend/app/modules/platform/service.py`)

8 public functions, all accepting `db: AsyncSession` as first param:

- `list_tenants()` — `SET LOCAL row_security = off` then `SELECT * FROM tenants ORDER BY created_at`. Cross-tenant scan requires the DB role to own the schema (dev) or have BYPASSRLS (prod).
- `get_tenant_detail()` — `SET LOCAL app.tenant_id = '{id}'` before the Tenant query. When `actor_role == PLATFORM_SUPPORT`, appends a `tenant.read` row to `platform_audit_logs` inside the same session and commits.
- `suspend_tenant()` / `reactivate_tenant()` — raises 409 if state already matches; sets `is_active`; calls `record_platform_audit()` before `db.commit()`.
- `change_tenant_plan()` — captures `old_plan`, sets `tenant.plan = new_plan`, records `tenant.plan_changed` audit with payload `{old_plan, new_plan}`, commits.
- `list_platform_audit_log()` — `WHERE target_tenant_id = ? ORDER BY timestamp DESC LIMIT/OFFSET`.
- `list_platform_users()` — all PlatformUser rows ordered by `created_at`.
- `create_platform_user()` — duplicate email check (409), `hash_password()`, `record_platform_audit()` with `action="platform_user.created"`, commits.

Private helpers: `_require_tenant()` (SET LOCAL + 404 guard), `_set_tenant_ctx()`, `_serialize_tenant()`, `_serialize_platform_user()`, `_serialize_audit_log()`.

### Router (`backend/app/modules/platform/router.py`)

```
GET    /api/v1/platform/tenants                    — admin, support, billing
GET    /api/v1/platform/tenants/{id}               — admin, support, billing
PATCH  /api/v1/platform/tenants/{id}/plan          — admin only
POST   /api/v1/platform/tenants/{id}/suspend       — admin only
POST   /api/v1/platform/tenants/{id}/reactivate    — admin only
GET    /api/v1/platform/tenants/{id}/audit-log     — admin, support
GET    /api/v1/platform/platform-users             — admin only
POST   /api/v1/platform/platform-users             — admin only (201)
```

Uses `get_session_raw` (no RLS injection) — platform operations are inherently cross-tenant; the RLS injection in `app.core.deps.get_session` would set a meaningless single-tenant context.

### Tests (8 GREEN — `backend/tests/test_platform_management_api.py`)

1. `test_platform_admin_can_list_tenants` — creates 2 tenants, verifies both appear in list
2. `test_platform_billing_can_list_tenants` — billing role also gets 200
3. `test_platform_admin_can_suspend_and_reactivate_tenant` — suspend → GET detail shows False → reactivate → True
4. `test_platform_support_cannot_suspend_tenant` — 403
5. `test_platform_billing_cannot_change_plan` — 403
6. `test_platform_admin_can_change_plan` — plan field updated in response
7. `test_platform_support_cannot_list_platform_users` — 403
8. `test_suspend_creates_audit_log_entry` — suspend then GET /audit-log → action="tenant.suspend" present

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `get_session` not exported from `app.database`**
- **Found during:** Task 2 (router import error at app startup)
- **Issue:** Router imported `from app.database import get_session` but `database.py` exports only `get_session_raw`; the RLS-aware `get_session` lives in `app.core.deps` (documented in database.py comments)
- **Fix:** Changed router import to `from app.database import get_session_raw as get_session` — architecturally correct since platform endpoints are cross-tenant and must not inject a tenant RLS context
- **Files modified:** `backend/app/modules/platform/router.py`
- **Commit:** b92b297

**2. [Rule 1 - Bug] Ruff import ordering violation in service.py**
- **Found during:** Post-write ruff check
- **Issue:** Import block had `uuid` after `fastapi`/`sqlalchemy` — ruff I001
- **Fix:** `ruff check --fix` auto-corrected (moved `from uuid import UUID` before third-party imports)
- **Files modified:** `backend/app/modules/platform/service.py`
- **Commit:** included in 628e657

## Verification Results

```
backend $ python -m pytest tests/test_platform_management_api.py -v
8 passed in 12.52s

backend $ python -m pytest tests/test_platform_scope_isolation.py tests/test_platform_management_api.py -v
14 passed in 8.96s

backend $ python -m pytest tests/ -x --tb=short -q
373 passed, 2 skipped in 138.82s

backend $ ruff check app/
All checks passed!

python -c "from app.main import app; platform_paths = [r.path for r in app.routes if '/platform' in getattr(r, 'path', '')]; print(len(platform_paths))"
9
```

## Security Invariants Confirmed

- `platform_support` POST /suspend → 403 (confirmed by test 4)
- `platform_billing` PATCH /plan → 403 (confirmed by test 5)
- `platform_support` GET /platform-users → 403 (confirmed by test 7)
- Every suspension creates an audit log entry (confirmed by test 8)
- Platform tokens still rejected on tenant endpoints (existing test_platform_scope_isolation tests still pass)

## Known Stubs

None — all 8 endpoints are fully wired with service logic, audit trail, and passing tests.

## Self-Check: PASSED
