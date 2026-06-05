# Phase 1: Security Hardening + Deploy Foundation — Context

**Gathered:** 2026-06-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the active CVE-2025-61152 auth bypass, harden the backend configuration and authentication surface, and deploy both the backend (Railway) and manager frontend (Vercel) to production with validated configuration and automatic Alembic migrations.

This phase does NOT cover: Service Worker / PWA (Phase 2), Control Tower optimization (Phase 3), or billing exports (Phase 3).

</domain>

<decisions>
## Implementation Decisions

### JWT Library Migration (SEC-05 — FIRST)
- **D-01:** Migrate `python-jose` → `PyJWT >= 2.8` as the very first task. Active CVE-2025-61152 — tokens with `alg=none` are accepted without signature verification, which is a complete auth bypass.
- **D-02:** The migration requires updating `backend/app/core/auth.py` (all `jose.jwt.*` calls) and removing `python-jose[cryptography]` from `pyproject.toml`.

### JWT Secret & Startup Validation (SEC-01, DEPLOY-01)
- **D-03:** `jwt_secret_key` must use `pydantic-settings` `SecretStr` with no default. The current default `"change-me-in-env"` must be removed.
- **D-04:** Required env vars that block startup if missing: `JWT_SECRET_KEY`, `DATABASE_URL`, `ENVIRONMENT`. REDIS_URL and R2_* are optional — app starts but those features degrade gracefully.
- **D-05:** `ENVIRONMENT=production` activates strict mode: CORS enforced, `Secure` cookies, test-token bypass disabled.

### Test-Token Dev Bypass
- **D-06:** The `"Bearer test-token"` bypass in `backend/app/core/auth.py` stays active in development (all 17 existing tests keep passing unchanged). It is automatically disabled when `ENVIRONMENT=production`. No test migration in Phase 1.

### Rate Limiting (SEC-03)
- **D-07:** Use `slowapi` (FastAPI-native) with in-memory store. No Redis dependency for rate limiting at this stage.
- **D-08:** Thresholds: `10 requests/minute per IP` on `/api/v1/auth/login`, `/api/v1/auth/refresh`, and `/api/v1/driver-auth/pair`.

### CORS (SEC-02)
- **D-09:** CORS allows production domain only — the Vercel-assigned URL for the manager app. No wildcard `*`. No Vercel preview URL patterns.
- **D-10:** `CORS_ORIGINS` env var accepts a JSON list of explicit origins. In `ENVIRONMENT=production`, app refuses to start if `CORS_ORIGINS` is empty or contains `"*"`. CORS_ORIGINS value is updatable via env var when a custom domain is added later.
- **D-11:** Current CORS code only attaches `CORSMiddleware` when `cors_origins` is non-empty — this conditional logic must be removed and CORS middleware always attached (with explicit origins or fail-closed in production).

### Secure Cookies (SEC-04)
- **D-12:** Manager Next.js cookies: add `secure: process.env.NODE_ENV === "production"` to both `apps/manager/app/api/auth/login/route.ts` and `apps/manager/app/lib/auth.ts`. SameSite should be `Lax`.

### Sync Endpoint Auth Fix (AUTH-03)
- **D-13:** Replace `get_current_principal` with `get_driver_principal` in both `/api/v1/sync/batch` and `/api/v1/sync/bootstrap` handlers in `backend/app/modules/sync/router.py`. Manager tokens must be rejected.

### Backend Deploy — Railway (DEPLOY-01, DEPLOY-02, DEPLOY-04)
- **D-14:** Deploy target: **Railway** (not Render). Railway defaults: Hobby plan, nearest region, service name derived from repo.
- **D-15:** `railway.toml` at repo root with `preDeployCommand = "alembic upgrade head"`. This ensures Alembic migrations run before the new server version accepts traffic.
- **D-16:** `Procfile` or `railway.toml` start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`.
- **D-17:** Required Railway env vars: `JWT_SECRET_KEY`, `DATABASE_URL` (Railway PostgreSQL add-on URL), `ENVIRONMENT=production`, `CORS_ORIGINS`.

### Manager Deploy — Vercel (DEPLOY-03)
- **D-18:** `vercel.json` at `apps/manager/vercel.json` with rewrite rules for Next.js App Router. `NEXT_PUBLIC_API_URL` env var pointing to Railway backend URL. Update `apps/manager/app/lib/api.ts` and `apps/manager/app/lib/auth.ts` to read `process.env.NEXT_PUBLIC_API_URL` instead of `process.env.ROTAS_API_BASE_URL`.
- **D-19:** Pin Node.js to `"engines": { "node": "20.x" }` in root `package.json` and `apps/manager/package.json`. This is a prerequisite for Vercel deploy (currently unset).
- **D-20:** Domain: use Vercel-assigned URL for now (e.g., `rotas-manager.vercel.app`). Updatable via env var later for custom domain.

### Cross-Tenant Regression Tests
- **D-21:** Before phase closes, write tests confirming that a query authenticated as tenant A cannot return data belonging to tenant B. These tests guard the CT-01 query rewrite in Phase 3. Minimum coverage: vehicle, driver, and trip endpoints returning 404 (not data) for wrong tenant.

### Claude's Discretion
- Specific `pyproject.toml` version pins for `PyJWT` and `slowapi` — use latest stable
- Exact `railway.toml` service name and region — use Railway defaults
- Structure of the startup validation (validator function, model_validator, or post_init) — follow pydantic-settings conventions
- Which exact tenant IDs to use in cross-tenant regression tests — use existing test fixtures

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Security & Auth (must read first)
- `backend/app/config.py` — Existing Settings class; jwt_secret_key default to remove, ENVIRONMENT field to add
- `backend/app/core/auth.py` — JWT decode path (python-jose calls to migrate), test-token bypass, get_driver_principal
- `backend/app/main.py` — CORS middleware attachment (conditional logic to fix)
- `backend/app/modules/sync/router.py` — Sync batch endpoint (get_current_principal → get_driver_principal)
- `backend/app/modules/auth/router.py` — Login endpoints (where slowapi decorators go)
- `backend/app/modules/auth/service.py` — Auth service (context for rate limiting scope)

### Frontend Auth & Cookies
- `apps/manager/app/api/auth/login/route.ts` — Cookie set without secure flag (SEC-04 fix here)
- `apps/manager/app/lib/auth.ts` — Second cookie path without secure flag (SEC-04 fix here)

### Deploy Config
- `backend/pyproject.toml` — Dependencies to update (python-jose → PyJWT, add slowapi)
- `package.json` (root) — Add engines.node = "20.x"
- `apps/manager/package.json` — Add engines.node = "20.x"
- `apps/manager/next.config.mjs` — Next.js config (reference before writing vercel.json)

### Tests
- `backend/tests/` — 18 test modules; understand test-token usage before touching auth.py

### Requirements
- `.planning/REQUIREMENTS.md` — SEC-01 through SEC-05, AUTH-03, DEPLOY-01 through DEPLOY-04

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pydantic-settings` `BaseSettings` in `config.py` — already in use; extend it with `SecretStr` for JWT secret and validation logic
- `get_driver_principal` in `backend/app/core/auth.py` — already exists, just needs to be wired into the sync router
- `backend/tests/conftest.py` — existing test fixtures; cross-tenant tests can reuse the same pattern

### Established Patterns
- Settings loaded via `pydantic-settings` with env file fallback — follow this pattern for new required fields
- `Field(validation_alias="ENV_VAR_NAME")` pattern already used in config.py — use same pattern for new vars
- Router-level dependency injection (`Depends(get_driver_principal)`) — already used in driver auth module

### Integration Points
- `backend/app/modules/auth/router.py` — attach `@limiter.limit("10/minute")` decorators
- `backend/app/main.py` — attach `SlowAPIMiddleware` and fix CORS conditional
- `railway.toml` — new file at repo root
- `vercel.json` — new file at `apps/manager/vercel.json`

</code_context>

<specifics>
## Specific Ideas

- ROADMAP specifies: `ENVIRONMENT=production` must activate strict mode — CORS enforce, Secure cookies, no test-token bypass. This is a single production flag, not per-feature toggles.
- ROADMAP specifies: `alg=none` tokens must return HTTP 401 (success criterion #1) — the PyJWT migration is what delivers this.
- ROADMAP specifies: missing env vars must raise `ValidationError` at startup, not at first use — validate at import time.
- Existing `billing-api.ts:244` falls back to `"test-token"` — this should also be cleaned up in this phase as a consequence of the secure-by-default approach (SEC-04 scope expansion).

</specifics>

<deferred>
## Deferred Ideas

- Full test suite migration from `"Bearer test-token"` to real JWT fixtures — Phase 1 only gates the bypass by ENVIRONMENT; test suite update is deferred.
- PostgreSQL RLS as a second isolation layer (defense-in-depth) — noted in PROJECT.md as a v2 revisit; deferred to Phase 4.
- Redis-backed rate limiting — deferred to when multi-worker Railway deployment is needed; in-memory is sufficient for MVP.
- `billing-api.ts` `ROTAS_MANAGER_TOKEN` escape hatch removal — noted in CONCERNS.md #14; addressed as part of the cookie auth unification if time allows, otherwise Phase 2.
- Password reset flow — out of scope for Phase 1.

</deferred>

---

*Phase: 01-security-hardening-deploy-foundation*
*Context gathered: 2026-06-05*
