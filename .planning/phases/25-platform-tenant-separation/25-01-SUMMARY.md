---
phase: 25-platform-tenant-separation
plan: "01"
subsystem: backend/core
tags: [auth, jwt, platform, rbac, security, multitenancy]
requirements: [PLAT-01, PLAT-02, PLAT-03]

dependency_graph:
  requires: []
  provides:
    - "scope=platform JWT family (create_access_token with tenant_id=None)"
    - "get_current_platform_principal() — separate platform JWT decoder"
    - "require_platform_role() FastAPI dependency factory"
    - "PLATFORM_ADMIN / PLATFORM_SUPPORT / PLATFORM_BILLING role constants"
    - "PlatformUser + PlatformAuditLog ORM models + DB tables"
    - "POST /api/v1/platform/auth/login endpoint"
  affects:
    - "backend/app/core/auth.py (Principal.tenant_id now UUID | None)"
    - "backend/app/core/tokens.py (create_access_token signature)"
    - "All callers of create_access_token get tenant_id=None support"

tech_stack:
  added: []
  patterns:
    - "Separate platform decoder function (not branch) — structural scope isolation"
    - "Scope check before role check — security invariant in require_platform_role()"
    - "Platform tables with GRANT but no RLS — platform-scoped, not tenant-scoped"
    - "Late imports inside dependency closures (noqa: PLC0415) to break circular deps"

key_files:
  created:
    - backend/alembic/versions/e1a2b3c4d5f6_add_platform_users_and_audit_logs.py
    - backend/app/modules/platform/__init__.py
    - backend/app/modules/platform/models.py
    - backend/app/modules/platform/schemas.py
    - backend/app/modules/platform/auth_service.py
    - backend/app/modules/platform/audit_service.py
    - backend/app/modules/platform/auth_router.py
    - backend/tests/test_platform_scope_isolation.py
  modified:
    - backend/app/core/tokens.py
    - backend/app/core/auth.py
    - backend/app/core/rbac.py
    - backend/app/database.py
    - backend/app/main.py

decisions:
  - "Separate get_current_platform_principal() function (not a branch in get_current_principal) — structural invariant prevents tenant tokens ever reaching platform logic"
  - "Scope check fires BEFORE role check in both get_current_platform_principal() and require_platform_role() — tenant JWT with role=platform_admin is rejected at scope, role claim is never read"
  - "Platform tables have no RLS — platform operations span all tenants; app.tenant_id session variable is meaningless in platform context; access controlled by require_platform_role() at application layer"
  - "DateTime(timezone=True) for all timestamp columns — asyncpg rejects timezone-aware datetimes against TIMESTAMP WITHOUT TIME ZONE columns"
  - "platform module uses get_session_raw (no RLS injection) for auth router — platform login has no tenant context to set"

metrics:
  duration_seconds: 1803
  completed_date: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_created: 8
  files_modified: 5
  tests_added: 6
  tests_total: 365
---

# Phase 25 Plan 01: Platform/Tenant Scope Separation — Core Infrastructure Summary

**One-liner:** JWT scope="platform" family with separate decoder, require_platform_role() RBAC guard, PlatformUser/PlatformAuditLog tables, and 6 isolation tests proving scope-before-role security invariant.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Extend core auth/token primitives | 14cac39 | tokens.py, auth.py, rbac.py |
| 2 | Alembic migration + platform module | 309215d | e1a2b3c4d5f6 migration, platform/ module (6 files), main.py, database.py |
| 3 | 6 scope isolation tests | 2cea887 | test_platform_scope_isolation.py, models.py (TIMESTAMPTZ fix) |

## What Was Built

### Core Token/Auth Changes
- `create_access_token(tenant_id: UUID | None, ..., platform_user_id: UUID | None)` — when `tenant_id=None`, the `"tenant_id"` key is omitted entirely from JWT claims (never written as `null`)
- `Principal.tenant_id: UUID | None` — backward compatible; existing tenant flows always supply a real UUID
- `get_current_platform_principal()` — decodes JWT, checks `scope == "platform"` BEFORE any role or DB lookup, then validates `PlatformUser.is_active`; entirely separate from `get_current_principal()`

### RBAC
- `PLATFORM_ADMIN`, `PLATFORM_SUPPORT`, `PLATFORM_BILLING` string constants in `rbac.py`
- `PLATFORM_ROLES: frozenset[str]` — union of all three
- `require_platform_role(*roles)` — FastAPI dependency factory; delegates to `get_current_platform_principal()` (scope verified there), then belt-and-suspenders scope check, then role membership check

### Database
- Migration `e1a2b3c4d5f6` (down_revision=tp11): creates `platform_users` + `platform_audit_logs` with `GRANT SELECT, INSERT, UPDATE, DELETE ON platform_users TO rotas_app` and `GRANT SELECT, INSERT ON platform_audit_logs TO rotas_app`
- No RLS on either table — documented rationale in migration comments

### Platform Module
- `PlatformUser` / `PlatformAuditLog` ORM models with `DateTime(timezone=True)` columns
- `platform_login()` service: credential validation + `create_access_token(tenant_id=None, scope="platform", platform_user_id=user.id)`
- `record_platform_audit()` service: caller-commits pattern matching `audit/service.py`
- `POST /api/v1/platform/auth/login` public endpoint registered in `main.py`

### Tests (6 GREEN)
1. `test_tenant_token_cannot_access_platform_endpoint` — dashboard JWT on platform path → not 200
2. `test_platform_token_cannot_access_tenant_endpoint` — platform JWT on /api/v1/trips → 401 or 403
3. `test_platform_admin_login_returns_scope_platform` — scope="platform", no tenant_id claim, platform_user_id present
4. `test_require_platform_role_checks_scope_before_role` — crafted JWT (scope=dashboard, role=platform_admin) → 403 at scope check
5. `test_platform_billing_role_token_has_correct_role` — role="platform_billing" in claims
6. `test_tenant_jwt_scope_is_dashboard` — existing tenant login → scope="dashboard" + tenant_id present

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] TIMESTAMP WITHOUT TIME ZONE columns rejected timezone-aware datetimes**
- **Found during:** Task 3 (first test run — 3/6 failed)
- **Issue:** `PlatformUser` model used `datetime.now(UTC)` (timezone-aware) but migration created `TIMESTAMP WITHOUT TIME ZONE` columns. asyncpg raises `DataError: can't subtract offset-naive and offset-aware datetimes`
- **Fix:** Changed `PlatformUser.created_at`, `updated_at` and `PlatformAuditLog.timestamp` column types to `DateTime(timezone=True)` in both models.py and migration. Applied `ALTER TABLE ... ALTER COLUMN ... TYPE TIMESTAMPTZ` to already-migrated DB
- **Files modified:** `backend/app/modules/platform/models.py`, `backend/alembic/versions/e1a2b3c4d5f6_add_platform_users_and_audit_logs.py`
- **Commit:** 2cea887

## Verification Results

```
backend $ python -m pytest tests/test_platform_scope_isolation.py -v
6 passed in 4.46s

backend $ python -m pytest tests/ -x --tb=short -q
365 passed, 2 skipped in 102.57s

backend $ ruff check app/
All checks passed.
```

## Security Invariants Confirmed

- Scope check fires BEFORE role check — test 4 (abuse scenario) proves this with a JWT signed by the real secret carrying scope=dashboard + role=platform_admin: rejected 403 before role is read
- Platform tokens have no `tenant_id` claim key (not `null`, absent) — test 3 asserts `"tenant_id" not in claims`
- `get_current_principal()` rejects scope=platform with `invalid_token_scope` 401 — test 2 confirms platform tokens cannot reach tenant endpoints

## Known Stubs

None — all functionality wired and tested end-to-end.

## Self-Check: PASSED
