---
phase: 22-rbac-permission-based
verified: 2026-06-20T00:00:00Z
status: passed
score: 7/7 must-haves verified
---

# Phase 22: RBAC Permission-Based Verification Report

**Phase Goal:** Qualquer endpoint do backend verifica uma permissão granular (trips.write,
billing.read, fleet.admin) em vez de um role string hardcoded. O owner ou director de um
tenant pode criar roles custom com as permissões exactas que pretende.
**Verified:** 2026-06-20
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                 | Status     | Evidence                                                                                 |
|----|-----------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------|
| 1  | Every manager-facing router uses require_permission(), not require_roles() | VERIFIED | 24 router files grep positive for require_permission; require_roles absent from all modules |
| 2  | 23 granular permission constants exist in rbac.py                    | VERIFIED   | ALL_PERMISSIONS.count == 23; printed sorted list confirms all domains covered            |
| 3  | Billing router uses 4 distinct levels: READ/WRITE/ISSUE/VOID          | VERIFIED   | billing/router.py lines 28,54,124,161,176,298,320 each bind the correct constant         |
| 4  | Mechanic role has workshop perms but zero billing perms               | VERIFIED   | ROLE_PERMISSIONS["mechanic"] billing intersection == empty set; confirmed by test + grep  |
| 5  | TenantRole model and custom_role_id FK exist on User                  | VERIFIED   | users/models.py: TenantRole class + User.custom_role_id mapped column with FK            |
| 6  | 4 /tenant-roles endpoints implemented and protected by ADMIN_USERS    | VERIFIED   | users/router.py: GET/POST /tenant-roles, PATCH /tenant-roles/{id}, POST /{id}/role       |
| 7  | Login embeds perms in JWT; custom role overrides default role perms   | VERIFIED   | auth/service.py _load_user_permissions() + _create_user_tokens() passes permissions=      |

**Score:** 7/7 truths verified

---

### Required Artifacts

| Artifact                                          | Expected                                  | Status     | Details                                                        |
|---------------------------------------------------|-------------------------------------------|------------|----------------------------------------------------------------|
| `backend/app/core/rbac.py`                        | 23 permission constants + ROLE_PERMISSIONS | VERIFIED  | 161 lines; ALL_PERMISSIONS=23; 5 roles defined                 |
| `backend/app/core/auth.py`                        | Principal.permissions field + has_any_permission() | VERIFIED | frozenset field + method at lines 29,31                  |
| `backend/app/modules/users/models.py`             | TenantRole model + User.custom_role_id FK | VERIFIED   | Both present with correct FKs and ARRAY(Text()) permissions col |
| `backend/app/modules/users/service.py`            | create/list/update roles + assign to user | VERIFIED   | All 4 functions implemented, slug validation, unknown-perm check |
| `backend/app/modules/users/router.py`             | 4 /tenant-roles endpoints                 | VERIFIED   | Lines 69-113; all protected with require_permission(ADMIN_USERS) |
| `backend/app/modules/auth/service.py`             | _load_user_permissions() at login         | VERIFIED   | Lines 45-59; custom_role_id path + ROLE_PERMISSIONS fallback    |
| `backend/alembic/versions/934b7fae14fc_*.py`      | tenant_roles migration with RLS + GRANT   | VERIFIED   | RLS enabled, policy created, GRANT to rotas_app in same migration |
| `backend/tests/test_rbac_permissions.py`          | 8 permission matrix tests                 | VERIFIED   | 8 tests, all PASSED (3.25s)                                     |
| `backend/tests/test_tenant_roles_api.py`          | 6 custom role lifecycle tests             | VERIFIED   | 6 tests, all PASSED                                             |

---

### Key Link Verification

| From                         | To                             | Via                                   | Status   | Details                                                               |
|------------------------------|--------------------------------|---------------------------------------|----------|-----------------------------------------------------------------------|
| All 24 routers               | require_permission()           | Depends() annotation                  | WIRED    | 24 files confirmed; no module uses require_roles                       |
| billing/router.py            | BILLING_READ/WRITE/ISSUE/VOID  | 4 distinct Depends() per endpoint     | WIRED    | Read-only ops use BILLING_READ; issue uses BILLING_ISSUE; void uses BILLING_VOID |
| auth/service.py login        | TenantRole.permissions         | _load_user_permissions() → JWT perms  | WIRED    | custom_role_id lookup falls back to ROLE_PERMISSIONS; embedded in JWT |
| get_current_principal()      | Principal.permissions          | JWT "perms" claim → frozenset         | WIRED    | auth.py lines 102-103; None when absent (backward compat)             |
| has_any_permission()         | ROLE_PERMISSIONS fallback      | permissions=None path                 | WIRED    | Test 8 verifies pre-Phase-22 tokens still resolve via role            |

---

### Behavioral Spot-Checks

| Behavior                                                    | Command                                                                    | Result       | Status |
|-------------------------------------------------------------|----------------------------------------------------------------------------|--------------|--------|
| All 8 permission matrix tests pass                          | pytest test_rbac_permissions.py -v                                         | 8/8 PASSED   | PASS   |
| All 6 custom role lifecycle tests pass                      | pytest test_tenant_roles_api.py -v                                         | 6/6 PASSED   | PASS   |
| Full test suite unaffected by RBAC migration                | pytest tests/ -q                                                           | 341p, 2skip  | PASS   |
| ALL_PERMISSIONS has exactly 23 entries                      | python -c "from app.core.rbac import ALL_PERMISSIONS; print(len(...))"     | 23           | PASS   |
| Mechanic has zero billing permissions                       | python check: billing intersection of mechanic perms                       | empty set    | PASS   |

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `backend/app/core/permissions.py` | `require_roles()` compatibility shim still present | INFO | Intentional; docstring in rbac.py notes it as shim. No module imports it. |

No blockers or warnings found. The shim is correctly isolated.

---

### v2.0 Migration Rule Compliance

The `tenant_roles` table was created in migration `934b7fae14fc_add_tenant_roles.py` with
RLS + GRANT co-located in the same migration file (lines 73-79), satisfying the v2.0 rule.
A follow-up migration `b4f2c9d8a1e6` adds an idempotent `IF NOT EXISTS` re-apply guard for
the RLS policy — this is additive safety, not a v2.0 violation.

---

### Human Verification Required

None. All goal criteria are verifiable programmatically and all checks passed.

---

### Summary

Phase 22 fully achieved its goal. Every one of the 24 manager-facing router files now
enforces a granular `require_permission()` check. `require_roles()` has zero active call
sites. The 23-permission lattice is complete, the billing router uses all four billing
permission levels with the correct granularity, and the mechanic role is correctly bounded
to workshop operations with no billing access. Custom tenant roles are implemented end-to-end:
create → store in `tenant_roles` → assign to user via `custom_role_id` → loaded at login
and embedded in the JWT `perms` claim → enforced by `has_any_permission()` in every
protected endpoint. Backward compatibility is preserved for tokens minted before Phase 22
(no `perms` claim → falls back to `ROLE_PERMISSIONS[role]`). All 14 new tests pass and
the full 341-test suite is green.

---

_Verified: 2026-06-20_
_Verifier: Claude (gsd-verifier)_
