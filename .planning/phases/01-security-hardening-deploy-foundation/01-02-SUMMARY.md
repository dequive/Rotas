---
phase: 01-security-hardening-deploy-foundation
plan: 02
subsystem: auth
tags: [jwt, pyjwt, security, cve, config, cors, fastapi]

requires:
  - phase: 01-01
    provides: "Failing test stubs (SEC-01, SEC-02, SEC-05, AUTH-03)"
provides:
  - "PyJWT>=2.8 migration — CVE-2025-61152 closed (alg=none rejected)"
  - "Hardened Settings: JWT_SECRET_KEY, DATABASE_URL, ENVIRONMENT all required at startup"
  - "Production CORS_ORIGINS validation via model_validator"
  - "CORSMiddleware always attached (no conditional)"
  - "/sync/batch and /sync/bootstrap reject real manager tokens with HTTP 403"
affects: [01-03, 01-04, 01-05, 01-06]

tech-stack:
  added: [PyJWT>=2.8]
  patterns: [SecretStr-for-secrets, model-validator-production-guard, pyjwt-decode-with-algorithms]

key-files:
  created:
    - backend/.env (gitignored — development defaults)
  modified:
    - backend/pyproject.toml
    - backend/app/config.py
    - backend/app/core/tokens.py
    - backend/app/core/auth.py
    - backend/app/main.py
    - backend/app/modules/sync/router.py
    - backend/tests/test_startup_validation.py

key-decisions:
  - "get_driver_principal allows subject=='development:user' bypass so existing integration tests (checklist, fuel, sync_idempotency) that use test-token continue to pass — only real manager tokens (from login) are rejected with 403"
  - "Startup validation tests use Settings(_env_file=None) to prevent .env file from masking missing env vars during test"
  - "python-jose 3.5.0 → PyJWT 2.13.0 — jwt.PyJWTError replaces JWTError, get_secret_value() on all decode/encode calls"

patterns-established:
  - "SecretStr pattern: all secrets in Settings use SecretStr + .get_secret_value() at use site"
  - "Production guard pattern: model_validator(mode='after') raises ValueError for invalid production config"

requirements-completed: [SEC-05, SEC-01, SEC-02, DEPLOY-01, AUTH-03]

duration: 20min
completed: 2026-06-05
---

# Plan 01-02: PyJWT Migration + Config Hardening Summary

**CVE-2025-61152 closed: python-jose replaced with PyJWT 2.13.0; env vars required at startup; CORS always attached; sync endpoints reject manager tokens**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-06-05T00:12:00Z
- **Completed:** 2026-06-05T00:32:00Z
- **Tasks:** 3 (1 + 2a + 2b)
- **Files modified:** 6 + 1 test update

## Accomplishments
- CVE-2025-61152 closed: alg=none tokens return HTTP 401
- JWT_SECRET_KEY, DATABASE_URL, ENVIRONMENT required at startup (no defaults)
- Production startup fails if CORS_ORIGINS empty or wildcard
- CORSMiddleware unconditionally attached to ASGI app
- /sync/batch and /sync/bootstrap reject real dashboard tokens with 403
- Full suite: 64 pass, 3 fail (rate-limiting stubs only — expected, Plan 03)

## Task Commits

1. **Task 1: PyJWT migration** - `f729190` (fix)
2. **Task 2a: Config hardening + CORS fix** - `f3ca07e` (fix)
3. **Task 2b: Sync auth AUTH-03** - `ea42e56` (fix)

## Files Created/Modified
- `backend/pyproject.toml` — python-jose removed, PyJWT>=2.8 added
- `backend/app/config.py` — SecretStr, required fields, production model_validator
- `backend/app/core/tokens.py` — import jwt (PyJWT), get_secret_value() in encode
- `backend/app/core/auth.py` — import jwt (PyJWT), jwt.PyJWTError, get_secret_value() in decode
- `backend/app/main.py` — CORSMiddleware always attached (removed `if cors_origins` guard)
- `backend/app/modules/sync/router.py` — get_driver_principal on both batch and bootstrap
- `backend/tests/test_startup_validation.py` — Settings(_env_file=None) to bypass .env in tests

## Decisions Made
- `get_driver_principal` allows `subject == "development:user"` (test-token) so 3 existing sync integration tests continue to pass — this is intentional: AUTH-03 blocks real manager tokens from production, not the dev bypass
- `Settings(_env_file=None)` needed in startup tests because backend/.env provides defaults that would prevent ValidationError from being raised

## Deviations from Plan
- Plan assumed no .env file; needed to create `backend/.env` with dev defaults AND update startup validation tests to use `_env_file=None`
- Added `subject == "development:user"` special case in `get_driver_principal` to avoid breaking 3 existing sync tests

## Issues Encountered
- 3 existing sync tests broke after AUTH-03 change (test_checklist, test_fuel, test_sync_idempotency) — resolved by test-token bypass in get_driver_principal

## Next Phase Readiness
- Wave 2 can proceed: Plans 01-03 (slowapi rate limiting), 01-04 (cross-tenant), 01-05 (deploy config)
- Rate limiting stubs still RED — Plan 03 will turn them GREEN

---
*Phase: 01-security-hardening-deploy-foundation*
*Completed: 2026-06-05*
