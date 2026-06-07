<!-- GSD:project-start source:PROJECT.md -->
## Project

**ROTAS**

ROTAS é uma plataforma SaaS multitenant de gestão de frotas construída para operadores logísticos e transportadoras em Moçambique. O produto resolve dois problemas simultaneamente: motoristas precisam registar viagens, abastecimentos e descargas sem conexão confiável (PWA offline-first com Dexie.js + sync idempotente), e gestores precisam de controlo financeiro rigoroso sobre custos de frota, cumprimento documental e faturamento de clientes. É distribuído como SaaS público — qualquer transportadora moçambicana pode contratar e começar a operar.

**Core Value:** Um motorista moçambicano consegue completar uma viagem inteira — partida, abastecimento, paradas e descarga — sem conexão, e todos os dados chegam intactos ao gestor quando o sinal reaparecer.

### Constraints

- **Tech stack**: FastAPI + Next.js + Vite/React + PostgreSQL — não mudar stack base
- **Compatibilidade**: Dexie.js 4 já em uso — manter schema IndexedDB compatível ao adicionar SW
- **Dados financeiros**: Colunas de valor monetário precisam migrar de `float` para `Numeric(10,2)` sem perder dados históricos
- **Caracteres locais**: Suporte a UTF-8 completo em todos os outputs (PDF, XLSX) — nomes moçambicanos com acentos e diacríticos
- **Multitenant safety**: Toda query deve filtrar por `tenant_id` — nunca remover esse filtro em otimizações
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Summary
## Languages
- Python 3.11+ — backend API (`backend/`)
- TypeScript 5.5 — both frontend apps (`apps/driver/`, `apps/manager/`)
- HTML/CSS — `apps/driver/index.html`, `apps/manager/app/globals.css`
## Runtime
- Python >= 3.11 (declared in `backend/pyproject.toml`)
- ASGI server: Uvicorn `>=0.29` with `[standard]` extras (websocket/http2 support)
- Node.js (version unspecified — no `.nvmrc` or `.node-version` file)
- npm workspaces (root `package.json` manages `apps/*`)
## Package Managers
- Workspace layout: `apps/driver`, `apps/manager`
- Build backend: `setuptools>=69` + `wheel`
- Virtual environment: `backend/.venv/` (committed, not gitignored per current state)
## Frameworks
### Backend — `backend/`
| Package | Version | Purpose |
|---|---|---|
| `fastapi` | `>=0.111` | HTTP API framework, ASGI |
| `sqlalchemy[asyncio]` | `>=2.0` | ORM + async query layer |
| `alembic` | `>=1.13` | Database migrations |
| `pydantic-settings` | `>=2.2` | Settings via env vars (`backend/app/config.py`) |
| `uvicorn[standard]` | `>=0.29` | ASGI server |
| `python-jose[cryptography]` | `>=3.3` | JWT signing/verification (HS256 algorithm) |
| `python-multipart` | `>=0.0.9` | File upload parsing |
| `asyncpg` | `>=0.29` | Async PostgreSQL driver (used by SQLAlchemy) |
| `psycopg[binary]` | `>=3.1` | Sync Psycopg3 driver (used by Alembic migrations) |
### Driver PWA — `apps/driver/`
| Package | Version | Purpose |
|---|---|---|
| `react` | `^18.3.0` | UI framework |
| `react-dom` | `^18.3.0` | DOM renderer |
| `dexie` | `^4.0.0` | IndexedDB wrapper for offline-first local storage |
| `lucide-react` | `^0.468.0` | Icon library |
| `vite` | `^5.4.0` | Dev server + bundler |
| `@vitejs/plugin-react` | `^4.3.0` | React Fast Refresh + JSX transform |
### Manager Web App — `apps/manager/`
| Package | Version | Purpose |
|---|---|---|
| `next` | `^14.2.0` | React framework with App Router |
| `react` | `^18.3.0` | UI framework |
| `react-dom` | `^18.3.0` | DOM renderer |
| `@tanstack/react-query` | `^5.0.0` | Server state / data fetching |
| `lucide-react` | `^0.468.0` | Icon library |
## Build / Dev Tooling
- `ruff >=0.4` — linter and formatter (`target-version = "py311"`, `line-length = 100`)
- Selected rules: `E, F, I, UP, B` (errors, pyflakes, isort, pyupgrade, bugbear)
- `vite ^5.4.0` — build + dev server, port 5174 (`apps/driver/vite.config.mjs`)
- `typescript ^5.5.0` — type checking only (`tsc --noEmit`)
- `next ^14.2.0` — dev server at port 3030 (`apps/manager/next.config.mjs`)
- `typescript ^5.5.0` — type checking only
## Testing
| Package | Version | Purpose |
|---|---|---|
| `pytest` | `>=8.2` | Test runner |
| `pytest-asyncio` | `>=0.23` | Async test support (`asyncio_mode = "auto"`) |
| `httpx` | `>=0.27` | HTTP client for ASGI integration tests |
- Test directory: `backend/tests/`
- 18 test modules present covering API endpoints and domain logic
- No frontend test framework detected in either `apps/driver/` or `apps/manager/`
## Configuration
| Setting | Env Var | Default |
|---|---|---|
| Database URL | `DATABASE_URL` | `postgresql+asyncpg://rotas:rotas@localhost:55432/rotas` |
| JWT secret | `JWT_SECRET_KEY` | `change-me-in-env` |
| JWT algorithm | (hardcoded) | `HS256` |
| Access token TTL | (hardcoded) | 15 minutes |
| Refresh token TTL | (hardcoded) | 30 days |
| CORS origins | `CORS_ORIGINS` | `[]` |
| Local upload dir | `LOCAL_UPLOAD_DIR` | `.rotas_uploads` |
- `VITE_ROTAS_API_BASE_URL` — backend base URL
- `VITE_ROTAS_TENANT_ID`, `VITE_ROTAS_VEHICLE_ID`, `VITE_ROTAS_DRIVER_ID`, `VITE_ROTAS_CHECKLIST_TEMPLATE_ID`, `VITE_ROTAS_DRIVER_TOKEN`
- Runtime override: values can also be set in `localStorage` (e.g., `rotas_api_base_url`, `rotas_tenant_id`)
- `ROTAS_API_BASE_URL` — backend base URL (read in `apps/manager/app/lib/api.ts`, `apps/manager/app/lib/auth.ts`)
## Infrastructure
- PostgreSQL 16 on port 55432
- Redis 7 on port 6381 (AOF persistence enabled)
## PDF / XLSX Generation
## Gaps / Unknowns
- No Node.js version pinned (no `.nvmrc`, `.node-version`, or `engines` field in `package.json`)
- No Tailwind CSS detected in `apps/manager/` despite it being mentioned in project docs — only `globals.css` and no `tailwind.config.*` found
- Redis is provisioned in `infra/docker-compose.yml` but no Redis client package (`redis-py`, `aioredis`) is present in `backend/pyproject.toml` — Redis is unused by the backend at this time
- No frontend test framework (Vitest, Jest, Playwright) present in either app
- No PWA manifest or service worker found in `apps/driver/` — offline-first is implemented via Dexie IndexedDB but no SW registered
- Python version is declared as `>=3.11` but the actual installed interpreter appears to be 3.13 (`.pyc` files in `__pycache__` are `cpython-313`)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Summary
## Module Structure
- `backend/app/modules/billing/domain.py` — `BillableTripCandidate`, `billing_status_for_candidate`, `can_create_billing_item`, `belongs_to_billing_period`
## Naming Patterns
- `vehicle.created`, `vehicle.updated`, `vehicle.qr_code_issued`, `vehicle.document_renewed`, `vehicle.odometer_updated_from_fuel`
- `driver.created`, `driver.updated`, `driver.document_renewed`
- `trip.billing_finalized`
- `cargo.load_permit_created`, `cargo.delivery_proof_created`, `cargo.delivery_proof_validated`, `cargo.delivery_proof_disputed`, `cargo.delivery_dispute_resolved`
- `billing.document_created`, `billing.item_created`, `billing.document_issued`, `billing.item_billed`
- `contract.created`, `contract.updated`
- `fuel_log.created`, `fuel_log.verified`
- `operational_exception.created`, `operational_exception.resolved`
## Linting and Formatting
## API Error Envelope
## Request ID / Correlation
- Reads `X-Request-Id` header (max 128 chars). If absent or too long, generates a `uuid4().hex`.
- Stores in a `ContextVar` accessible via `get_request_id()`.
- Echoes the value back in the `X-Request-Id` response header.
- Error responses include `request_id` in the error body.
## Authentication Pattern
## RBAC Pattern
## Multitenancy Isolation
- Every tenant-owned table carries `tenant_id` (indexed FK to `tenants.id`).
- Tenant ID is **extracted from the JWT** by `get_current_principal` — clients can never inject their own `tenant_id` into request bodies for privileged operations.
- Services always scope queries with `WHERE tenant_id = ?`. The `_require_vehicle` / `_require_driver` pattern (checking `vehicle.tenant_id != tenant_id`) is the canonical way to enforce isolation on lookups.
- Tests explicitly verify cross-tenant isolation: e.g., same plate allowed in tenant B after creation in tenant A; history endpoint returns 404 for wrong tenant.
## Idempotency Pattern
### HTTP Idempotency (manager dashboard mutations)
- Client sends `Idempotency-Key` header.
- First call: inserts `IdempotencyKey` record, executes handler, stores response.
- Replay (same key + same payload hash): returns cached response, no duplicate write.
- Replay with different payload: raises `ApiError("idempotency_key_reused", ..., 409)`.
- TTL: 30 days for operational entities, 90 days for billing entities (`billing_document`, `billing_item`).
### Sync Idempotency (offline PWA batch)
## Audit Log Pattern
- `tenant_id`, `user_id`, `driver_id`, `action`, `entity_type`, `entity_id`
- `old_values` (JSON), `new_values` (JSON)
- `ip_address`, `user_agent`
- `correlation_id` — automatically set from `get_request_id()` if not provided
## Service Layer Conventions
- Services return plain `dict` (never raw ORM objects) for public-facing flows.
- Helper functions prefixed with `_` (e.g., `_require_vehicle`, `_plate_exists`) are module-private.
- `serialize_vehicle(vehicle: Vehicle) -> dict` pattern is used to decouple ORM shape from response shape.
- Services call `record_audit_log` directly inside the same DB session before committing, ensuring audit and mutation are in the same transaction.
- Services accept a `db: AsyncSession` parameter — sessions are opened by the router via `Depends(get_session)`.
## Router Conventions
- Routers handle HTTP mechanics only: parsing headers, injecting dependencies, forwarding to service.
- No business logic in routers.
- Response type annotations are omitted (returns untyped `dict`/`list` from service).
- Pagination via `limit` and `offset` query params with sensible defaults and bounds: `Query(50, ge=1, le=200)`.
## Frontend Conventions
## Gaps / Unknowns
- No ESLint config file found for either frontend app — linting beyond TypeScript is unclear.
- Manager app has no explicit API error-handling conventions established in code (no shared `useError` hook or error boundary pattern observed).
- No shared `types/` package between driver and manager apps — schemas are duplicated or implicit.
- `domain.py` files only exist in `billing/`; other modules with complex rules (e.g., `availability`, `compliance`) embed rules in `service.py` — inconsistent placement.
- No pre-commit hooks configured (no `.pre-commit-config.yaml` found).
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Summary
## Overall Pattern
## Multitenancy
- `dashboard` — for manager/web users (`User` model, roles: owner/admin/manager/viewer).
- `driver_app` — for drivers on mobile devices (`Driver` + `DriverDevice` models, paired by one-time code).
## Authentication Details
- `POST /api/v1/auth/login` → returns `access_token` + `refresh_token`.
- Next.js server action (`apps/manager/app/lib/auth.ts`) stores tokens in HttpOnly cookies.
- Next.js middleware (`apps/manager/middleware.ts`) redirects unauthenticated requests to `/login`.
- All API calls from server components use `apiFetch()` (`apps/manager/app/lib/api.ts`) which reads session cookies and injects `Authorization` + `X-Tenant-Id` headers.
- Driver pairing: manager generates a pairing code → driver enters it in the app → `POST /api/v1/driver-auth/pair` → returns a long-lived `access_token` bound to `(driver_id, device_id, tenant_id)`.
- Auth state stored in `localStorage` (keys: `rotas_access_token`, `rotas_tenant_id`, `rotas_driver_id`, `rotas_device_id`).
- Every API call and sync batch sends `Authorization: Bearer <token>` + `X-Tenant-Id: <tenant>` headers.
## Offline Sync Mechanism
### Client-side (IndexedDB via Dexie)
| Store | Purpose |
|---|---|
| `syncQueue` | Primary outbox — every entity creation/update |
| `photoQueue` | Binary photo blobs awaiting upload |
| `pendingFuelLogs` | Fuel log local state mirror |
| `loadPermits`, `cargoManifests`, `deliveryProofs` | Local entity mirrors |
| `driverProfile`, `vehicles`, `checklistTemplates`, `destinations` | Read-only reference data synced from server |
| `activeTrip`, `tripStops`, `tripCosts`, `transportDocuments` | Trip execution state |
| `pendingChecklists`, `checklistResponses` | Checklist local state |
### Sync execution (`apps/driver/src/sync.ts`)
### Server-side (`backend/app/modules/sync/`)
## Data Flow
### Driver records a fuel refuel (offline scenario)
### Manager views the control tower dashboard
## Domain Modules
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
## Database Layer
- **ORM:** SQLAlchemy 2 with async sessions (`AsyncSession`, `async_sessionmaker`).
- **Driver:** `asyncpg` via `postgresql+asyncpg://`.
- **Session management:** `get_session()` in `backend/app/database.py` is a FastAPI dependency that yields an `AsyncSession` per request.
- **Model discovery:** `import_all_models()` imports all `models.py` modules at startup to register SQLAlchemy metadata before Alembic or the ORM uses it.
- **Migrations:** Alembic, with 20+ migration files in `backend/alembic/versions/`.
- **Default currency/timezone:** `MZN` / `Africa/Maputo` on `Tenant` model defaults.
## Cross-Cutting Infrastructure
## Gaps / Unknowns
- **No WebSocket / push channel**: The manager dashboard has no real-time updates — data is stale until page reload. Control tower shows a snapshot, not a live feed.
- **Sync pull direction missing**: The driver app only pushes data (`sync/batch`). There is no mechanism to pull updated server state into IndexedDB (e.g., trip assignment changes, new checklist templates) beyond the `bootstrap` endpoint which returns minimal metadata, not entity data.
- **`availability` module**: Listed in `backend/app/modules/` directory but not registered in `main.py` or `database.py` MODEL_MODULES. Its router and models are not imported.
- **File storage**: Config shows `local_upload_dir = ".rotas_uploads"`. No S3/object storage integration found — production file storage strategy is not specified.
- **No background task runner**: No Celery, ARQ, or similar found. Alerts module presumably generates alerts synchronously or not at all in current state.
- **Conflict resolution on sync**: Server returns `conflict` status but the client only marks items as `conflict` in IndexedDB — there is no conflict resolution UI or merge strategy.
- **Tenant limits enforcement**: `max_vehicles`, `max_drivers`, `max_users` fields exist on `Tenant` but no enforcement was found in service layers during this analysis.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->

## Design System

Always read `DESIGN.md` before making any visual or UI decisions.
All font choices, colors, spacing, border radius, motion, and aesthetic direction are defined there.
Do not deviate without explicit user approval.

Key rules enforced at all times:

- Fonts: Manrope (UI/body) + IBM Plex Mono (data/IDs/monetary values). Never Inter, Roboto, Arial, or system-ui as primary.
- Accent color: `--amber: #f59e0b`. Never purple gradients or generic blue as the primary brand accent.
- Sidebar: always grouped sections (Operações / Frota / Financeiro / Config). Never a flat list.
- Badges: always with a colored dot (`::before` circle). Never plain text badges.
- Decoration: minimal. No blobs, decorative gradients, or illustration backgrounds.
- In QA mode: flag any component that doesn't match DESIGN.md tokens.

## v2.0 Migration Rules

Every new table with `tenant_id` created in Phases 5-12 MUST include the following RLS
statements in the same CREATE TABLE migration -- never as a follow-up patch:

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_{table} ON {table}
    USING (tenant_id::text = current_setting('app.tenant_id', true));
```

Additionally, grant `rotas_app` read/write access in the same migration:

```sql
GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app;
```

**Rationale:** The export_jobs gap (Phase 9) was caused by a table created on a parallel
Alembic branch after the RLS migration ran. GRANT...ON ALL TABLES only covers tables
existing at migration execution time. Co-locating RLS + GRANT in the CREATE TABLE migration
prevents this class of gap permanently.

**Enforcement:** Plan-checkers for Phases 10-12 must verify any new `tenant_id` table in
`files_modified` has a corresponding RLS block in the same migration file. Fail as blocker
if absent.
