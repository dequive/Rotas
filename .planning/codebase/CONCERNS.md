# CONCERNS
_Last updated: 2026-06-04_

---

## Summary

The ROTAS backend is a well-structured FastAPI monorepo with a strong domain model, good audit coverage, and disciplined idempotency. However, several gaps between the stated "operacional MVP" status and actual production-readiness exist. The most acute risks are: (1) the `jwt_secret_key` default `"change-me-in-env"` ships silently to production if `.env` is not set; (2) the Driver PWA has no Service Worker / PWA manifest, so it is not truly installable offline; (3) the sync endpoint does not scope to driver token — any dashboard user can submit sync batches; (4) the manager dashboard has two parallel auth layers that diverge in cookie contents; (5) the Control Tower service issues ~38 sequential database queries per request with no caching. The codebase is pre-production-ready for a pilot deployment on a single tenant but has concrete blockers before it can be safely handed to multiple operators.

---

## Critical (MVP Blockers)

### 1. JWT secret key default ships insecurely
- **Issue:** `jwt_secret_key` defaults to `"change-me-in-env"` in `backend/app/config.py:20`. If `JWT_SECRET_KEY` is not set in the production environment, all tokens are signed with a well-known string. Any party that reads this codebase can forge valid tokens.
- **Files:** `backend/app/config.py`, `backend/app/core/auth.py`
- **Impact:** Complete authentication bypass in production if the environment variable is omitted.
- **Fix:** Add a startup validation that refuses to start when `environment != "development"` and `jwt_secret_key == "change-me-in-env"`. Rotate the key to a cryptographically random 32-byte value.

### 2. Driver PWA is not a real PWA — no Service Worker, no web app manifest
- **Issue:** `apps/driver/vite.config.mjs` uses only `@vitejs/plugin-react` — no `vite-plugin-pwa`, no `workbox`, no `manifest.json` in `public/`. The app cannot be installed to a home screen, has no cache-first shell, and will stop functioning entirely if the browser tab is closed while offline. Data queued in Dexie (`RotasMotoristaDB`) persists but the app itself is not offline-accessible.
- **Files:** `apps/driver/vite.config.mjs`, `apps/driver/package.json`
- **Impact:** The core value proposition (offline-first for Mozambique low-connectivity drivers) is undelivered. Drivers cannot use the app after the first page load goes offline.
- **Fix:** Add `vite-plugin-pwa` with a `generateSW` strategy + `manifest.json`. Register a service worker that caches the app shell. This is a non-trivial configuration change.

### 3. Sync endpoint accepts dashboard-scope tokens, not just driver tokens
- **Issue:** `backend/app/modules/sync/router.py` uses `get_current_principal` (not `get_driver_principal`). Any authenticated manager with a dashboard token can POST to `/api/v1/sync/batch` and inject arbitrary trips, fuel logs, or delivery proofs.
- **Files:** `backend/app/modules/sync/router.py`, `backend/app/core/auth.py`
- **Impact:** Cross-role data injection. A manager can create driver-attributed operations without going through the operational controls.
- **Fix:** Replace `get_current_principal` with `get_driver_principal` in both `/sync/batch` and `/sync/bootstrap` handlers, or add an explicit scope check in `process_batch`.

### 4. Manager dashboard cookie auth diverges from `auth.ts` server action
- **Issue:** There are two auth code paths that write cookies differently. `apps/manager/app/api/auth/login/route.ts` writes `rotas_refresh_token` cookie. `apps/manager/app/lib/auth.ts:login()` server action does not write `rotas_refresh_token`. Sessions expire silently after 8 hours (`maxAge: 60 * 60 * 8`) with no refresh attempt. The JWT access token expires in 15 minutes (backend `access_token_minutes: 15`) but the cookie lives for 8 hours — so every server action within the 8-hour window sends an expired JWT to the backend and gets silent 401 responses.
- **Files:** `apps/manager/app/api/auth/login/route.ts`, `apps/manager/app/lib/auth.ts`, `apps/manager/app/lib/api.ts`
- **Impact:** Manager dashboard goes silently stale after 15 minutes. API calls start returning 401 but `apiFetch` only throws without redirecting to login.
- **Fix:** Implement token refresh in `apiFetch` using the stored `rotas_refresh_token` cookie. Unify the two login code paths to a single implementation.

### 5. CORS is disabled unless explicitly configured
- **Issue:** `backend/app/main.py:39` only adds `CORSMiddleware` when `cors_origins` is non-empty. An empty list (the default) means CORS headers are never sent. The Driver PWA makes cross-origin fetch calls to the backend. If `CORS_ORIGINS` is not set in production, the PWA sync will fail in all browsers due to missing CORS headers.
- **Files:** `backend/app/main.py`, `backend/app/config.py`
- **Impact:** Driver PWA sync silently fails in production if `CORS_ORIGINS` env var is not configured.
- **Fix:** Document `CORS_ORIGINS` as a required deployment variable in the README. Consider failing-closed at startup for production environments.

---

## High (Reliability Risks)

### 6. Control Tower issues ~38 sequential DB queries per request
- **Issue:** `backend/app/modules/control_tower/service.py` (695 lines) calls `await _count()`, `await db.scalar()`, and `await db.scalars()` approximately 38 times sequentially to assemble the dashboard response. Each query is a separate async round-trip to PostgreSQL. There is no result caching. The manager dashboard revalidates every 15 seconds (`revalidate: 15` in `loadControlTower`).
- **Files:** `backend/app/modules/control_tower/service.py`, `apps/manager/app/lib/control-tower-api.ts`
- **Impact:** Under any meaningful load (multiple concurrent operators), the Control Tower request latency will be high. Redis is provisioned in `infra/docker-compose.yml` but never connected to the application.
- **Fix:** Materialise a read model with a short TTL in Redis, or batch the queries using CTEs / `UNION ALL` into fewer round-trips. Alternatively, accept the Redis client dependency and cache the result for 10–30 seconds.

### 7. `Mapped[float]` with `Numeric(12, 2)` columns — Python type mismatch
- **Issue:** Financial columns across billing and trips models use `Mapped[float]` as the Python annotation but `Numeric(12, 2)` as the SQL column type. SQLAlchemy returns `Decimal` objects for `Numeric` columns; annotating them as `float` bypasses type-safety. The billing domain object at `backend/app/modules/billing/domain.py:20` has `amount: float`. This means arithmetic in Python can accumulate floating-point rounding errors on monetary values.
- **Files:** `backend/app/modules/billing/models.py`, `backend/app/modules/trips/models.py`, `backend/app/modules/billing/domain.py`
- **Impact:** Potential rounding errors in billing totals and margin calculations. At current scale this is low-risk, but it is architecturally incorrect and will be harder to fix later.
- **Fix:** Change all financial `Mapped[float]` annotations to `Mapped[Decimal]`. Update `domain.py` to use `Decimal`. Update service arithmetic to stay in `Decimal` throughout.

### 8. Auth middleware opens a new DB connection per request (outside the request session)
- **Issue:** `backend/app/core/auth.py:77` does `async with AsyncSessionLocal() as db:` inside the `get_current_principal` dependency. This creates a second database connection for every authenticated request in addition to the `get_session` dependency used by the route handler. Under concurrent load this doubles the number of open connections.
- **Files:** `backend/app/core/auth.py`
- **Impact:** Connection pool exhaustion under load. The engine uses SQLAlchemy defaults (pool size 5, max overflow 10). With 15 concurrent authenticated requests, the pool will be exhausted.
- **Fix:** Refactor `get_current_principal` to accept the `db` session from `get_session` via `Depends`, or decode the JWT without a DB lookup and push the tenant/user validation into a separate `Depends` that shares the request session.

### 9. Token refresh not implemented in Driver PWA
- **Issue:** `apps/driver/src/api.ts` stores the access token in `localStorage` and sends it on every request. The access token has a 15-minute TTL. There is no refresh logic in the PWA. After 15 minutes the driver receives 401 errors on all API calls (bootstrap, vehicle list, sync). The PWA silently shows "Sem rede — a trabalhar offline." without distinguishing an auth failure from a network failure.
- **Files:** `apps/driver/src/api.ts`, `apps/driver/src/sync.ts`, `apps/driver/src/App.tsx:85`
- **Impact:** Drivers are de-authenticated mid-shift with no indication. Offline-queued items attempt to sync and fail permanently until the driver re-pairs.
- **Fix:** Implement token refresh using `POST /api/v1/driver-auth/refresh` after receiving a 401. Add a pairing-code or QR re-pair prompt when the refresh token is also expired.

### 10. Docker Compose Postgres uses hardcoded `rotas/rotas` credentials
- **Issue:** `infra/docker-compose.yml` sets `POSTGRES_PASSWORD: rotas` and the `.env.example` encodes `DATABASE_URL=postgresql+asyncpg://rotas:rotas@localhost:55432/rotas`. If this compose file is deployed as-is to a VPS, the database is accessible with predictable credentials.
- **Files:** `infra/docker-compose.yml`, `.env.example`
- **Impact:** Database exposed to brute-force if port 55432 is reachable.
- **Fix:** Remove the hardcoded password from `docker-compose.yml`. Use a `secrets` file or require the password to be injected via environment variable. Document this as a required change before any cloud deployment.

### 11. PDF export uses hand-rolled PDF writer (no proper library)
- **Issue:** `backend/app/modules/billing/exporters.py` implements PDF generation by manually writing PDF content streams (`BT`, `Tf`, `Td`, `Tj`, `ET` operators). There is no PDF library dependency (`reportlab`, `weasyprint`, `fpdf2`) in `pyproject.toml`. The implementation only supports `Helvetica`/`Helvetica-Bold` built-in fonts and does not support Unicode characters beyond ASCII. Mozambican client names with accents (e.g., `Ção`, `José`) will have characters silently dropped or corrupted by `_pdf_escape()`.
- **Files:** `backend/app/modules/billing/exporters.py`, `backend/pyproject.toml`
- **Impact:** Billing PDFs with non-ASCII content (common in Mozambican Portuguese) will be malformed. This could affect invoice legality.
- **Fix:** Replace with `fpdf2` or `reportlab` which handle font encoding correctly. Both are lightweight and have no system dependencies.

### 12. No rate limiting on authentication endpoints
- **Issue:** `POST /api/v1/auth/login` and `POST /api/v1/driver-auth/pair` have no rate limiting or lockout mechanism. An attacker can attempt unlimited password guesses or pairing-code brute-force attempts. Driver pairing codes are short (likely a few digits given the UX) and expire, but during the expiry window they can be brute-forced without restriction.
- **Files:** `backend/app/modules/auth/router.py`, `backend/app/modules/auth/service.py`
- **Impact:** Credential brute-force attacks succeed without detection.
- **Fix:** Add FastAPI middleware-level rate limiting (e.g., `slowapi`) scoped to IP or `tenant_slug`. At minimum, add a failed-attempt counter with exponential backoff per email.

---

## Medium (Tech Debt)

### 13. All tests use `Bearer test-token` dev bypass — no real JWT tests except `test_auth_api.py`
- **Issue:** 17 of 18 test files authenticate using the `"Bearer test-token"` development shortcut (`backend/app/core/auth.py:40`). This bypass is granted `admin` role unconditionally and skips the full JWT decode path, the tenant-activity check, and the user-activity check. Only `test_auth_api.py` exercises the real token flow. RBAC enforcement (role checks) is tested only through the dev path which always grants `admin`.
- **Files:** All test files in `backend/tests/`, `backend/app/core/auth.py`
- **Impact:** RBAC role boundaries are not tested. A regression in `require_roles()` would not be caught. Tests do not validate that the production authentication stack works end-to-end.
- **Fix:** Add a shared `authed_headers(role)` fixture that creates a real JWT via `create_access_token` for the given role. Replace `test-token` usage in at least the most security-sensitive flows (billing issue, waiver creation).

### 14. Manager dashboard `billing-api.ts` uses `ROTAS_MANAGER_TOKEN` with `test-token` default
- **Issue:** `apps/manager/app/lib/billing-api.ts:244` falls back to `"test-token"` when `ROTAS_MANAGER_TOKEN` is not set. This bypasses authentication for the billing module specifically, independent of the cookie-based login flow.
- **Files:** `apps/manager/app/lib/billing-api.ts`
- **Impact:** In a production deployment without `ROTAS_MANAGER_TOKEN` set, billing API calls use the dev bypass token. This is only blocked if the backend `ENVIRONMENT` is set to `production`.
- **Fix:** Remove the `ROTAS_MANAGER_TOKEN` escape hatch. All manager calls should go through the cookie-authenticated `apiFetch` with the session's `accessToken`.

### 15. Manager fallback/demo data scattered across API lib files
- **Issue:** `billing-api.ts`, `control-tower-api.ts`, `fleet-history-api.ts`, and `fuel-operations-api.ts` each define `fallbackTrips`, `fallbackTower`, `fallbackVehicleHistory`, and `fallbackTanks` with hardcoded demo data. When `ROTAS_TENANT_ID` is not configured or the API is unreachable, the manager silently shows fake data that looks real.
- **Files:** `apps/manager/app/lib/billing-api.ts`, `apps/manager/app/lib/control-tower-api.ts`, `apps/manager/app/lib/fleet-history-api.ts`, `apps/manager/app/lib/fuel-operations-api.ts`
- **Impact:** An operator who hasn't fully configured the environment will be looking at static demo numbers and making operational decisions based on fake data. There is a `source: "fallback"` discriminant but it is only shown as a small label in some boards.
- **Fix:** Show a prominent "API não configurada — dados de demonstração" banner when `source === "fallback"`. Consider removing fallback data entirely in production builds.

### 16. Redis provisioned but never used by the application
- **Issue:** `infra/docker-compose.yml` provisions a Redis instance on port 6381. No Python code imports a Redis client or uses Redis for any purpose (session storage, caching, rate limiting, background task queuing).
- **Files:** `infra/docker-compose.yml`, `backend/pyproject.toml`
- **Impact:** Infrastructure waste in development. More importantly, the MODULE_CLOSURE_MATRIX mentions Alert "external adapters" and `auth` "MFA" as future work that likely requires Redis. The absence creates a false sense that the infrastructure is ready.
- **Fix:** Either remove Redis from the compose file until it is needed, or document clearly which future feature will adopt it.

### 17. `trips/service.py` and `workshop/service.py` are very large
- **Issue:** `backend/app/modules/trips/service.py` is 1,476 lines and `backend/app/modules/workshop/service.py` is 1,449 lines. Both files contain mixed concerns: pure domain logic, database queries, exception creation, alert creation, and audit log writes.
- **Files:** `backend/app/modules/trips/service.py`, `backend/app/modules/workshop/service.py`
- **Impact:** High cognitive load, test isolation is harder, and risk of side-effect coupling when adding new features.
- **Fix:** Extract sub-services or domain helpers (e.g., `TripCostService`, `WorkOrderTransitionService`) as separate modules. No urgent refactor needed for MVP, but plan to split before adding new features to these modules.

### 18. Sync update path only supports `checklist` entity type
- **Issue:** `backend/app/modules/sync/service.py:196-208` handles `operation == "update"` only for `checklist`. All other entity types (trip, fuel_log, delivery_proof, etc.) return `"unsupported_entity_type_for_update"`. The Driver PWA `db.ts` declares `operation: "create" | "update"` in the queue schema, suggesting updates were intended to be supported more broadly.
- **Files:** `backend/app/modules/sync/service.py`, `apps/driver/src/db.ts`
- **Impact:** If a driver modifies a queued item (e.g., corrects a fuel entry before sync), the update will fail silently with a `conflict` status. The driver has no way to correct data after initial submission.
- **Fix:** Implement update dispatch for at least `fuel_log` and `trip` entity types, or document the limitation explicitly and remove `"update"` from the driver's `operation` type union.

### 19. Manager cookie `secure` flag not set
- **Issue:** Both `apps/manager/app/api/auth/login/route.ts:27` and `apps/manager/app/lib/auth.ts:49` set cookies with `{ httpOnly: true, path: "/", maxAge: 60 * 60 * 8 }`. The `secure: true` flag is not set. On HTTP connections, the `httpOnly` flag alone does not prevent the cookie from being transmitted.
- **Files:** `apps/manager/app/api/auth/login/route.ts`, `apps/manager/app/lib/auth.ts`
- **Impact:** Session cookies transmitted in cleartext over HTTP in any non-HTTPS deployment.
- **Fix:** Add `secure: process.env.NODE_ENV === "production"` to cookie options.

### 20. No pagination guards on Control Tower queue lists
- **Issue:** The Control Tower queue responses (e.g., `pending_dispatch`, `open_incidents`, `negative_margin_trips`) return unlimited rows. `backend/app/modules/control_tower/service.py` applies no `LIMIT` clause to queue queries. With hundreds of active trips, the Control Tower payload will grow unbounded.
- **Files:** `backend/app/modules/control_tower/service.py`
- **Impact:** Response payload size grows linearly with active trips. Not a problem for a pilot with 10–20 vehicles, but will become one beyond ~200 active trips.
- **Fix:** Cap all queue slices at a configurable limit (e.g., 50). Add a `total_count` summary field alongside the capped list.

---

## Low (Polish / Nice-to-Have)

### 21. No password reset flow
- **Issue:** `docs/MODULE_CLOSURE_MATRIX.md` lists "recuperacao de password" as an explicit gap for `users` and `auth`. No `POST /api/v1/auth/forgot-password` or `POST /api/v1/auth/reset-password` endpoint exists. If a manager forgets their password, they must be manually updated via the seed/admin script.
- **Files:** `backend/app/modules/auth/`, `backend/app/modules/users/`
- **Impact:** Support burden for the pilot operator. Not a blocker if someone with DB access is available.

### 22. Alert channel adapters not implemented
- **Issue:** `backend/app/modules/alerts/service.py:14` defines `ALERT_CHANNELS = {"dashboard", "whatsapp", "email", "sms"}` but only the `"dashboard"` channel is functional. WhatsApp, email, and SMS alerts are stored in the database with their channel type but never dispatched externally. The MODULE_CLOSURE_MATRIX acknowledges "adaptadores externos" as a gap.
- **Files:** `backend/app/modules/alerts/service.py`
- **Impact:** Operational alerts (e.g., low stock, SLA breach) are only visible inside the manager dashboard. Managers with the app closed receive no notification.

### 23. File download serves directly from local disk — no signed URL for R2
- **Issue:** `backend/app/modules/files/router.py:110` serves files via `FileResponse` from `LOCAL_UPLOAD_DIR`. The MODULE_CLOSURE_MATRIX lists "storage adapter R2" as a gap. The `presign_upload` service returns `upload_url: "local://..."` which is meaningless to a client — the upload URL is never a real presigned URL.
- **Files:** `backend/app/modules/files/service.py`, `backend/app/modules/files/router.py`
- **Impact:** File storage is not suitable for production without local disk persistence. Cloudflare R2 integration is described in `.env.example` but not implemented.

### 24. Driver PWA has no `vite.config.ts` — only `vite.config.mjs`
- **Issue:** The Vite config at `apps/driver/vite.config.mjs` uses no TypeScript, lacks a `public/manifest.json`, and has no explicit `build.target` for modern browser support. Small issue but inconsistent with the rest of the TypeScript-first codebase.
- **Files:** `apps/driver/vite.config.mjs`

### 25. Pilot seed hardcodes UUIDs and local port
- **Issue:** `backend/scripts/seed_pilot.py` (referenced in `IMPLEMENTATION_STATUS.md`) creates a Maputo tenant with deterministic data targeting `localhost:55432`. The script is marked idempotent but relies on slug uniqueness. If the seed is run against a production DB that already has a `maputo` slug under a different tenant, it will silently succeed without creating the intended data.
- **Files:** `backend/scripts/seed_pilot.py`
- **Impact:** Low risk for the intended single-tenant pilot, but error-prone if the same script is reused for a second deployment.

### 26. No frontend test suite for either app
- **Issue:** Neither `apps/manager/package.json` nor `apps/driver/package.json` includes any test runner (`vitest`, `jest`, `@testing-library/react`). All validation is manual (Playwright screenshots noted in `IMPLEMENTATION_STATUS.md`) or type-checking only.
- **Files:** `apps/manager/package.json`, `apps/driver/package.json`
- **Impact:** UI regressions are not caught by CI. Not a blocker for the pilot but a gap for any sustained operation.

---

## Gaps vs Documentation Claims

| Claim in `docs/` | Reality |
|---|---|
| "Driver PWA scaffold created in Vite/React with Dexie local queue" — implies installable PWA | No Service Worker, no `manifest.json`. The app is a browser SPA, not an installable PWA. |
| "Authentication now issues validated short-lived JWT access tokens" — implies secure by default | `jwt_secret_key` defaults to `"change-me-in-env"`. No startup guard prevents production use of the insecure default. |
| "Manager dashboard responds locally at `http://localhost:3100`" | Dev port in `package.json` is `3030`, not `3100`. Minor inconsistency. |
| `alerts` module listed as "operacional MVP" with gap "adaptadores externos" | WhatsApp/email/SMS alert channels are registered in the schema but have no dispatch implementation. The module is dashboard-only. |
| `files` module listed as "operacional MVP" with gap "storage adapter R2" | `presign_upload` returns `upload_url: "local://..."`. There is no actual presigned URL. Multipart upload flow is functionally broken for clients that try to use the presigned URL directly. |
| "Reusable HTTP idempotency support now reserves keys before mutation" | The `_dispatch_update` path in sync only supports `checklist`. All other update entity types return a failure response. Sync update coverage is incomplete. |
| MODULE_CLOSURE_MATRIX lists `Combustivel` as "operacional MVP" | Fuel tank management backend is implemented, but there is no driver-side flow for internal tank refuels (only external station refuels via the classic fuel log). Tank stock management requires manager desktop access. |
| `auth` listed as "operacional MVP" with gap "recuperacao de password, MFA" | No `/forgot-password` or `/reset-password` endpoint exists. Users are locked out permanently without DB access. |
