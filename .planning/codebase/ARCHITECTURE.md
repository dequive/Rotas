# Architecture

_Last updated: 2026-06-04_

## Summary

ROTAS is a multi-tenant, offline-first fleet management SaaS built for Mozambique. The backend is a Python/FastAPI async REST API backed by PostgreSQL. Two frontends consume it: a Next.js 15 manager dashboard (server-rendered, cookie-auth) and a React/Vite driver PWA (client-rendered, offline-first via IndexedDB + sync queue). All data is scoped by `tenant_id` enforced at the application layer on every query.

---

## Overall Pattern

**Backend:** Modular monolith. Each domain lives under `backend/app/modules/<domain>/` with its own `models.py`, `schemas.py`, `service.py`, and `router.py`. All modules share a single Postgres database and a single SQLAlchemy `Base`. No internal service-to-service calls — services import each other's functions directly (e.g. `sync/service.py` calls `trip_service.create_trip`, `fuel_service.create_fuel_log`, etc.).

**Frontends:** Two separate apps in an npm workspace. The manager app (`apps/manager`) is Next.js with server components that fetch directly from the API using session cookies. The driver app (`apps/driver`) is a Vite/React SPA that operates offline-first.

---

## Multitenancy

Every database table carries a `tenant_id UUID` column with a foreign key to `tenants.id`. There is no row-level security at the database layer — tenant isolation is enforced in application code.

**Auth flow:**
1. JWT decoded in `backend/app/core/auth.py → get_current_principal()`.
2. `tenant_id` is extracted from the JWT claims.
3. The `X-Tenant-Id` header (sent by both frontends) is validated against the token's `tenant_id`; mismatch raises 403.
4. `Principal` dataclass is injected into every route handler via FastAPI `Depends`.
5. Service functions receive `tenant_id` as an explicit argument and filter all queries with `WHERE tenant_id = :tenant_id`.

**Two scopes exist in the JWT:**
- `dashboard` — for manager/web users (`User` model, roles: owner/admin/manager/viewer).
- `driver_app` — for drivers on mobile devices (`Driver` + `DriverDevice` models, paired by one-time code).

Role enforcement: `backend/app/core/permissions.py → require_roles(*roles)` is a FastAPI dependency factory that gates routes by role.

---

## Authentication Details

**Manager (dashboard scope):**
- `POST /api/v1/auth/login` → returns `access_token` + `refresh_token`.
- Next.js server action (`apps/manager/app/lib/auth.ts`) stores tokens in HttpOnly cookies.
- Next.js middleware (`apps/manager/middleware.ts`) redirects unauthenticated requests to `/login`.
- All API calls from server components use `apiFetch()` (`apps/manager/app/lib/api.ts`) which reads session cookies and injects `Authorization` + `X-Tenant-Id` headers.

**Driver (driver_app scope):**
- Driver pairing: manager generates a pairing code → driver enters it in the app → `POST /api/v1/driver-auth/pair` → returns a long-lived `access_token` bound to `(driver_id, device_id, tenant_id)`.
- Auth state stored in `localStorage` (keys: `rotas_access_token`, `rotas_tenant_id`, `rotas_driver_id`, `rotas_device_id`).
- Every API call and sync batch sends `Authorization: Bearer <token>` + `X-Tenant-Id: <tenant>` headers.

---

## Offline Sync Mechanism

The driver app is built around an **offline-first queue**. All driver actions write to IndexedDB first; a manual or triggered sync pushes them to the server.

### Client-side (IndexedDB via Dexie)

Schema defined in `apps/driver/src/db.ts` (`RotasMotoristaDB`, DB name `RotasMotoristaDB`, schema version 1):

| Store | Purpose |
|---|---|
| `syncQueue` | Primary outbox — every entity creation/update |
| `photoQueue` | Binary photo blobs awaiting upload |
| `pendingFuelLogs` | Fuel log local state mirror |
| `loadPermits`, `cargoManifests`, `deliveryProofs` | Local entity mirrors |
| `driverProfile`, `vehicles`, `checklistTemplates`, `destinations` | Read-only reference data synced from server |
| `activeTrip`, `tripStops`, `tripCosts`, `transportDocuments` | Trip execution state |
| `pendingChecklists`, `checklistResponses` | Checklist local state |

**SyncStatus lifecycle:** `local_only` → `syncing` → `synced` / `retrying` (up to 5 retries) / `conflict` / `failed`

**queueOperation()** (`apps/driver/src/db.ts`): Appends to `syncQueue` with a UUID idempotency key, `retryCount: 0`, `status: "local_only"`.

**queueFuelLog()** (`apps/driver/src/db.ts`): Transactional write — inserts to `pendingFuelLogs` AND `syncQueue` atomically.

### Sync execution (`apps/driver/src/sync.ts`)

`processSyncQueue(token)`:
1. Fetches all `syncQueue` items with status `local_only` or `retrying` where `retryCount < 5`.
2. For each item, calls `syncItem()`:
   a. Sets item status to `syncing`.
   b. Calls `uploadQueuedPhotos()` — uploads `photoQueue` blobs for the entity to `POST /api/v1/files/upload`, receives `serverFileId`, patches payload with real file IDs.
   c. Posts to `POST /api/v1/sync/batch` with `{ device_id, operations: [{ local_id, idempotency_key, operation, entity_type, payload }] }`.
   d. On success (`status: "processed"`): deletes from `syncQueue`, updates `pendingFuelLogs` to `synced`.
   e. On conflict or error: sets status to `conflict`/`retrying`, increments `retryCount`.

### Server-side (`backend/app/modules/sync/`)

`POST /api/v1/sync/batch` → `service.process_batch()`:
1. For each operation, checks `IdempotencyKey` table for duplicate by `(tenant_id, idempotency_key)`.
2. If found with same `request_hash`: returns cached response (idempotent replay).
3. If found with different hash: returns `conflict` error.
4. If new: dispatches to the appropriate domain service via `_dispatch_create()` / `_dispatch_update()`.
5. Stores result in `IdempotencyKey` + records a `SyncEvent`.
6. Handles `IntegrityError` race condition by re-checking the key on rollback.

**Supported sync entity types:** `trip`, `checklist`, `fuel_log`, `trip_stop`, `load_permit`, `cargo_manifest`, `transport_document`, `delivery_proof`, `trip_cost`.

`GET /api/v1/sync/bootstrap`: Returns `{ tenant_id, server_time, supported_entity_types, idempotency_ttl_days }` — used to confirm connectivity and supported operations.

**Idempotency TTL:** 30 days for most entities, 90 days for billing entities.

---

## Data Flow

### Driver records a fuel refuel (offline scenario)

1. Driver fills fuel form in `apps/driver/src/App.tsx → submitFuelLog()`.
2. Photos saved to `db.photoQueue` (blobs in IndexedDB) with `status: "local_only"`.
3. `queueFuelLog()` writes to `db.pendingFuelLogs` + `db.syncQueue` in a single Dexie transaction.
4. App shows "Abastecimento guardado offline."
5. Driver taps sync button → `processSyncQueue(token)`.
6. `uploadQueuedPhotos()` POSTs blobs to `/api/v1/files/upload`; receives `serverFileId`; patches payload.
7. `POST /api/v1/sync/batch` dispatches to `fuel_service.create_fuel_log()`.
8. `FuelLog` row created in Postgres; idempotency record stored.
9. `syncQueue` item deleted; `pendingFuelLogs` status updated to `synced`.

### Manager views the control tower dashboard

1. Next.js server component (`apps/manager/app/page.tsx`) runs on the server.
2. `requireSession()` reads HttpOnly cookie; redirects to `/login` if absent.
3. `loadControlTower()` calls `apiFetch()` → `GET /api/v1/control-tower` with `Authorization` + `X-Tenant-Id`.
4. `control_tower/service.py` runs aggregation queries scoped to `tenant_id`.
5. JSON response rendered into server-side HTML; client receives fully rendered page.

---

## Domain Modules

All under `backend/app/modules/`:

| Module | Tables | Key Responsibility |
|---|---|---|
| `auth` | `user_sessions`, `refresh_tokens` | Login, token refresh, logout for dashboard users |
| `tenants` | `tenants` | Tenant CRUD, plan/limits management |
| `contracts` | `contracts` | Client contracts with rate cards |
| `users` | `users` | Dashboard users (owner/admin/manager/viewer) |
| `drivers` | `drivers`, `driver_devices`, `driver_sessions` | Driver profiles, device pairing, sessions |
| `vehicles` | `vehicles` | Vehicle registry, QR codes |
| `files` | `files` | File metadata; local upload storage |
| `checklists` | `checklist_templates`, `checklists`, `checklist_responses` | Pre/post trip vehicle inspection |
| `fuel` | `fuel_logs`, `fuel_tanks`, `fuel_purchases`, `fuel_receipts`, `fuel_movements`, `vehicle_refuels`, `fuel_stock_counts` | External refuels + internal tank stock |
| `trip_orders` | `trip_orders` | Pre-trip order/dispatch planning |
| `trips` | `trips`, `trip_stops`, `trip_costs`, `dispatch_clearances`, `trip_execution_events`, `trip_incidents`, `known_routes` | Full trip lifecycle |
| `cargo` | `load_permits`, `cargo_manifests`, `transport_documents`, `delivery_proofs` | Cargo documentation chain |
| `billing` | `billing_documents`, `billing_items` | Monthly billing documents per contract |
| `operations` | (operations tables) | Operations admin view / dispatch board |
| `operational_exceptions` | `operational_exceptions` | Manual exception flags on trips |
| `workshop` | `maintenance_requests`, `work_orders`, `work_order_tasks`, `spare_parts_inventory`, `spare_part_movements`, `maintenance_parts_used`, `workshop_tools`, `tool_checkouts`, `maintenance_plans`, `maintenance_schedule` | Full workshop / maintenance lifecycle |
| `control_tower` | (no own tables, aggregates) | Real-time fleet status dashboard aggregation |
| `alerts` | `alerts` | Rule-based alert generation |
| `sync` | `idempotency_keys`, `sync_events` | Offline sync processing and idempotency |
| `audit` | `audit_logs` | Immutable audit trail for admin actions |
| `availability` | (availability tables) | Driver/vehicle availability tracking |

---

## Database Layer

- **ORM:** SQLAlchemy 2 with async sessions (`AsyncSession`, `async_sessionmaker`).
- **Driver:** `asyncpg` via `postgresql+asyncpg://`.
- **Session management:** `get_session()` in `backend/app/database.py` is a FastAPI dependency that yields an `AsyncSession` per request.
- **Model discovery:** `import_all_models()` imports all `models.py` modules at startup to register SQLAlchemy metadata before Alembic or the ORM uses it.
- **Migrations:** Alembic, with 20+ migration files in `backend/alembic/versions/`.
- **Default currency/timezone:** `MZN` / `Africa/Maputo` on `Tenant` model defaults.

---

## Cross-Cutting Infrastructure

**Request context** (`backend/app/core/request_context.py`): `RequestContextMiddleware` sets a `ContextVar[request_id]` per request, propagated in the `x-request-id` response header.

**Idempotency** (`backend/app/core/idempotency.py`): `execute_http_idempotent()` for HTTP endpoints; the sync module has its own integrated idempotency path via `IdempotencyKey` table.

**Error handling** (`backend/app/core/errors.py`): `install_error_handlers(app)` — custom `ApiError` exception class with `error_code`, `message`, `status_code`, optional `details`.

**Audit** (`backend/app/modules/audit/`): `AuditLog` table records `action`, `entity_type`, `entity_id`, `old_values`, `new_values`, `correlation_id`. Queryable by admins via `GET /api/v1/audit-logs`.

**Permissions** (`backend/app/core/permissions.py`): `require_roles(*roles)` factory. Role hierarchy: `owner > admin > manager > viewer`. `WRITE_ROLES = {owner, admin, manager}`. `ADMIN_ROLES = {owner, admin}`.

---

## Gaps / Unknowns

- **No WebSocket / push channel**: The manager dashboard has no real-time updates — data is stale until page reload. Control tower shows a snapshot, not a live feed.
- **Sync pull direction missing**: The driver app only pushes data (`sync/batch`). There is no mechanism to pull updated server state into IndexedDB (e.g., trip assignment changes, new checklist templates) beyond the `bootstrap` endpoint which returns minimal metadata, not entity data.
- **`availability` module**: Listed in `backend/app/modules/` directory but not registered in `main.py` or `database.py` MODEL_MODULES. Its router and models are not imported.
- **File storage**: Config shows `local_upload_dir = ".rotas_uploads"`. No S3/object storage integration found — production file storage strategy is not specified.
- **No background task runner**: No Celery, ARQ, or similar found. Alerts module presumably generates alerts synchronously or not at all in current state.
- **Conflict resolution on sync**: Server returns `conflict` status but the client only marks items as `conflict` in IndexedDB — there is no conflict resolution UI or merge strategy.
- **Tenant limits enforcement**: `max_vehicles`, `max_drivers`, `max_users` fields exist on `Tenant` but no enforcement was found in service layers during this analysis.
