---
phase: 25-platform-tenant-separation
verified: 2026-06-20T00:00:00Z
status: passed
score: 8/8 must-haves verified
---

# Phase 25: Platform/Tenant Scope Separation — Verification Report

**Phase Goal:** A JWT with `scope="platform"` can never access tenant business endpoints; a JWT with `scope="tenant"` can never access `/platform/*` endpoints. The separation is structural in the JWT, not by convention. ROTAS operators have their own auth plane (`platform_users` table, separate login, roles `platform_admin`/`platform_support`/`platform_billing`).

**Verified:** 2026-06-20
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | Structural scope guard — `require_platform_role()` checks `scope == "platform"` before role | VERIFIED | `rbac.py` L182-197: delegates to `get_current_platform_principal` which rejects non-platform scope at L196-200 in `auth.py` before role is ever read. Belt-and-suspenders check at L192-197 in `rbac.py` also fires. |
| 2 | 8 isolation tests all GREEN | VERIFIED | `pytest tests/test_platform_scope_isolation.py -v` → 8 passed in 4.19s. All named tests present and passing including the three specified. |
| 3 | `PlatformUser` is a separate table, not a flag on `User` | VERIFIED | `platform/models.py` L11-33: `class PlatformUser(Base)` with `__tablename__ = "platform_users"`, no `tenant_id`, separate `password_hash`, `role`. |
| 4 | Platform audit log called on mutations before `db.commit()` | VERIFIED | `platform/service.py`: `suspend_tenant` L159-168, `reactivate_tenant` L185-194, `change_tenant_plan` L210-220 all call `record_platform_audit(db, ...)` then `await db.commit()` immediately after. |
| 5 | All 3 platform roles defined in `rbac.py` | VERIFIED | `rbac.py` L166-170: `PLATFORM_ADMIN = "platform_admin"`, `PLATFORM_SUPPORT = "platform_support"`, `PLATFORM_BILLING = "platform_billing"`, combined into `PLATFORM_ROLES` frozenset. |
| 6 | JWT `scope` claim embedded; tenant tokens carry `scope="dashboard"` | VERIFIED | `tokens.py` L44: `"scope": scope` in claims dict. `auth/service.py` L86: `scope="dashboard"` passed to `create_access_token`. Platform login passes `scope="platform"`. `test_tenant_jwt_scope_is_dashboard` confirms `claims["scope"] == "dashboard"`. |
| 7 | Full test suite: 375 passed | VERIFIED | `pytest tests/ -q` → 375 passed, 2 skipped in 123.89s. Zero failures. |
| 8 | Ruff clean: 0 errors | VERIFIED | `ruff check app/` → "All checks passed!" |

**Score:** 8/8 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/core/rbac.py` | `require_platform_role()` + 3 role constants | VERIFIED | L164-207: all three role constants, `PLATFORM_ROLES` frozenset, `require_platform_role()` factory with dual-check (scope via `get_current_platform_principal`, then role check). Also includes `require_own_tenant_or_platform()` for combined guard. |
| `backend/app/core/auth.py` | `get_current_platform_principal()` with scope-first rejection | VERIFIED | L160-229: separate function (not a branch of `get_current_principal`). Scope check at L196-200 fires before DB lookup — rejects any non-platform scope with 403 `forbidden`. |
| `backend/app/core/tokens.py` | `scope` claim in JWT + `platform_user_id` embedding | VERIFIED | L44: `"scope": scope` always present. L54: `tenant_id` only written when non-None. L60-61: `platform_user_id` embedded for platform tokens. |
| `backend/app/modules/platform/models.py` | `PlatformUser` + `PlatformAuditLog` tables | VERIFIED | L11-33: `PlatformUser.__tablename__ = "platform_users"`. L36-56: `PlatformAuditLog.__tablename__ = "platform_audit_logs"`. No `tenant_id` on either. |
| `backend/app/modules/platform/service.py` | Mutating functions call audit before commit | VERIFIED | `suspend_tenant`, `reactivate_tenant`, `change_tenant_plan` all follow the pattern: mutate → `record_platform_audit()` → `db.commit()`. Atomicity preserved. |
| `backend/tests/test_platform_scope_isolation.py` | 8 isolation tests | VERIFIED | 8 tests collected and all GREEN. Includes the three specifically required: `test_tenant_token_cannot_access_platform_endpoint` (named `_cannot_access_platform_endpoint`), `test_platform_token_cannot_access_tenant_endpoint`, `test_require_platform_role_checks_scope_before_role`. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `get_current_principal` (tenant decoder) | Rejects platform tokens | Missing `tenant_id` claim → `KeyError` → 401 `invalid_token` at `auth.py` L86-93 | WIRED | Platform JWTs have no `tenant_id` claim; `UUID(claims["tenant_id"])` raises `KeyError`, caught and raised as 401. Confirmed by `test_platform_token_cannot_access_tenant_endpoint` passing (401). |
| `get_current_platform_principal` | Rejects tenant tokens | `scope != "platform"` check at `auth.py` L196-200 | WIRED | Fires BEFORE DB lookup or role read. Returns 403 `forbidden`. Confirmed by `test_require_platform_role_checks_scope_before_role`. |
| `require_platform_role()` | `get_current_platform_principal` | FastAPI `Depends()` in closure | WIRED | `rbac.py` L187-188: dependency parameter annotated with `Depends(get_current_platform_principal)` — scope already validated before role check at L192. |
| `platform/service.py` mutations | `record_platform_audit()` | Direct call inside same session | WIRED | All three mutating functions call `record_platform_audit(db, ...)` with same session before `await db.commit()`. |
| Tenant login (`auth/service.py`) | `scope="dashboard"` claim | `create_access_token(scope="dashboard", ...)` at L86 | WIRED | Confirmed by `test_tenant_jwt_scope_is_dashboard`. |

---

### Scope Rejection Matrix (Security Invariants)

| Token Type | Target Endpoint Type | Rejection Mechanism | HTTP Status | Test |
|------------|---------------------|---------------------|-------------|------|
| `scope="dashboard"` (tenant) | `/platform/*` endpoint | `get_current_platform_principal` checks `scope != "platform"` → 403 | 403 | `test_tenant_token_cannot_access_platform_endpoint` |
| `scope="platform"` (platform) | Tenant endpoint | `get_current_principal` reads `claims["tenant_id"]` → KeyError → 401 | 401 | `test_platform_token_cannot_access_tenant_endpoint` |
| `scope="dashboard"` + `role="platform_admin"` (forged) | `get_current_platform_principal` | Scope `"dashboard" != "platform"` → 403 before role is read | 403 | `test_require_platform_role_checks_scope_before_role` |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 8 isolation tests all pass | `pytest tests/test_platform_scope_isolation.py -v` | 8 passed in 4.19s | PASS |
| Full suite backward compat | `pytest tests/ -q` | 375 passed, 2 skipped | PASS |
| Ruff: zero linting errors | `ruff check app/` | All checks passed! | PASS |

---

### Anti-Patterns Found

None. No TODO/FIXME/placeholder patterns, no empty implementations, no disconnected audit calls in the platform service layer.

---

### Human Verification Required

None. All security invariants are verifiable programmatically. Tests explicitly cover the abuse scenario (forged tenant JWT with platform role name).

---

## Summary

Phase 25 fully achieves its goal. The separation between platform and tenant auth planes is structural, not conventional:

1. **Structural decode separation**: `get_current_platform_principal` and `get_current_principal` are entirely separate functions. A platform token sent to a tenant endpoint fails at the missing `tenant_id` claim (401); a tenant token sent to a platform endpoint fails at the explicit scope check before any role or DB lookup (403).

2. **Scope-first ordering confirmed**: `get_current_platform_principal` checks `claims.get("scope") != "platform"` at line 196 of `auth.py` before reading the role or hitting the database. The abuse scenario test (`test_require_platform_role_checks_scope_before_role`) mints a validly-signed JWT with `scope="dashboard"` and `role="platform_admin"` and confirms it receives 403 at the scope check, with the role never examined.

3. **Separate identity table**: `PlatformUser` in `platform_users` has no `tenant_id` — operators have a completely separate identity from tenant `User` rows.

4. **Atomic audit on mutations**: All three mutating service functions (`suspend_tenant`, `reactivate_tenant`, `change_tenant_plan`) call `record_platform_audit()` inside the same session before `db.commit()`, ensuring audit records are never written without the mutation or vice versa.

5. **Backward compatibility intact**: 375 existing tests pass unchanged, confirming tenant auth flows are unaffected.

---

_Verified: 2026-06-20_
_Verifier: Claude (gsd-verifier)_
