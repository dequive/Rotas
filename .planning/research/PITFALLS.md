# Pitfalls Research
_Last updated: 2026-06-04_

---

## Summary

Research covers five domains relevant to ROTAS reaching production safely: FastAPI/JWT security beyond the already-audited gaps, Service Worker retrofit to an existing Vite/React SPA, offline sync data integrity, multitenant PostgreSQL at scale, and FastAPI deployment on Railway/Render. Key findings that extend the existing CONCERNS.md audit are marked with **[NEW]**.

The most dangerous unresolved risk beyond the five known critical gaps is the `python-jose` library itself (CVE-2024-33663, CVE-2024-33664, CVE-2025-61152 — `alg=none` acceptance). A second class of risk is the application-layer-only tenant isolation: a single missing `tenant_id` filter in any of the ~38 Control Tower queries or the sync batch processor creates a cross-tenant data leak that fails silently. A third class is the Service Worker retrofit: adding Workbox to Dexie.js 4 requires strict version management or drivers will be stuck on a broken cached build with no network fallback.

---

## Security Pitfalls (FastAPI + JWT)

### Pitfall S-1: JWT Library Has Active CVEs — `python-jose` (HIGH confidence)
**What goes wrong:** ROTAS uses `python-jose`. Three CVEs affect the library through its latest release (3.3.0/3.3.1):
- **CVE-2024-33663** — Algorithm confusion with OpenSSH ECDSA keys; allows signature bypass via key format confusion.
- **CVE-2024-33664** — JWT bomb: a crafted JWE token triggers resource exhaustion (DoS). Affects `3.3.0`.
- **CVE-2025-61152** — `alg=none` tokens are decoded and accepted without any signature verification.

**Why it happens:** `python-jose` is under-maintained. The `alg=none` variant is a well-known class of attack (documented by Auth0 in 2015) and should have been blocked by default years ago. Many FastAPI tutorials still recommend `python-jose`.

**Consequences:** CVE-2025-61152 is a complete auth bypass: an attacker can craft a token with `{"alg": "none"}` in the header, drop the signature, and the library accepts it as valid. Any authenticated endpoint is reachable without credentials.

**Warning signs in ROTAS:** `backend/pyproject.toml` lists `python-jose`; the `decode()` call in `backend/app/core/auth.py` must be checked for an explicit `algorithms=["HS256"]` parameter. If the `algorithms` kwarg is omitted, the library falls back to the token header's algorithm claim.

**Prevention:** Migrate to `PyJWT >= 2.8` (actively maintained, explicit algorithm enforcement) or `joserfc`. If staying on `python-jose`, pin to `>= 3.3.1` and explicitly pass `algorithms=["HS256"]` to every `decode()` call.

**Phase that must address it:** SEC phase / Phase 1 security hardening — before any external-facing deployment.

---

### Pitfall S-2: Algorithm Confusion Attack — RS256 Public Key Used as HS256 Secret (HIGH confidence)
**What goes wrong:** If an API accepts both RS256 and HS256 (or does not lock down the algorithm), an attacker can take the RSA public key (often publicly discoverable at `/.well-known/jwks.json`) and sign a token with HS256 using that public key as the HMAC secret. The server verifies it as a valid HS256 signature using the same key.

**Why it happens:** ROTAS is HS256-only (symmetric shared secret), so the RS256/HS256 swap is not directly applicable. However, if any future OAuth integration or third-party token is accepted on the same `decode()` path, the risk surfaces.

**Consequences:** Token forgery — attacker gains access with arbitrary claims (tenant_id, role).

**Prevention:** Explicitly pass `algorithms=["HS256"]` to every `decode()` call. Never accept algorithm from the token header. Log and reject tokens with unexpected algorithm headers.

**Phase that must address it:** Phase 1 / SEC hardening — enforce algorithm list explicitly.

---

### Pitfall S-3: `test-token` Dev Bypass Reachable in Production (HIGH confidence — already in CONCERNS.md #13, #14)
**What goes wrong:** `backend/app/core/auth.py` accepts `"Bearer test-token"` and grants unconditional `admin` access when `ENVIRONMENT != "production"`. `billing-api.ts` falls back to `"test-token"` if `ROTAS_MANAGER_TOKEN` is not set, independent of the backend environment check.

**Why it matters beyond CONCERNS.md:** The combination means a deployment where `ENVIRONMENT=production` on the backend but `ROTAS_MANAGER_TOKEN` is unset on the Next.js side will send `test-token` to the backend. The backend blocks it. But if `ENVIRONMENT` defaults to something other than `"production"` on Railway (e.g., the default is `"development"`), the bypass remains open.

**Warning signs:** Any Railway/Render deployment that does not explicitly set `ENVIRONMENT=production` in the environment variable panel.

**Prevention:** Remove `ROTAS_MANAGER_TOKEN` fallback entirely. Add startup assertion: `if settings.environment == "production" and settings.jwt_secret_key == "change-me-in-env": raise RuntimeError(...)`.

**Phase that must address it:** DEPLOY-01 / Phase 1.

---

### Pitfall S-4: Missing Token Scope Validation on Individual Record Access (MEDIUM confidence)
**What goes wrong:** JWT tokens contain `tenant_id` and `role`. But many routes that accept a record UUID (e.g., `GET /api/v1/trips/{trip_id}`) rely solely on the `tenant_id` filter in the SQLAlchemy query. If a bug or missing filter causes a query to return a record belonging to another tenant, the JWT claims do not provide a second check.

**Why it happens:** Application-layer isolation (no Postgres RLS) means the only defense is the SQLAlchemy filter. This is acknowledged in PROJECT.md Key Decisions as a known risk.

**Consequences:** Cross-tenant data read or mutation without any database-level rejection. Fails silently (returns 200 with another tenant's data).

**Warning signs:** The ~38 sequential Control Tower queries (`control_tower/service.py`) and the sync batch processor are the highest-risk locations — complex query assembly is where `tenant_id` filters are most often accidentally omitted.

**Prevention:** Add a Postgres RLS policy as a second layer (see PROJECT.md decision to revisit for v2). Short-term: write a test fixture that authenticates as tenant A and requests resources owned by tenant B — assert 404 or 403 on all endpoints. This regression test catches missing filters before production.

**Phase that must address it:** Phase 2 / tenant hardening or alongside CT-01 Control Tower optimization.

---

### Pitfall S-5: No Brute-Force Protection on Driver Pairing Codes (HIGH confidence — extends CONCERNS.md #12)
**What goes wrong:** Driver pairing codes are short (likely 6 digits or similar). The pairing endpoint has no rate limiting. During the code's validity window, an attacker on the same network (common in fleet yards) can brute-force all 999,999 combinations in seconds with no lockout.

**Why it matters beyond known gap:** The pairing code grants a persistent device token scoped to a specific driver. A brute-forced pairing allows an attacker to receive all that driver's future sync data and submit fraudulent trip logs attributed to that driver.

**Prevention:** Add `slowapi` rate limiting to `POST /driver-auth/pair` (e.g., 10 attempts per IP per 5 minutes). Add attempt counter per code in Redis. Use 8-digit alphanumeric codes instead of numeric-only.

**Phase that must address it:** SEC-03 / Phase 1.

---

### Pitfall S-6: Sensitive Operational Data in JWT Payload (LOW confidence)
**What goes wrong:** JWTs are base64-encoded, not encrypted. If `tenant_id`, `vehicle_id`, or route information is embedded in the driver token payload, any party with the token (e.g., extracted from `localStorage` via XSS) can read it in plaintext.

**Why it matters for ROTAS:** `localStorage` is used for the driver token (`apps/driver/src/api.ts`). `localStorage` is accessible to any JavaScript running on the same origin, including injected scripts.

**Prevention:** Keep JWT payloads to minimum claims (`sub`, `tenant_id`, `scope`, `exp`). Move sensitive operational claims to a server-side session lookup if needed. Consider `sessionStorage` for the driver token (cleared on tab close, reducing long-lived exposure).

**Phase that must address it:** Phase 2 / auth hardening.

---

## Service Worker Addition to Existing SPA

### Pitfall SW-1: Dexie.js Version Conflict When SW Installs Alongside Running App (HIGH confidence)
**What goes wrong:** When `vite-plugin-pwa` installs the first Service Worker, existing browser tabs remain on the old (no-SW) version. The new SW enters "waiting" state. If the SW's precache manifest includes a new version of `db.ts` with a higher `Dexie` version number (schema migration), the `versionchange` event fires in tabs that still have the old schema open. Dexie 4 requires all connections to close before an upgrade proceeds. On Android Chrome, if the user does not reload, the app tab blocks the DB upgrade indefinitely — and the SW stays in "waiting" state holding offline data.

**Why it happens:** Dexie's `versionchange` handler emits an event but does not force-close connections. The SW lifecycle's `skipWaiting()` takes over the page context but cannot force-close the IndexedDB connection held by the old tab's Dexie instance.

**Consequences:** Drivers on mid-shift may have a broken offline queue that neither the old nor new schema can read. Data loss risk on upgrade if the schema migration runs partially.

**Warning signs:** Any Dexie schema version bump (adding a new table or index) coinciding with a SW deployment.

**Prevention:**
1. Register a `versionchange` listener in Dexie that calls `db.close()` and prompts the user to reload.
2. Keep Dexie schema version bumps decoupled from SW deployments where possible.
3. Set `registerType: 'autoUpdate'` with a reload-on-update prompt in the driver PWA rather than silent skip-waiting.
4. Test: open two tabs, deploy new SW, verify the offline queue survives.

**Phase that must address it:** PWA-01 / Phase 2 — must be designed in from the start of SW implementation.

---

### Pitfall SW-2: Service Worker Cached Broken Build — No Escape Hatch (HIGH confidence)
**What goes wrong:** Once a SW is installed and caches the app shell, a broken deployment is served from cache to every returning user. Unlike a normal web deployment where a server rollback is immediate, a SW-cached broken build persists until:
- The SW update check fires (browser checks every 24h by default, or on next navigation).
- The user manually clears site data.

The driver PWA runs on low-cost Android devices where "clear site data" is buried in settings.

**Consequences:** A bad deployment can brick the driver app for all field users with no server-side fix path. This is especially severe in Mozambique where support channels are limited.

**Prevention:**
1. Set `Cache-Control: no-store` on the `sw.js` file itself (via Vercel/CDN headers) so the browser always re-fetches the SW script.
2. Implement a `"check for updates"` button in the driver app UI that calls `registration.update()`.
3. Use a versioned cache name in Workbox so old caches are cleaned up on activation.
4. Stage SW deployments separately from API deployments — never deploy both simultaneously.

**Phase that must address it:** PWA-01 / Phase 2 — SW deployment strategy must be documented before going live.

---

### Pitfall SW-3: Background Sync API Not Available on Firefox or Older iOS (HIGH confidence)
**What goes wrong:** The Background Sync API (`SyncManager`) is Chromium-only. Firefox keeps it disabled behind a flag. Safari/iOS does not implement it. The ROTAS driver PWA targets Android (specifically low-cost Android devices in Mozambique, per PROJECT.md), so this is not a blocker, but it means:
- The "sync when connection returns" behavior only works if the PWA is in the foreground or the tab is open.
- True background sync (app closed, radio comes up, sync fires) requires the app to be installed as a PWA on Android Chrome with Periodic Background Sync permissions.

**Why it matters for ROTAS:** Drivers complete trips and then close the app. If they close it before sync completes (or before connectivity returns), the Background Sync registration is the only mechanism to flush the Dexie queue. Without it, data sits in IndexedDB until the driver manually re-opens the app.

**Consequences:** "Data arrives when driver next opens the app" rather than "data arrives when network returns." For time-sensitive operations (delivery confirmations triggering invoicing), this introduces unpredictable latency.

**Prevention:**
1. Document the behavior explicitly: sync fires in foreground or within ~5 minutes of app being in background on Android Chrome.
2. Show a "N items pending sync" badge on the PWA home screen so drivers know to keep the app open when connectivity returns.
3. Register Background Sync as progressive enhancement: always queue to Dexie first; Background Sync is the optimization.
4. Test on a real low-cost Android device (not emulator) before declaring offline-first operational.

**Phase that must address it:** PWA-01 / Phase 2 — background sync must be tested on target hardware.

---

### Pitfall SW-4: SW Update Stuck in "Waiting" — Users Never Get New Versions (HIGH confidence)
**What goes wrong:** With `registerType: 'prompt'` (vite-plugin-pwa default), a new SW enters "waiting" state. If the app never shows a "reload to update" prompt (or the driver dismisses it), the old SW runs indefinitely. All users on a fleet can run different SW versions simultaneously, with different cached API response shapes — causing silent deserialization errors when the backend API schema changes.

**Warning signs in ROTAS:** No update prompt logic exists yet (SW is not implemented). This must be designed in from the start.

**Prevention:**
1. Use `registerType: 'autoUpdate'` for the driver PWA — drivers are not power users who need to control updates.
2. On SW activation (`activate` event), call `self.clients.claim()` to take over all existing tabs immediately.
3. Clean up old versioned caches in the `activate` event to prevent cache accumulation.
4. vite-plugin-pwa issue #810: update detection can take 30–60 seconds; set `periodicSyncForUpdates: 3600` to check every hour.

**Phase that must address it:** PWA-01 / Phase 2.

---

### Pitfall SW-5: API Calls Intercepted by SW Cache — Stale Sync Responses (MEDIUM confidence)
**What goes wrong:** Workbox's default `StaleWhileRevalidate` strategy caches API responses. If `POST /api/v1/sync/batch` or `POST /api/v1/driver-auth/refresh` are accidentally matched by a cache strategy, the SW serves a stale 200 response from a previous sync — the driver thinks data synced but it did not.

**Prevention:**
1. Explicitly exclude all POST requests and all `/api/` paths from the Workbox cache. Use `NetworkOnly` for all API routes.
2. Use `CacheFirst` or `StaleWhileRevalidate` only for static assets and the app shell.
3. Set `navigateFallback` only for the SPA shell route, not for API paths.

**Phase that must address it:** PWA-01 / Phase 2 — Workbox config must be reviewed before first deploy.

---

## Offline Sync Data Integrity

### Pitfall OD-1: Idempotency Key Collision Across Tenants (HIGH confidence)
**What goes wrong:** The `POST /api/v1/sync/batch` endpoint uses `idempotency_keys` to deduplicate replayed sync batches. If idempotency keys are generated by the driver device without a tenant namespace (e.g., using only a UUID or timestamp), two drivers from different tenants could theoretically generate the same key. The deduplication logic would then suppress a legitimate operation from one tenant because a key from another tenant was already processed.

**Why it matters for ROTAS:** The idempotency key table is shared across all tenants (multitenant monolith). Unless keys include `tenant_id` as a prefix or namespace, cross-tenant collisions are possible — especially if keys are short or deterministic.

**Warning signs:** Check `backend/app/modules/sync/service.py` and the `idempotency_keys` table schema for whether `tenant_id` is part of the unique constraint.

**Prevention:** Idempotency keys must be `{tenant_id}:{device_id}:{local_uuid}` or the unique constraint on the `idempotency_keys` table must be `(key, tenant_id)` composite, not just `(key)`.

**Phase that must address it:** AUTH-03 / Phase 1 — sync endpoint security hardening.

---

### Pitfall OD-2: Partial Batch Failure Leaves Queue in Inconsistent State (HIGH confidence)
**What goes wrong:** `POST /api/v1/sync/batch` processes a list of operations. If the batch is processed record-by-record without a transaction wrapping the entire batch, and the server crashes or returns a 500 midway through, some operations are committed and some are not. When the driver retries the full batch (correct behavior), the already-committed operations are replayed — idempotency keys prevent true duplicates, but the driver's local queue does not know which items succeeded. The driver either removes all items from the Dexie queue (assuming success) or retries all (assuming failure), leading to either data loss or duplicate attempt records.

**Why it matters:** The CONCERNS.md notes that `_dispatch_update` only supports `checklist`. If a batch contains a mix of `create` and `update` operations, a partial commit on `create` success but `update` failure returns a mixed result. The driver's `sync.ts` must handle per-item status, not just top-level HTTP status.

**Prevention:**
1. Wrap the entire batch in a database transaction, or return per-item status codes in the response body.
2. The driver `sync.ts` must process per-item results and only remove successfully committed items from the Dexie queue.
3. Test: submit a batch of 5 where item 3 is invalid — verify items 1, 2 are committed, items 4, 5 are rolled back, and the driver queue retains only items 3, 4, 5.

**Phase that must address it:** AUTH-04 / Phase 1 and Phase 2 (sync update coverage).

---

### Pitfall OD-3: Clock Skew Between Device and Server Corrupts Temporal Ordering (MEDIUM confidence)
**What goes wrong:** Driver devices in Mozambique may have incorrect system clocks (no NTP sync on cheap Android devices, or clocks set manually). If trip start/end timestamps, fuel log timestamps, or delivery proof timestamps come from the device clock, records can arrive at the server with timestamps in the past or future. Last-write-wins ordering based on these timestamps will be wrong.

**Consequences:** A delivery proof submitted at `2026-06-04T10:00:00` (correct server time) but timestamped `2026-06-03T18:00:00` by the device appears to precede the trip start — billing trigger logic that depends on chronological ordering breaks silently.

**Prevention:**
1. Store both `client_timestamp` (from device) and `server_received_at` (set by server on ingest) for all sync records.
2. Use `server_received_at` for billing triggers and operational ordering; keep `client_timestamp` for display/audit only.
3. Reject records where `client_timestamp` is more than 48 hours in the future (likely wrong clock).

**Phase that must address it:** Phase 2 / sync hardening.

---

### Pitfall OD-4: Silent Data Loss When `update` Operation Falls Through to "Unsupported" (HIGH confidence — extends CONCERNS.md #18)
**What goes wrong:** The sync service returns `"conflict"` status for `update` operations on non-checklist entities. The driver's Dexie queue marks the item as `conflict` and stops retrying. The driver has no UI indication. The data is lost from the server's perspective — the driver's local Dexie copy remains but will never sync.

**Consequences:** A corrected fuel entry or trip cost never reaches the backend. Financial reports are wrong. No error is surfaced to the driver or manager.

**Prevention:**
1. Short-term: remove `"update"` from the driver's `operation` type union until server-side update handlers exist. Make it a compile-time error.
2. Medium-term: Implement update handlers for `fuel_log` and `trip` as the highest-priority entity types.
3. Driver UI must show a "sync failed — N items" indicator with item detail, not just silently stop retrying.

**Phase that must address it:** AUTH-04 / Phase 1.

---

### Pitfall OD-5: Retry Storm After Reconnect — Large Queued Batches Overwhelm Backend (MEDIUM confidence)
**What goes wrong:** A driver who worked offline for 8 hours accumulates hundreds of sync items. When connectivity returns, the SW Background Sync fires and all items are submitted in a single large batch. If multiple drivers reconnect simultaneously (e.g., fleet returns to depot), the backend receives a spike of large batch requests simultaneously, overwhelming the connection pool (already limited to 5 + 10 overflow per CONCERNS.md #8).

**Consequences:** Pool exhaustion causes 503 errors on sync attempts. Drivers retry, making the storm worse. The 38-query Control Tower polling (every 15 seconds) competes for the same pool.

**Prevention:**
1. Break large batches into paginated chunks (e.g., 50 items per request) with exponential backoff on 503.
2. Increase SQLAlchemy pool size for production: `pool_size=10, max_overflow=20` (check Railway/Render instance memory).
3. The Control Tower 15-second revalidation must back off under load — add a jitter or reduce to 60 seconds.

**Phase that must address it:** Phase 2 / performance hardening.

---

## Multitenant Scale Pitfalls

### Pitfall MT-1: Missing `tenant_id` Filter in One Query = Silent Cross-Tenant Leak (HIGH confidence)
**What goes wrong:** Application-layer isolation means every SQLAlchemy query must include `.where(Model.tenant_id == tenant_id)`. There is no database-level enforcement. A single query in the ~38 Control Tower sequential queries or the sync batch processor that omits the filter returns all tenants' rows.

**Why it happens systematically:** Complex aggregation queries (CTEs, subqueries) are where the filter is most often accidentally dropped when refactoring. The upcoming CT-01 optimization (replacing 38 queries with CTEs) is a high-risk moment.

**Consequences:** One tenant's manager sees another tenant's vehicles, trips, or financial data. Fails silently — returns 200 with mixed data.

**Warning signs for ROTAS:** The Control Tower optimization (CT-01) will rewrite many of these 38 queries. Every refactored query is a new opportunity to drop the filter.

**Prevention:**
1. Write a cross-tenant regression test before starting CT-01: authenticate as Tenant A, assert zero records from Tenant B appear in every Control Tower endpoint.
2. Add a SQLAlchemy query event listener that asserts `tenant_id` appears in the WHERE clause of every SELECT (can be done in test mode only).
3. Long-term: add Postgres RLS as a second layer (PROJECT.md already flags this for v2).

**Phase that must address it:** CT-01 optimization phase — must run cross-tenant tests after every query rewrite.

---

### Pitfall MT-2: Redis Cache Without Tenant Namespace = Cross-Tenant Cache Poisoning (HIGH confidence)
**What goes wrong:** When Redis caching is implemented for Control Tower KPIs (CT-02), if cache keys are not tenant-namespaced (e.g., `cache.set("control_tower_kpis", data)` instead of `cache.set(f"control_tower_kpis:{tenant_id}", data)`), Tenant A's cached response is served to Tenant B on the first cache hit.

**Why it matters for ROTAS:** Redis is provisioned but unused. CT-02 will add caching. This mistake is extremely easy to make when adding caching for the first time under deadline pressure.

**Consequences:** One of the most severe multitenant bugs — financial and operational KPIs from one tenant visible to another. The bug only manifests intermittently (when the cache was populated by a different tenant request), making it hard to detect in testing.

**Prevention:** All Redis keys must include `tenant_id`: `{tenant_id}:control_tower:kpis`. Add a code review checklist item: "Does every cache.set() key include tenant_id?"

**Phase that must address it:** CT-02 / Redis cache implementation.

---

### Pitfall MT-3: Composite Index Missing `tenant_id` — Full Table Scan at Scale (MEDIUM confidence)
**What goes wrong:** As the platform onboards multiple tenants, tables like `trips`, `fuel_logs`, and `sync_queue` grow to contain rows from all tenants. An index on `(vehicle_id)` alone forces Postgres to scan all tenants' rows to find the matching vehicle. The correct index is `(tenant_id, vehicle_id)` with `tenant_id` first (since it eliminates the most rows).

**Why it matters for ROTAS:** Currently single-tenant pilot. The issue is invisible until tenant count reaches ~5-10 with active fleets (hundreds of thousands of rows). At that point, slow queries appear suddenly and are hard to diagnose.

**Prevention:** Audit all indexes in Alembic migrations. Ensure every table with a `tenant_id` column has `tenant_id` as the leading column in its most-used composite indexes. Add `EXPLAIN ANALYZE` output to the CT-01 optimization task.

**Phase that must address it:** CT-01 + Phase 3 / scale preparation.

---

### Pitfall MT-4: Alembic Migration Runs Against All Tenants' Data Simultaneously (MEDIUM confidence)
**What goes wrong:** In a shared-table multitenant model, a migration that adds a NOT NULL column without a default, or rewrites financial `float` → `Decimal` columns (CONCERNS.md #7), runs against all tenants' rows in a single transaction. At 100,000 rows this takes seconds and locks the table. At 1,000,000 rows this takes minutes — during which the entire application is down for all tenants simultaneously.

**Why it matters for ROTAS:** The `float` → `Numeric(10,2)` migration is already identified as necessary (CONCERNS.md #7). Doing this incorrectly on a live multi-tenant database causes a full outage.

**Prevention:**
1. Use `ALTER TABLE ... ADD COLUMN ... DEFAULT NULL` followed by a background data migration, then `ALTER COLUMN SET NOT NULL` — never add NOT NULL without a default in a single migration.
2. For the float→Decimal migration: add the new `Numeric` column, backfill in batches, rename in a final migration. Never do a single-statement type cast on a large live table.
3. Test all migrations on a database copy with production-equivalent row counts before running on live.

**Phase that must address it:** Before any data migration involving financial columns — coordinate with BILL domain work.

---

## FastAPI Deploy Pitfalls (Railway / Render)

### Pitfall D-1: Alembic Migration Race Condition on Deploy (HIGH confidence)
**What goes wrong:** Railway and Render deploy by spinning up a new container, running the start command, and then switching traffic. If `alembic upgrade head` is run inside the FastAPI `startup` event (or as a pre-start command), and Railway/Render spins up two instances simultaneously (during a rolling deploy or crash-recovery), both instances attempt `alembic upgrade head` at the same time. Alembic uses an advisory lock (`alembic_version` table lock) to prevent concurrent migrations, but if the lock fails to acquire in time, one instance may start serving traffic with a partially migrated schema.

**Why it happens:** Platform-as-a-service deployments often spin up the new instance before tearing down the old one. Alembic's locking is not designed for this pattern.

**Prevention:**
1. Run `alembic upgrade head` as a separate Railway/Render "pre-deploy" job or a separate one-off process, not inside the application startup event.
2. On Railway: use a `releaseCommand` in `railway.json` that runs migrations before traffic is switched.
3. On Render: use a pre-deploy command in `render.yaml`.
4. Add a readiness check (`/health`) that verifies the DB schema version matches the expected version before accepting traffic.

**Phase that must address it:** DEPLOY-04 / Phase 3 deploy setup.

---

### Pitfall D-2: Free/Starter Tier Sleep Causes Cold Start 500s (HIGH confidence)
**What goes wrong:** Railway and Render's free/starter tiers put services to sleep after inactivity. When a sleeping service receives a request, the DB connection may also be sleeping. The first request hits a connection timeout (PostgreSQL connection pool is cold) and returns a 500. Subsequent requests succeed. For a fleet management app, the first request of the day (morning dispatch) failing is a bad experience.

**Consequences:** `apiFetch` in the manager dashboard throws on the first request; if there is no retry logic, the manager sees an error on login.

**Prevention:**
1. Configure a health-check ping from an external service (UptimeRobot free tier) every 5 minutes to prevent sleep.
2. Set `pool_pre_ping=True` in SQLAlchemy `create_async_engine` to validate connections before use.
3. Handle 503/connection errors in `apiFetch` with one automatic retry after 2 seconds.

**Phase that must address it:** DEPLOY-02 / Phase 3.

---

### Pitfall D-3: Single Uvicorn Worker on Railway = No Concurrency Under Sync Storm (HIGH confidence)
**What goes wrong:** Railway's default FastAPI deployment runs a single Uvicorn worker. The ROTAS backend uses async SQLAlchemy, so a single worker handles concurrent requests via the event loop — in theory. But if any route handler blocks (e.g., PDF generation with a hand-rolled writer, large Alembic migrations in startup, or a synchronous file operation), the single worker stalls and all other requests queue. During a sync storm (multiple drivers reconnecting simultaneously), a blocked worker drops connections.

**Prevention:**
1. Use Gunicorn with 2-4 UvicornWorkers: `gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app`.
2. Ensure all I/O operations in route handlers are async (check PDF export — CONCERNS.md #11 — for blocking `open()` calls).
3. Set `--timeout 30` on Gunicorn to kill hung workers rather than letting them block indefinitely.

**Phase that must address it:** DEPLOY-02 / Phase 3.

---

### Pitfall D-4: `ENVIRONMENT` Variable Defaults to `development` if Unset (HIGH confidence)
**What goes wrong:** If `ENVIRONMENT` is not explicitly set in the Railway/Render environment variable panel, it defaults to `"development"`. This enables:
- The `test-token` auth bypass (CONCERNS.md #13).
- Permissive CORS (if the CORS logic branches on `environment`).
- Detailed error responses in FastAPI (stack traces in API responses).
- The JWT secret default `"change-me-in-env"` may not be caught by a startup guard if the guard only checks `environment == "production"`.

**Why it happens:** Teams in a hurry set the critical secrets (DB URL, JWT secret) but forget the `ENVIRONMENT` flag because it doesn't cause an immediate error.

**Prevention:** `ENVIRONMENT=production` must be the first variable set in the deployment checklist. Add it to DEPLOY-01 required variables list. The Pydantic Settings validator should default to `"production"` in the absence of the variable, not `"development"`.

**Phase that must address it:** DEPLOY-01 / Phase 3.

---

### Pitfall D-5: Database URL Uses `postgresql://` Not `postgresql+asyncpg://` in Production Env (MEDIUM confidence)
**What goes wrong:** Railway auto-generates a `DATABASE_URL` environment variable using the `postgresql://` scheme. SQLAlchemy async requires `postgresql+asyncpg://`. If the Railway-generated URL is used directly (e.g., copied from the Railway dashboard into the env panel), the async engine fails with a cryptic `asyncpg: unknown scheme` or falls back to the sync driver — blocking the event loop on every DB call.

**Prevention:** Document in DEPLOY-01 that `DATABASE_URL` must use `postgresql+asyncpg://`. Add a startup validation that checks the URL scheme and raises a `ValueError` if it is not `postgresql+asyncpg`.

**Phase that must address it:** DEPLOY-01 / Phase 3.

---

### Pitfall D-6: Memory Limit Exceeded by Gunicorn Workers + Connection Pool (MEDIUM confidence)
**What goes wrong:** Railway Starter plan provides 512MB RAM. With 2 Gunicorn/Uvicorn workers, SQLAlchemy pool size 5 + overflow 10 per worker = 30 potential connections per instance. Each PostgreSQL connection uses ~5-10MB on the server side. Large response payloads (unbounded Control Tower queries — CONCERNS.md #20) loaded into memory simultaneously across workers can exceed the 512MB limit, causing OOM kill and an unclean restart.

**Prevention:**
1. Cap Control Tower queue responses at 50 rows (CONCERNS.md #20 fix).
2. Set `pool_size=3, max_overflow=5` per worker for Railway Starter plan.
3. Monitor Railway memory dashboard in the first week of production — set an alert at 400MB.
4. Upgrade to Railway Pro plan before onboarding the second tenant (512MB is too tight for multi-tenant production load).

**Phase that must address it:** CT-03 (pagination) + DEPLOY-02 (production sizing).

---

## Gaps / Unknowns

1. **python-jose version in `pyproject.toml`**: The exact pinned version was not confirmed. If it is `< 3.3.1`, CVE-2024-33664 (JWT bomb DoS) is actively exploitable. Needs direct inspection of `backend/pyproject.toml`.

2. **Idempotency key uniqueness constraint scope**: Whether the `idempotency_keys` table unique constraint is `(key)` or `(key, tenant_id)` composite was not confirmed from the codebase audit. This determines whether cross-tenant key collision (OD-1) is already mitigated.

3. **Alembic migration strategy for `float` → `Numeric` backfill**: The correct approach for zero-downtime migration of financial columns depends on row counts and production traffic patterns. Needs a migration rehearsal on a data copy before execution.

4. **Railway `releaseCommand` support**: Railway's documentation describes a pre-deploy hook for migrations, but the exact TOML syntax and its interaction with health checks was not confirmed from current Railway docs. Needs verification at deploy time.

5. **Background Sync on target Android devices**: The specific Android version and Chrome version on drivers' low-cost devices determines whether Periodic Background Sync is available. This needs field testing on actual hardware.

6. **Workbox version compatibility with Dexie 4**: Workbox 7 (current) and Dexie 4 have no known conflicts, but the interaction between Workbox's `clientsClaim()` and Dexie's `versionchange` event in a concurrent multi-tab scenario has not been tested in the ROTAS context. Needs explicit test case.

---

## Sources

- CVE-2024-33663 / CVE-2024-33664 (python-jose): https://vulert.com/vuln-db/CVE-2024-33663 and https://ethicalhacking.uk/python-jose-security-risk-cve-2024-33663-explained/
- CVE-2025-61152 (python-jose alg=none): https://zeropath.com/blog/cve-2025-45768-pyjwt-weak-encryption-summary (PyJWT reference) and https://dev.to/ofri-peretz/the-jwt-algorithm-none-attack-the-vulnerability-in-1-line-of-code-d9g
- JWT algorithm confusion attacks: https://workos.com/blog/jwt-algorithm-confusion-attacks
- FastAPI security pitfalls: https://medium.com/@ThinkingLoop/fastapi-security-pitfalls-that-almost-leaked-my-user-data-c9903bc13fd7
- Service Worker update stuck: https://github.com/vite-pwa/vite-plugin-pwa/discussions/821 and https://github.com/vite-pwa/vite-plugin-pwa/issues/810
- Cache invalidation SW retrofit: https://gist.github.com/Rich-Harris/fd6c3c73e6e707e312d7c5d7d0f3b2f9 and https://iinteractive.com/resources/blog/taming-pwa-cache-behavior
- Background Sync browser support: https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Offline_and_background_operation
- Dexie versionchange: https://dexie.org/docs/Dexie/Dexie.on.versionchange
- Offline sync idempotency pitfalls: https://dev.to/salazarismo/the-hidden-problems-of-offline-first-sync-idempotency-retry-storms-and-dead-letters-1no8
- Offline conflict resolution: https://www.sachith.co.uk/offline-sync-conflict-resolution-patterns-architecture-trade%E2%80%91offs-practical-guide-feb-19-2026/
- Multitenant data leakage: https://medium.com/@instatunnel/multi-tenant-leakage-when-row-level-security-fails-in-saas-da25f40c788c
- Redis cache tenant isolation: https://redis.io/blog/data-isolation-multi-tenant-saas/
- PostgreSQL multitenant indexing: https://docs.citusdata.com/en/v7.3/articles/designing_saas.html
- FastAPI Railway deployment: https://docs.railway.com/guides/fastapi
- FastAPI Render deployment: https://render.com/articles/fastapi-production-deployment-best-practices
- SQLAlchemy pool exhaustion: https://github.com/fastapi/fastapi/discussions/10450
- FastAPI OOM: https://github.com/fastapi/fastapi/issues/1624
