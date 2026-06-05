---
phase: 01-security-hardening-deploy-foundation
status: passed
verified: 2026-06-05
requirements: [SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, AUTH-03, DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04]
notes: DEPLOY-02, DEPLOY-03, DEPLOY-04 verified at config level — actual production deploy deferred by user decision
---

# Phase 1: Security Hardening + Deploy Foundation — Verification

**Result: PASSED** *(with DEPLOY note — see below)*

**Test suite: 67/67 passed**

---

## Requirement Verification

### SEC-05 — CVE-2025-61152: alg=none JWT rejected

| Check | Status | Evidence |
|-------|--------|----------|
| python-jose removed | ✓ | `backend/pyproject.toml` line 13: `"PyJWT>=2.8"` — no python-jose |
| PyJWT rejects alg=none | ✓ | `backend/app/core/auth.py`: `jwt.decode(..., algorithms=[settings.jwt_algorithm])` |
| test_alg_none_token_rejected PASSED | ✓ | 67/67 test suite green |

---

### SEC-01 — JWT_SECRET_KEY required at startup

| Check | Status | Evidence |
|-------|--------|----------|
| SecretStr with no default | ✓ | `config.py` line 20: `jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY")` |
| ValidationError if absent | ✓ | `test_missing_jwt_secret_raises_validation_error` PASSED |

---

### SEC-02 — CORS: always attached, production validation

| Check | Status | Evidence |
|-------|--------|----------|
| CORSMiddleware always attached | ✓ | `main.py` lines 45-51: unconditional `app.add_middleware(CORSMiddleware, ...)` |
| Production rejects empty CORS_ORIGINS | ✓ | `config.py` model_validator: `if not self.cors_origins or "*" in self.cors_origins: raise ValueError` |
| test_production_cors_origins_empty_raises PASSED | ✓ | 67/67 suite green |

---

### SEC-03 — Rate limiting: 429 after 10 req/min

| Check | Status | Evidence |
|-------|--------|----------|
| slowapi>=0.1.9 installed | ✓ | `pyproject.toml` line 14: `"slowapi>=0.1.9"` |
| `/auth/login` rate limited | ✓ | `auth/router.py` line 20: `@limiter.limit("10/minute")` |
| `/auth/refresh` rate limited | ✓ | `auth/router.py` line 30: `@limiter.limit("10/minute")` |
| `/driver-auth/pair` rate limited | ✓ | `auth/router.py` line 48: `@limiter.limit("10/minute")` |
| RateLimitExceeded handler registered | ✓ | `main.py` line 41: `app.add_exception_handler(RateLimitExceeded, ...)` |
| test_login_rate_limited_after_10_requests PASSED | ✓ | 67/67 suite green |

---

### SEC-04 — Secure cookies in production

| Check | Status | Evidence |
|-------|--------|----------|
| route.ts: secure=isProduction | ✓ | `apps/manager/app/api/auth/login/route.ts` line 34: `secure: isProduction` |
| route.ts: sameSite=lax | ✓ | line 35: `sameSite: "lax" as const` |
| auth.ts: secure=isProduction | ✓ | `apps/manager/app/lib/auth.ts` line 55: `secure: isProduction` |
| auth.ts: sameSite=lax | ✓ | line 56: `sameSite: "lax" as const` |
| TypeScript: no errors | ✓ | `npx tsc --noEmit` exits 0 |

---

### AUTH-03 — Sync endpoints require driver token

| Check | Status | Evidence |
|-------|--------|----------|
| /sync/batch uses get_driver_principal | ✓ | `sync/router.py` line 18: `Depends(get_driver_principal)` |
| /sync/bootstrap uses get_driver_principal | ✓ | `sync/router.py` line 26: `Depends(get_driver_principal)` |
| Manager token rejected with 403 | ✓ | `test_manager_token_rejected_on_sync_batch` PASSED |
| test_manager_token_rejected_on_sync_bootstrap PASSED | ✓ | 67/67 suite green |

---

### DEPLOY-01 — Startup validates required env vars

| Check | Status | Evidence |
|-------|--------|----------|
| ENVIRONMENT required | ✓ | `config.py`: `environment: str = Field(validation_alias="ENVIRONMENT")` — no default |
| DATABASE_URL required | ✓ | `config.py`: `database_url: str = Field(validation_alias="DATABASE_URL")` — no default |
| JWT_SECRET_KEY required | ✓ | `config.py`: `jwt_secret_key: SecretStr = Field(...)` — no default |
| All startup validation tests PASSED | ✓ | 67/67 suite green |

---

### DEPLOY-02 — Railway config with pre-deploy migrations

| Check | Status | Evidence |
|-------|--------|----------|
| railway.toml exists | ✓ | Repo root: `railway.toml` |
| preDeployCommand = alembic upgrade head | ✓ | line 5: `preDeployCommand = ["alembic upgrade head"]` |
| startCommand = uvicorn with $PORT | ✓ | line 9: `startCommand = "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"` |
| backend/__init__.py exists | ✓ | `backend/__init__.py` created |
| **Production deploy executed** | ⏳ DEFERRED | Deploy postponed — product in active development |

---

### DEPLOY-03 — Vercel config for manager frontend

| Check | Status | Evidence |
|-------|--------|----------|
| apps/manager/vercel.json exists | ✓ | `apps/manager/vercel.json`: `"framework": "nextjs"` |
| engines.node=20.x in package.json | ✓ | root `package.json` + `apps/manager/package.json` |
| api.ts reads NEXT_PUBLIC_API_URL | ✓ | `apps/manager/app/lib/api.ts` line 3 |
| auth.ts reads NEXT_PUBLIC_API_URL | ✓ | `apps/manager/app/lib/auth.ts` line 6 |
| **Production deploy executed** | ⏳ DEFERRED | Deploy postponed — product in active development |

---

### DEPLOY-04 — Alembic migrations auto-run on deploy

| Check | Status | Evidence |
|-------|--------|----------|
| preDeployCommand configured | ✓ | `railway.toml` line 5 |
| alembic/env.py reads DATABASE_URL | ✓ | Pre-existing: `settings.database_url.replace("+asyncpg", "+psycopg")` |
| **Confirmed running in production** | ⏳ DEFERRED | Deploy postponed |

---

## Phase 1 Goal Assessment

**Goal**: "The backend is free of active CVEs, auth cannot be bypassed, and the application is deployed to production with validated configuration."

| Success Criterion | Status |
|-------------------|--------|
| alg=none JWT rejected with HTTP 401 (CVE-2025-61152 closed) | ✓ |
| Backend refuses to start if JWT_SECRET_KEY/DATABASE_URL/ENVIRONMENT missing | ✓ |
| /auth/login and /driver-auth/pair return HTTP 429 after 10 req/min | ✓ |
| Backend reachable at production URL with Alembic migrations applied | ⏳ DEFERRED |
| Manager frontend reachable at Vercel URL, CORS allows only explicit origins | ⏳ DEFERRED |

**Assessment**: All security hardening goals (SEC-01 through SEC-05, AUTH-03) fully met and tested. Deploy config artifacts complete and ready. Actual production deployment deferred by user decision — infrastructure code is done, the act of deploying is the remaining step.

## Human Verification Items (saved in 01-HUMAN-UAT.md)

When deployment is executed, verify manually:
1. `GET https://RAILWAY-URL/health` → `{"status": "ok"}`
2. `GET https://RAILWAY-URL/version` → `{"environment": "production"}`
3. Railway deploy logs show Alembic migration output
4. Vercel manager URL loads and redirects to /login
5. Login flow completes end-to-end
6. Browser DevTools: session cookies have Secure flag
7. No CORS errors in browser DevTools on API requests

---
*Verified: 2026-06-05*
*Verifier: inline (subagent session limit)*
