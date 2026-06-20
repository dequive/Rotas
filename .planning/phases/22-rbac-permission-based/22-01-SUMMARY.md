---
phase: 22-rbac-permission-based
plan: 01
subsystem: backend/auth
tags: [rbac, permissions, jwt, security, fastapi]
dependency_graph:
  requires: []
  provides: [rbac-permission-infrastructure, principal-has-any-permission, jwt-perms-claim]
  affects: [backend/app/core/auth.py, backend/app/core/tokens.py, backend/app/modules/auth/service.py]
tech_stack:
  added: []
  patterns: [fastapi-depends-factory, late-import-circular-dep-break, jwt-embedded-permissions]
key_files:
  created:
    - backend/app/core/rbac.py
    - backend/tests/test_rbac_permissions.py
  modified:
    - backend/app/core/auth.py
    - backend/app/core/tokens.py
    - backend/app/modules/auth/service.py
decisions:
  - mechanic role receives fleet.read/drivers.read/trips.read/fuel.read/workshop.read/workshop.write (6 perms, no billing access)
  - manager excluded from billing.void_payment (owner+admin only) — the only behavioral delta from current role-set system
  - perms JWT claim omitted entirely when permissions=None (not set to null) for backward compat
  - late import of ROLE_PERMISSIONS inside has_any_permission() to break auth.py <-> rbac.py circular dependency
metrics:
  duration_minutes: 15
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 3
  tests_added: 8
  tests_total_after: 335
  completed_date: 2026-06-20
---

# Phase 22 Plan 01: RBAC Permission Infrastructure Summary

**One-liner:** Permission-based RBAC layer with 23 string constants, 5-role ROLE_PERMISSIONS matrix, `require_permission()` FastAPI dependency, JWT `perms` claim embedding at login, and `Principal.has_any_permission()` with backward-compatible role fallback.

## What Was Built

### `backend/app/core/rbac.py` (new)

- 23 permission string constants (FLEET_READ, BILLING_VOID, WORKSHOP_WRITE, etc.)
- `ROLE_PERMISSIONS: dict[str, frozenset[str]]` mapping all 5 roles to their effective permission sets
- `ALL_PERMISSIONS = frozenset().union(*ROLE_PERMISSIONS.values())` — exactly 23 unique strings
- `require_permission(*permissions: str) -> Callable` FastAPI dependency factory:
  - Calls `principal.has_any_permission(required)` — grants if ANY required permission is held
  - On denial: raises `ApiError("forbidden", ..., 403, details={"required_permissions": sorted(required)})`
  - `sorted()` converts frozenset to JSON-serializable list (avoids `TypeError: frozenset is not JSON serializable`)

### `backend/app/core/auth.py` (modified)

- `Principal.permissions: frozenset[str] | None = None` added as last optional field
- `Principal.has_any_permission(required: frozenset[str]) -> bool` added:
  - Uses `self.permissions` if not None (explicit JWT claim or custom role)
  - Falls back to `ROLE_PERMISSIONS.get(self.role or "", frozenset())` for legacy tokens
  - Late import of `ROLE_PERMISSIONS` inside method body — breaks `auth.py → rbac.py → auth.py` circular dep
- `get_current_principal()`: extracts `raw_perms = claims.get("perms")` after JWT decode; sets `permissions=frozenset(raw_perms) if raw_perms else None`

### `backend/app/core/tokens.py` (modified)

- `create_access_token()`: new `permissions: frozenset[str] | None = None` parameter
- When `permissions is not None`: adds `claims["perms"] = sorted(permissions)`
- When `None`: key omitted entirely (not `"perms": null`) — backward compatible with old token decoders

### `backend/app/modules/auth/service.py` (modified)

- Added `from app.core.rbac import ROLE_PERMISSIONS`
- `_create_user_tokens()`: computes `permissions = ROLE_PERMISSIONS.get(user.role, frozenset())` before `create_access_token()` call; passes `permissions=permissions`
- `_create_driver_tokens()` left unchanged (drivers use `get_driver_principal()`, not `require_permission()`)

## Permission Matrix (ALL_PERMISSIONS: 23 strings)

| Permission | owner | admin | manager | viewer | mechanic |
|---|---|---|---|---|---|
| fleet.read | + | + | + | + | + |
| fleet.write | + | + | + | — | — |
| drivers.read | + | + | + | + | + |
| drivers.write | + | + | + | — | — |
| drivers.pairing | + | + | — | — | — |
| trips.read | + | + | + | + | + |
| trips.dispatch | + | + | + | — | — |
| trips.close | + | + | + | — | — |
| cargo.write | + | + | + | — | — |
| cargo.validate_delivery | + | + | + | — | — |
| billing.read | + | + | + | + | — |
| billing.write | + | + | + | — | — |
| billing.issue | + | + | + | — | — |
| billing.void_payment | + | + | — | — | — |
| fuel.read | + | + | + | + | + |
| fuel.write | + | + | + | — | — |
| fuel.approve_adjustment | + | + | — | — | — |
| workshop.read | + | + | + | + | + |
| workshop.write | + | + | + | — | + |
| workshop.release_vehicle | + | + | — | — | — |
| admin.users | + | + | — | — | — |
| admin.tenant | + | — | — | — | — |
| audit.read | + | + | — | — | — |

## Test Results

```
tests/test_rbac_permissions.py  8 passed
tests/test_auth_api.py         17 passed
tests/test_rbac_deny.py         9 passed
Full suite:                    335 passed, 2 skipped (known flaky rate-limit tests)
```

The 2 skipped tests are pre-existing Redis rate-limit tests, unrelated to this plan.

## Deviations from Plan

None — plan executed exactly as written.

The `mechanic` role uses the RESEARCH.md matrix (fleet.read, drivers.read, trips.read, fuel.read, workshop.read, workshop.write = 6 permissions) rather than the prompt's abbreviated example (which listed only 4). The plan's `<behavior>` block is the binding spec and explicitly states: "mechanic contains workshop.read, workshop.write, fleet.read, drivers.read, trips.read, fuel.read (NOT billing.read)" — this was followed exactly.

## Commits

| Hash | Message |
|---|---|
| a07e242 | feat(22-01): create rbac.py with 23 permission constants, ROLE_PERMISSIONS for 5 roles, require_permission() dependency |
| 9c16dca | feat(22-01): extend Principal with permissions field and has_any_permission(); add perms param to create_access_token() |
| 3a1f847 | feat(22-01): embed perms JWT claim at login; add 8-test permission matrix test suite |

## Known Stubs

None — all permission constants, role mappings, and JWT embedding are fully wired.

## Self-Check: PASSED
