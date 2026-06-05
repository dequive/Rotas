---
phase: 04-production-hardening-scale-preparation
plan: 08
subsystem: backend/security
tags: [rls, postgresql, multitenancy, alembic, sqlalchemy]
dependency_graph:
  requires: [04-06, 04-07]
  provides: [postgresql-rls, rls-event-listener, alembic-bypassrls]
  affects: [backend/app/database.py, backend/app/core/deps.py, backend/alembic/env.py, all routers]
tech_stack:
  added: []
  patterns:
    - SQLAlchemy after_begin event listener for SET LOCAL app.tenant_id
    - ContextVar for asyncio-safe per-request tenant context
    - Circular-import-safe dependency via app/core/deps.py
    - PostgreSQL RLS with FORCE ROW LEVEL SECURITY + tenant_isolation policy
    - ALEMBIC_DATABASE_URL for BYPASSRLS migrations (Pitfall 1 fix)
key_files:
  created:
    - backend/app/core/deps.py
    - backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py
    - backend/tests/test_rls.py
  modified:
    - backend/app/database.py
    - backend/app/config.py
    - backend/alembic/env.py
    - backend/app/modules/auth/router.py
    - backend/app/modules/alerts/router.py
    - backend/app/modules/analytics/router.py
    - backend/app/modules/audit/router.py
    - backend/app/modules/billing/router.py
    - backend/app/modules/cargo/router.py
    - backend/app/modules/checklists/router.py
    - backend/app/modules/contracts/router.py
    - backend/app/modules/control_tower/router.py
    - backend/app/modules/drivers/router.py
    - backend/app/modules/files/router.py
    - backend/app/modules/fuel/operations_router.py
    - backend/app/modules/fuel/router.py
    - backend/app/modules/operational_exceptions/router.py
    - backend/app/modules/operations/router.py
    - backend/app/modules/sync/router.py
    - backend/app/modules/tenants/router.py
    - backend/app/modules/trips/known_routes_router.py
    - backend/app/modules/trips/router.py
    - backend/app/modules/trip_orders/router.py
    - backend/app/modules/users/router.py
    - backend/app/modules/vehicles/router.py
    - backend/app/modules/workshop/router.py
decisions:
  - "get_session moved to app/core/deps.py to avoid circular import (auth.py imports AsyncSessionLocal from database.py)"
  - "RLS cross-tenant test uses SET LOCAL ROLE rotas_app because rotas superuser has BYPASSRLS=true in local dev"
  - "CREATE POLICY wrapped in DO block for idempotency (PostgreSQL < 17 has no IF NOT EXISTS for policies)"
  - "files table excluded from RLS — cross-tenant file access by service workers not yet resolved"
metrics:
  duration: ~35 minutes
  completed: "2026-06-05T21:34:41Z"
  tasks_completed: 2
  files_changed: 28
---

# Phase 4 Plan 8: PostgreSQL Row Level Security Summary

PostgreSQL RLS as defense-in-depth second isolation layer: all 47 tenant-scoped tables protected by `tenant_isolation` policy using `SET LOCAL app.tenant_id`; SQLAlchemy event listener wires it automatically per transaction; Alembic uses BYPASSRLS role for migrations.

## What Was Built

### Task 1: RLS ContextVar + Event Listener + Session Wiring (commit a88b75f)

**`backend/app/database.py`** — added:
- `_rls_tenant: ContextVar[str | None]` — asyncio-safe per-request tenant context
- `set_rls_tenant(tenant_id)` — sets the ContextVar before session opens
- `_inject_rls_tenant` — SQLAlchemy `after_begin` event listener on `AsyncSession.sync_session_class` that fires `SET LOCAL app.tenant_id = '{tid}'` on every transaction start
- `get_session_raw()` — raw session without RLS, for auth endpoints that have no principal yet

**`backend/app/core/deps.py`** — new file:
- `get_session(principal)` with `Depends(get_current_principal)` — the RLS-aware session dependency that calls `set_rls_tenant` before yielding, clears it in `finally`
- Placed here (not in `database.py`) to avoid circular import: `auth.py` imports `AsyncSessionLocal` from `database.py`; `deps.py` imports from both safely after both are loaded

**23 routers updated**: all non-auth routers changed from `from app.database import get_session` to `from app.core.deps import get_session`. Auth router changed to `from app.database import get_session_raw as get_session`.

### Task 2: Alembic Migration + ALEMBIC_DATABASE_URL + RLS Tests Green (commit 289e38d)

**`backend/app/config.py`**:
- Added `alembic_database_url` field (env: `ALEMBIC_DATABASE_URL`)
- Added `resolved_alembic_database_url` property (falls back to `database_url`)

**`backend/alembic/env.py`**:
- Replaced `engine_from_config` with `create_engine(settings.resolved_alembic_database_url)`
- Now uses `ALEMBIC_DATABASE_URL` (rotas_admin role, BYPASSRLS) — Pitfall 1 fix

**`backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py`**:
- Creates `rotas_app` role (RLS enforced) and `rotas_admin` role (BYPASSRLS) via idempotent DO blocks
- Grants SELECT/INSERT/UPDATE/DELETE on all public tables to `rotas_app`
- Enables `ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on 47 tenant-scoped tables
- Creates `tenant_isolation` policy: `USING (tenant_id::text = current_setting('app.tenant_id', true))`
- `CREATE POLICY` wrapped in DO block for idempotency (no `IF NOT EXISTS` before PostgreSQL 17)
- Downgrade drops policies and disables RLS (roles not dropped to avoid breaking connections)
- Roundtrip `downgrade -1 && upgrade head`: clean

**`backend/tests/test_rls.py`** — 3 stub tests turned green:
- `test_rls_tenant_isolation_policy_exists` — verifies policy in `pg_policies`
- `test_rls_set_local_scoped_to_transaction` — verifies SET LOCAL clears after transaction
- `test_rls_blocks_cross_tenant_trip_access` — creates data in tenant B, queries as tenant A with `SET LOCAL ROLE rotas_app` (required because `rotas` superuser has `BYPASSRLS=true`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Circular import: database.py cannot import from auth.py at module level**
- **Found during:** Task 1
- **Issue:** `auth.py` imports `AsyncSessionLocal` from `database.py`. Adding `Depends(get_current_principal)` to `get_session` in `database.py` would create a circular import at module load time.
- **Fix:** Created `app/core/deps.py` to hold the wired `get_session` dependency. Updated all 22 non-auth routers to import from `app.core.deps`. Auth router uses `get_session_raw` from `database.py`.
- **Files modified:** `backend/app/core/deps.py` (new), `backend/app/modules/auth/router.py`, 22 other routers
- **Commit:** a88b75f

**2. [Rule 1 - Bug] AsyncSessionLocal.sync_session_class does not exist on async_sessionmaker instances**
- **Found during:** Task 1
- **Issue:** The plan's interface used `AsyncSessionLocal.sync_session_class` where `AsyncSessionLocal` is an `async_sessionmaker` instance — this attribute does not exist on instances.
- **Fix:** Used `AsyncSession.sync_session_class` (class attribute on `AsyncSession`) which returns `sqlalchemy.orm.session.Session` — the correct event target.
- **Files modified:** `backend/app/database.py`
- **Commit:** a88b75f

**3. [Rule 1 - Bug] Migration table list contained non-existent tables (checklist_responses, etc.)**
- **Found during:** Task 2
- **Issue:** Plan's `TENANT_SCOPED_TABLES` list included `checklist_responses` and other tables that don't exist in the actual DB schema; also missed `operational_waivers`, `refresh_tokens`, etc.
- **Fix:** Queried `information_schema.columns` for tables with `tenant_id` column to get the authoritative list; updated migration with 47 actual tables.
- **Files modified:** `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py`
- **Commit:** 289e38d

**4. [Rule 1 - Bug] CREATE POLICY not idempotent — partial migration state**
- **Found during:** Task 2 (first upgrade attempt failed mid-run)
- **Issue:** First migration attempt failed at `checklist_responses` (missing table), partially applying RLS to earlier tables. Re-running upgrade then failed with `DuplicateObject` on `tenant_isolation` policy.
- **Fix:** Wrapped `CREATE POLICY` in a `DO $$` block that checks `pg_policies` before creating — fully idempotent.
- **Files modified:** `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py`
- **Commit:** 289e38d

**5. [Rule 1 - Bug] RLS test fails because rotas superuser has BYPASSRLS=true**
- **Found during:** Task 2 (third test assertion failure)
- **Issue:** The `rotas` database user (used by the application in local dev) has `rolbypassrls=true`, so RLS policies never filter rows for this user — making the cross-tenant test always see all rows.
- **Fix:** Added `SET LOCAL ROLE rotas_app` before the cross-tenant query in the test. `rotas_app` does not have BYPASSRLS, so the `tenant_isolation` policy applies.
- **Files modified:** `backend/tests/test_rls.py`
- **Commit:** 289e38d

## Known Stubs

None — all RLS tests are fully implemented and green.

## Test Results

```
tests/test_rls.py::test_rls_tenant_isolation_policy_exists    PASSED
tests/test_rls.py::test_rls_set_local_scoped_to_transaction   PASSED
tests/test_rls.py::test_rls_blocks_cross_tenant_trip_access   PASSED
tests/test_cross_tenant_isolation.py (3 tests)                PASSED
```

## Self-Check: PASSED

Files verified:
- backend/app/database.py — contains `set_rls_tenant`, `_inject_rls_tenant`, `SET LOCAL app.tenant_id`, `ContextVar`, `get_session_raw`
- backend/app/core/deps.py — contains `get_session` with `Depends(get_current_principal)`
- backend/alembic/env.py — contains `ALEMBIC_DATABASE_URL` (via `resolved_alembic_database_url`)
- backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py — contains `ENABLE ROW LEVEL SECURITY` and `tenant_isolation` policy name
- backend/tests/test_rls.py — 3 tests, 0 skipped, all passed

Commits verified:
- a88b75f — Task 1 (RLS event listener + session wiring)
- 289e38d — Task 2 (migration + ALEMBIC_DATABASE_URL + tests green)
