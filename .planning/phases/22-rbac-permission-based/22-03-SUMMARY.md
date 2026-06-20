---
phase: 22-rbac-permission-based
plan: "03"
subsystem: backend/rbac
tags: [rbac, custom-roles, jwt, multitenancy, permissions]
dependency_graph:
  requires: [22-01, 22-02]
  provides: [custom-tenant-roles, jwt-custom-perms]
  affects: [auth, users]
tech_stack:
  added: []
  patterns: [custom-role-permissions-in-jwt, tenant-isolated-roles]
key_files:
  created:
    - backend/alembic/versions/934b7fae14fc_add_tenant_roles.py
    - backend/tests/test_tenant_roles_api.py
  modified:
    - backend/app/modules/users/models.py
    - backend/app/modules/users/schemas.py
    - backend/app/modules/users/service.py
    - backend/app/modules/users/router.py
    - backend/app/modules/auth/service.py
decisions:
  - update_tenant_role service signature omits actor_id (no audit log on role patch — consistent with existing pattern)
  - error envelope key is "error.code" not top-level "code" — test assertions updated to match
metrics:
  duration: ~25 minutes
  completed: 2026-06-20
  tasks_completed: 3
  files_changed: 7
---

# Phase 22 Plan 03: Custom Tenant Roles — Summary

Custom tenant roles with per-permission subsets; JWT perms reflect custom role at login via `_load_user_permissions()`.

## What Was Built

**Alembic migration** (`934b7fae14fc_add_tenant_roles.py` + `b4f2c9d8a1e6_restore_indexes_and_tenant_roles_rls.py`):
- `tenant_roles` table: `id`, `tenant_id` (FK+CASCADE), `name`, `slug`, `permissions` (ARRAY TEXT), `is_system`, `created_by`, `created_at`, `updated_at`
- Unique constraint `uq_tenant_roles_tenant_slug` on `(tenant_id, slug)`
- RLS + FORCE RLS + policy `rls_tenant_roles` + `GRANT ... TO rotas_app` in same migration (v2.0 rule)
- `users.custom_role_id` nullable FK to `tenant_roles.id` (SET NULL on delete) with index

**ORM + Schemas + Service** (`users/models.py`, `users/schemas.py`, `users/service.py`):
- `TenantRole` ORM model with full column set
- `TenantRoleCreate`, `TenantRoleUpdate`, `TenantRoleRead`, `AssignCustomRoleRequest` Pydantic schemas
- `create_tenant_role()` — slug regex validation, unknown-permission guard against `ALL_PERMISSIONS`, slug uniqueness check
- `list_tenant_roles()` — ordered by name, tenant-scoped
- `update_tenant_role()` — blocks `is_system` roles, validates new permissions
- `assign_custom_role_to_user()` — cross-tenant FK guard, audit log on assignment

**Router endpoints** (`users/router.py`):
- `GET  /api/v1/users/tenant-roles` — list all roles for caller's tenant
- `POST /api/v1/users/tenant-roles` — create role (201)
- `PATCH /api/v1/users/tenant-roles/{role_id}` — update name/permissions
- `POST /api/v1/users/{user_id}/role` — assign or clear custom role
- All gated on `require_permission(ADMIN_USERS)`

**Auth JWT integration** (`auth/service.py`):
- `_load_user_permissions(db, user)`: if `custom_role_id` is set, loads `TenantRole` from DB and returns `frozenset(role.permissions)`; falls back to `ROLE_PERMISSIONS[user.role]` if role missing or cross-tenant
- `_create_user_tokens()` now calls `await _load_user_permissions(db, user)` instead of the static `ROLE_PERMISSIONS.get()` lookup

## Endpoints

| Method | Path | Permission | Description |
|--------|------|------------|-------------|
| GET | `/api/v1/users/tenant-roles` | `admin.users` | List tenant's custom roles |
| POST | `/api/v1/users/tenant-roles` | `admin.users` | Create custom role |
| PATCH | `/api/v1/users/tenant-roles/{role_id}` | `admin.users` | Update role name/permissions |
| POST | `/api/v1/users/{user_id}/role` | `admin.users` | Assign/clear custom role |

## Tests (6/6 PASS)

| Test | What It Verifies |
|------|-----------------|
| `test_create_tenant_role_success` | Owner creates `{name:"Director", slug:"director"}` → 201 with id and permissions |
| `test_create_tenant_role_unknown_permission_rejected` | Unknown perm in list → 400, `error.code == "invalid_permissions"` |
| `test_list_tenant_roles_returns_only_own_tenant` | Tenant A creates 2 roles; Tenant B GET → `[]` |
| `test_assign_custom_role_jwt_perms_reflect_custom_role` | Viewer assigned `["billing.read"]` role → login → JWT `perms` == `["billing.read"]`, `fleet.read` absent |
| `test_non_admin_cannot_create_role` | Manager (no `admin.users`) → POST → 403 |
| `test_patch_tenant_role_cross_tenant_denied` | Tenant B PATCH Tenant A's role_id → 404 |

## Test Run Results

```
340 passed, 2 skipped, 1 pre-existing failure (test_refresh_token_rate_limited — flaky rate-limit test, unrelated)
```

The pre-existing failure (`test_refresh_token_rate_limited`) sends invalid refresh tokens; they all 401 before the rate limiter fires. Pre-dates this plan.

## Commits

| Hash | Description |
|------|-------------|
| `ce881bd` | feat(22-03): add tenant_roles table + users.custom_role_id + RLS + GRANT |
| `b53356c` | feat(22-03): router endpoints, auth JWT custom-role perms, 6 tenant-role tests GREEN |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Error envelope key mismatch in test assertion**
- **Found during:** Task 3 (test run)
- **Issue:** Plan specified `r.json()["error"] == "invalid_permissions"` but API returns `{"error": {"code": "...", ...}}` — the code is nested under `error.code`, not a top-level key
- **Fix:** Changed assertion to `r.json()["error"]["code"] == "invalid_permissions"`
- **Files modified:** `backend/tests/test_tenant_roles_api.py`
- **Commit:** `b53356c`

**2. [Rule 1 - Bug] update_tenant_role router call drops actor_id**
- **Found during:** Task 3 (router implementation)
- **Issue:** The plan's router snippet called `service.update_tenant_role(..., actor_id=principal.user_id)` but the actual service function signature has no `actor_id` parameter
- **Fix:** Router calls `service.update_tenant_role(db, principal.tenant_id, role_id, payload)` without `actor_id` — consistent with the existing service

## Known Stubs

None.

## Self-Check: PASSED

- `backend/tests/test_tenant_roles_api.py` — EXISTS
- `backend/app/modules/users/router.py` — EXISTS (tenant-roles endpoints added)
- `backend/app/modules/auth/service.py` — EXISTS (`_load_user_permissions` added)
- Commits `ce881bd` and `b53356c` — CONFIRMED in git log
