# Codebase Structure

_Last updated: 2026-06-04_

## Summary

ROTAS is an npm workspace monorepo with two frontend apps under `apps/` and a standalone Python backend under `backend/`. Infrastructure config lives in `infra/`. Each frontend has its own `package.json`; the root `package.json` orchestrates workspaces and provides top-level `dev:*` and `lint` scripts.

---

## Top-Level Directory Layout

```
rotas/
├── apps/
│   ├── driver/          # React/Vite offline-first driver PWA
│   └── manager/         # Next.js 15 manager dashboard
├── backend/             # FastAPI async Python API
│   ├── alembic/         # Database migrations
│   ├── app/             # Application source
│   └── tests/           # Backend test suite
├── infra/               # Infrastructure / deployment config
├── docs/                # Project documentation
├── .planning/           # GSD planning documents
├── package.json         # npm workspace root
├── package-lock.json
└── .env.example
```

---

## Backend (`backend/`)

```
backend/
├── alembic/
│   ├── versions/        # 20+ migration scripts (one per feature/schema change)
│   └── env.py           # Alembic environment
├── app/
│   ├── main.py          # FastAPI app init, middleware, router registration
│   ├── config.py        # Pydantic settings (reads .env)
│   ├── database.py      # SQLAlchemy engine, session factory, model importer
│   ├── core/
│   │   ├── auth.py      # JWT decode, Principal dataclass, get_current_principal()
│   │   ├── permissions.py  # require_roles() factory
│   │   ├── tenant.py    # get_current_tenant_id() dependency
│   │   ├── idempotency.py  # execute_http_idempotent() for HTTP endpoints
│   │   ├── errors.py    # ApiError + install_error_handlers()
│   │   ├── passwords.py # Password hashing utilities
│   │   ├── tokens.py    # JWT encoding/decoding helpers
│   │   └── request_context.py  # RequestContextMiddleware + request_id ContextVar
│   └── modules/
│       ├── alerts/
│       ├── audit/
│       ├── auth/
│       ├── availability/    # NOT registered in main.py (incomplete)
│       ├── billing/
│       ├── cargo/
│       ├── checklists/
│       ├── contracts/
│       ├── control_tower/
│       ├── drivers/
│       ├── files/
│       ├── fuel/
│       ├── operational_exceptions/
│       ├── operations/
│       ├── sync/
│       ├── tenants/
│       ├── trip_orders/
│       ├── trips/
│       ├── users/
│       ├── vehicles/
│       └── workshop/
├── scripts/             # Dev/ops helper scripts
├── pyproject.toml       # Python packaging + dev dependencies
└── alembic.ini
```

### Module Internal Structure

Every module under `backend/app/modules/<name>/` follows this layout:

```
<module>/
├── __init__.py
├── models.py      # SQLAlchemy ORM models (tables)
├── schemas.py     # Pydantic request/response schemas
├── service.py     # Business logic (async functions, no HTTP concerns)
└── router.py      # FastAPI APIRouter with route handlers
```

Exceptions:
- `fuel/` has `operations.py`, `operations_router.py`, `operations_schemas.py` — separate sub-domain for internal tank operations vs. external refuels.
- `trips/` has `known_routes_router.py` — the known-routes resource has its own router file registered separately in `main.py`.
- `auth/` splits `driver_router` and `router` in a single `router.py` file; both are registered in `main.py` with different prefixes (`/auth` and `/driver-auth`).
- `control_tower/` has no `schemas.py` — response shapes are built inline in the service.
- `sync/` has `schemas.py` for `SyncBatchRequest` / `SyncOperation` but no separate resource schemas.

### API Route Prefix Pattern

All routes: `POST|GET|PATCH|DELETE /api/v1/<resource>` (prefix from `settings.api_v1_prefix`).

Notable route prefixes:
- `/api/v1/auth` — user login/logout/refresh
- `/api/v1/driver-auth` — driver device pairing
- `/api/v1/sync/batch` — offline sync upload
- `/api/v1/sync/bootstrap` — driver app bootstrap
- `/api/v1/control-tower` — fleet dashboard aggregation
- `/api/v1/audit-logs` — audit trail (admin only)
- `/api/v1/files/upload` — multipart photo/document upload

---

## Driver App (`apps/driver/`)

```
apps/driver/
├── src/
│   ├── main.tsx         # Vite entry point, renders <App />
│   ├── App.tsx          # Root component; all views, checklist + fuel forms
│   ├── api.ts           # REST client (pairDevice, bootstrap, getVehicles, createTrip)
│   ├── db.ts            # Dexie (IndexedDB) schema, queueOperation(), queueFuelLog()
│   ├── sync.ts          # processSyncQueue(), uploadQueuedPhotos()
│   ├── styles.css       # Global styles
│   ├── vite-env.d.ts
│   └── views/
│       ├── PairingView.tsx        # Device pairing screen
│       ├── TripStartView.tsx      # New trip creation
│       ├── LoadPermitView.tsx     # Load permit capture
│       ├── CargoManifestView.tsx  # Cargo manifest capture
│       ├── TripStopView.tsx       # Trip stop / waypoint
│       └── DeliveryProofView.tsx  # Delivery proof capture
├── package.json
├── tsconfig.json
└── vite.config.ts (implied)
```

### Driver App View Model

`App.tsx` manages a single `View` state string:
`"dashboard" | "checklist" | "fuel" | "load_permit" | "cargo_manifest" | "trip_stop" | "delivery_proof" | "new_trip"`

All inline components (`ChecklistPanel`, `FuelPanel`, `BillingPanel`) live directly in `App.tsx`. Extracted views live in `src/views/`.

### Driver App Environment

```
VITE_ROTAS_API_BASE_URL   # Backend API base URL
VITE_ROTAS_TENANT_ID      # Optional fallback tenant ID
```

Runtime config also read from `localStorage`:
- `rotas_api_base_url` — overrides env var at runtime
- `rotas_tenant_id`, `rotas_access_token`, `rotas_driver_id`, `rotas_device_id`, `rotas_driver_name`

---

## Manager App (`apps/manager/`)

```
apps/manager/
├── app/                    # Next.js App Router root
│   ├── layout.tsx           # Root layout (HTML shell, Inter font)
│   ├── page.tsx             # Home / operations dashboard (server component)
│   ├── globals.css
│   ├── login/
│   │   └── page.tsx         # Login page (client component)
│   ├── motoristas/
│   │   └── page.tsx         # Drivers list (server component)
│   ├── viaturas/
│   │   └── page.tsx         # Vehicles list (server component)
│   ├── viagens/
│   │   └── page.tsx         # Trips list (server component)
│   ├── contratos/
│   │   └── page.tsx         # Contracts list (server component)
│   ├── rotas-config/
│   │   └── page.tsx         # Known routes config (server component)
│   ├── api/                 # Next.js API routes
│   │   └── auth/
│   │       └── login/route.ts  # POST /api/auth/login (proxies to backend)
│   ├── components/
│   │   ├── SidebarLayout.tsx          # App shell with nav sidebar
│   │   ├── ControlTowerOverview.tsx   # Live fleet status panel
│   │   ├── TransportCargoBoard.tsx    # Cargo transport board
│   │   ├── FleetComplianceBoard.tsx   # Compliance/checklist board
│   │   ├── FleetHistoryBoard.tsx      # Trip history board
│   │   ├── FuelControlBoard.tsx       # Fuel control board
│   │   ├── CostMarginBoard.tsx        # Cost/margin board
│   │   ├── BillingTripActions.tsx     # Billing action buttons (client component)
│   │   ├── DriverDespachoTableAdmin.tsx  # Dispatch table
│   │   ├── DriverFormModal.tsx        # Driver create/edit modal (client)
│   │   ├── VehicleFormModal.tsx       # Vehicle create/edit modal (client)
│   │   ├── TripFormModal.tsx          # Trip create/edit modal (client)
│   │   ├── TripActionButton.tsx       # Trip action controls (client)
│   │   ├── ContractFormModal.tsx      # Contract create/edit modal (client)
│   │   ├── KnownRouteFormModal.tsx    # Known route modal (client)
│   │   ├── KnownRouteDeleteButton.tsx
│   │   ├── PairingCodeButton.tsx      # Generate driver pairing code (client)
│   │   └── TransportCargoActions.tsx
│   └── lib/
│       ├── auth.ts              # Server actions: getSession(), login(), logout()
│       ├── api.ts               # apiFetch() — server-side fetch with session headers
│       ├── billing-api.ts       # loadBillingTrips(), loadBillingDocuments(), loadContracts()
│       ├── control-tower-api.ts # loadControlTower()
│       ├── drivers-api.ts       # loadDrivers()
│       ├── vehicles-api.ts      # loadVehicles()
│       ├── trips-api.ts         # loadTrips()
│       ├── contracts-api.ts     # loadContracts()
│       ├── fuel-operations-api.ts  # loadFuelControlBoard()
│       ├── fleet-history-api.ts # loadFleetHistories()
│       ├── known-routes-api.ts  # loadKnownRoutes()
│       └── operations-admin-api.ts  # loadDriverDespachoTable()
├── middleware.ts            # Auth guard — redirects unauthenticated requests to /login
├── next.config.mjs
├── package.json
└── tsconfig.json
```

### Manager App Component Pattern

- **Server components** (default in Next.js App Router): call `requireSession()` and `load*()` API functions at the top of the component. No `useState`, no `useEffect`.
- **Client components** (marked `"use client"`): all modal forms (create/edit entities), action buttons. They receive `apiConfig` or specific data props from server components.
- **`apiFetch<T>(path, options)`** (`lib/api.ts`): Used by all `load*` API functions. Reads session, injects auth headers, supports Next.js `revalidate` cache option.

### Manager App Environment

```
ROTAS_API_BASE_URL   # Backend API base URL (server-side only)
```

---

## Naming Conventions

### Python (backend)

- Files: `snake_case.py`
- Classes: `PascalCase` (models, schemas, exceptions)
- Functions: `snake_case` (services, dependencies)
- Schema classes: `<Entity>Create`, `<Entity>Update`, `<Entity>Patch`, `<Entity>Response`
- Router variables: `router = APIRouter(prefix="/<resource>", tags=["<resource>"])`
- Service functions: verb + noun — `create_trip()`, `patch_checklist()`, `list_audit_logs()`

### TypeScript (both apps)

- Files: `PascalCase.tsx` for components, `camelCase.ts` for utilities/hooks
- Components: `PascalCase`
- Functions and variables: `camelCase`
- Interfaces: `PascalCase` (e.g. `AuthState`, `SyncQueueItem`)
- Types: `PascalCase` (e.g. `SyncStatus`, `View`)
- API load functions: `load<Resource>()` (e.g. `loadDrivers`, `loadBillingTrips`)
- DB queue functions: `queue<Entity>()` (e.g. `queueFuelLog`, `queueOperation`)

---

## Where to Add New Code

### New backend domain module

1. Create `backend/app/modules/<name>/` with `__init__.py`, `models.py`, `schemas.py`, `service.py`, `router.py`.
2. Add `"<name>"` to `MODEL_MODULES` tuple in `backend/app/database.py`.
3. Import and register the router in `backend/app/main.py`:
   ```python
   from app.modules.<name>.router import router as <name>_router
   app.include_router(<name>_router, prefix=api)
   ```
4. Create an Alembic migration: `alembic revision --autogenerate -m "add_<name>"`.

### New API endpoint in existing module

Add a route handler to `backend/app/modules/<name>/router.py` and the corresponding service function to `service.py`. Add Pydantic schemas to `schemas.py` if new request/response shapes are needed.

### New manager dashboard page

1. Create `apps/manager/app/<route>/page.tsx` as an async server component.
2. Add `await requireSession()` at the top.
3. Create a `load<Resource>()` function in `apps/manager/app/lib/<resource>-api.ts` using `apiFetch`.
4. Add the route to the sidebar in `apps/manager/app/components/SidebarLayout.tsx`.

### New driver app view

1. Create `apps/driver/src/views/<ViewName>View.tsx`.
2. Add the view name to the `View` union type in `apps/driver/src/App.tsx`.
3. Handle the view in the JSX conditional block in `App.tsx`.
4. If the view generates offline data, add an entity type to `SyncQueueItem["entityType"]` in `apps/driver/src/db.ts` and implement the dispatch in `backend/app/modules/sync/service.py → _dispatch_create()`.

### New sync entity type

1. Add type literal to `SyncQueueItem["entityType"]` in `apps/driver/src/db.ts`.
2. Add dispatch case in `backend/app/modules/sync/service.py → _dispatch_create()` or `_dispatch_update()`.
3. Update `bootstrap()` in `sync/service.py` to include the new type in `supported_entity_types`.

---

## Special Directories

**`backend/alembic/versions/`**
- Generated Alembic migration scripts. One file per schema change.
- Committed to source control. Always generate with `alembic revision --autogenerate`.

**`backend/app/core/`**
- Cross-cutting infrastructure only. No domain logic. No domain model imports except through dependency injection.

**`infra/`**
- Infrastructure configuration (contents not explored in this analysis).

**`.planning/`**
- GSD planning documents. Not shipped to production. Committed to repo for team context.

**`apps/driver/src/views/`**
- Extracted view components for the driver PWA. Inline components that are complex enough to extract but still owned by `App.tsx` state.
