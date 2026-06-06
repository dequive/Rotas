# Phase 9: PostgreSQL RLS Policies — Research

**Researched:** 2026-06-06
**Domain:** PostgreSQL Row Level Security, SQLAlchemy async, Alembic, Railway deployment
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RLS-01 | All 47+ tables with `tenant_id` have ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY + CREATE POLICY using `current_setting('app.tenant_id')` | Alembic migration `4b0a7802dc3c` already exists and covers 44 tenant-scoped tables with this exact pattern |
| RLS-02 | Roles `rotas_app` (RLS enforced) and `rotas_admin` (BYPASSRLS) created and configured in Railway and docker-compose | Role creation already in the migration; `ALEMBIC_DATABASE_URL` and `ADMIN_DATABASE_URL` fields already in `Settings`; need Railway config confirmation |
| RLS-03 | Cross-tenant test suite passes under `rotas_app` role — tenant A data invisible when session `app.tenant_id` is set to tenant B's ID, with no explicit WHERE filter | `test_rls.py` already exists with `SET LOCAL ROLE rotas_app` pattern; test verifies trip isolation |
</phase_requirements>

---

## Critical Discovery: Phase 9 Is Largely Pre-Implemented

**This is the most important finding.** Phase 9 work was partially executed as plan `04-08-PLAN.md` from Phase 4. The following components already exist in the codebase:

### Already Implemented

| Component | File | Status |
|-----------|------|--------|
| Alembic RLS migration | `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` | EXISTS — covers 44 tables |
| `set_rls_tenant()` function | `backend/app/database.py` | EXISTS — ContextVar-based |
| `after_begin` event listener | `backend/app/database.py` | EXISTS — uses `SET LOCAL` correctly |
| `get_session()` with RLS injection | `backend/app/core/deps.py` | EXISTS — sets+clears tenant ContextVar |
| `get_session_raw()` bypass | `backend/app/database.py` | EXISTS — used by auth endpoints |
| `ALEMBIC_DATABASE_URL` config field | `backend/app/config.py` | EXISTS — `resolved_alembic_database_url` property |
| `ADMIN_DATABASE_URL` config field | `backend/app/config.py` | EXISTS — `resolved_admin_database_url` property |
| Alembic env.py using admin URL | `backend/alembic/env.py` | EXISTS — replaces `+asyncpg` with `+psycopg` |
| RLS test file | `backend/tests/test_rls.py` | EXISTS — 3 tests including cross-tenant isolation |
| Cross-tenant app-layer tests | `backend/tests/test_cross_tenant_isolation.py` | EXISTS |

### What Remains To Be Verified / Completed

1. **Table count gap**: The migration covers 44 tables but the requirement says 47+. The roadmap decisions explicitly note `files` is excluded (cross-tenant file service access pattern). The actual gap must be verified by running `SELECT count(*) FROM pg_policies WHERE policyname = 'tenant_isolation'` against the database.

2. **`export_jobs` table**: Added in migration `d4e5f6a7b8c9_add_export_jobs_table.py` — has `tenant_id` but may not be in the RLS migration's `TENANT_SCOPED_TABLES` list. Must be verified.

3. **`checklist_responses` table**: Referenced in the roadmap architecture but not visible in the initial schema migration. Check if it exists and whether it has `tenant_id`.

4. **Railway environment variables**: `ALEMBIC_DATABASE_URL` and `ADMIN_DATABASE_URL` must be configured in Railway before migration runs. This is a deployment task, not a code task.

5. **`rotas_app` login credentials**: The `rotas_app` and `rotas_admin` roles are created by the migration, but they need passwords set and connection strings configured (`postgresql+asyncpg://rotas_app:<password>@host/db`).

6. **Confirmation gate**: After migration, `SELECT count(*) FROM pg_policies WHERE policyname = 'tenant_isolation'` must return 44+ (or 47+ after verifying the actual tenant table count).

7. **`test_rls.py` requires live PostgreSQL**: The RLS cross-tenant test uses `SET LOCAL ROLE rotas_app` which only works if the `rotas_app` role exists in the test database. The test will fail in CI if the test DB hasn't had the RLS migration applied.

---

## Standard Stack

### Core (all already in use)

| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| PostgreSQL | 16 (Railway) | RLS enforcement | Configured |
| SQLAlchemy asyncio | >=2.0 | `after_begin` event for `SET LOCAL` | In use |
| asyncpg | >=0.29 | Async PG driver | In use |
| psycopg[binary] | >=3.1 | Sync driver for Alembic | In use |
| Alembic | >=1.13 | Migration runner | In use |

### Key PostgreSQL RLS DDL

```sql
-- Role creation (idempotent via DO block)
DO $$ BEGIN CREATE ROLE rotas_app; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE rotas_admin BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Per-table RLS (already in migration 4b0a7802dc3c)
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- Inject tenant context (already in database.py after_begin listener)
SET LOCAL app.tenant_id = '{tenant_id}';
```

---

## Architecture Patterns

### Pattern 1: SET LOCAL for Pool-Safe Tenant Injection (ALREADY IMPLEMENTED)

The `after_begin` event listener in `database.py` uses `SET LOCAL`, not `SET`. This is the critical decision that prevents tenant context from leaking across pooled asyncpg connections.

```python
# Source: backend/app/database.py (already implemented correctly)
@event.listens_for(AsyncSession.sync_session_class, "after_begin")
def _inject_rls_tenant(session, transaction, connection):
    tid = _rls_tenant.get()
    if tid is not None:
        connection.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
```

`SET LOCAL` is scoped to the current transaction. When the transaction ends (commit or rollback), the setting is automatically cleared. This is verified by `test_rls_set_local_scoped_to_transaction` in `test_rls.py`.

### Pattern 2: ContextVar for Asyncio-Safe Tenant Propagation (ALREADY IMPLEMENTED)

```python
# Source: backend/app/database.py (already implemented correctly)
_rls_tenant: ContextVar[str | None] = ContextVar("_rls_tenant", default=None)
```

`ContextVar` is asyncio-safe: each coroutine has its own copy. The `get_session()` dependency in `deps.py` calls `set_rls_tenant(str(principal.tenant_id))` before yielding the session and clears it in `finally`. This ensures every request operates under the correct tenant context.

### Pattern 3: Role Separation for Alembic and ARQ (ALREADY IMPLEMENTED IN CODE)

```
DATABASE_URL         → rotas_app role  → subject to RLS (FastAPI application)
ALEMBIC_DATABASE_URL → rotas_admin role → BYPASSRLS (Alembic migrations)  
ADMIN_DATABASE_URL   → rotas_admin role → BYPASSRLS (ARQ worker cross-tenant jobs)
```

Alembic `env.py` already reads `settings.resolved_alembic_database_url` and replaces `+asyncpg` with `+psycopg` for the sync Alembic driver.

### Pattern 4: New Table RLS at CREATE Time (FORWARD-LOOKING CONSTRAINT)

Every v2.0 table that has `tenant_id` (clients, client_payments, payment_allocations, driver_advances, trip_settlements, gps_positions, gps_devices, vehicle_last_position, tracking_tokens) MUST include `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY` + `GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app` in the same Alembic migration that creates the table. NOT as a follow-up patch.

```python
# Pattern for all v2.0 CREATE TABLE migrations:
op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
op.execute("""
    CREATE POLICY tenant_isolation ON clients
    USING (tenant_id::text = current_setting('app.tenant_id', true))
""")
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON clients TO rotas_app")
op.execute("GRANT USAGE ON SEQUENCE clients_id_seq TO rotas_app")  -- if applicable
```

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-request tenant leakage | Custom connection wrapper | `SET LOCAL` in `after_begin` event | Already implemented; `SET` (not LOCAL) silently corrupts next request |
| Role-aware connection strings | Custom connection pool per role | Three distinct `DATABASE_URL` env vars | Alembic and ARQ need BYPASSRLS; mixing into single pool is unsafe |
| Policy idempotency | Track applied policies in code | `DO $$ IF NOT EXISTS SELECT ... THEN EXECUTE 'CREATE POLICY...' $$` | Already in migration; `CREATE POLICY IF NOT EXISTS` only available in PG 17+ |
| Tenant ID type mismatch | Custom casting logic | `tenant_id::text = current_setting(...)` | `current_setting` returns text; UUID column requires explicit cast |

---

## Common Pitfalls

### Pitfall 1: SET vs SET LOCAL (MITIGATED — already using SET LOCAL)
**What goes wrong:** Using `SET app.tenant_id = X` instead of `SET LOCAL` on a pooled asyncpg connection. The setting persists on the connection after the transaction ends. The next request reusing that connection executes under the wrong tenant with no error.
**Status:** Already mitigated — `database.py` uses `SET LOCAL` and has a comment explaining why. `test_rls_set_local_scoped_to_transaction` verifies this behavior.

### Pitfall 2: Alembic Blocked by Its Own RLS Migration (MITIGATED — ALEMBIC_DATABASE_URL exists)
**What goes wrong:** Once RLS is enabled on all tenant tables, Alembic connecting as `rotas_app` cannot read `alembic_version` or `pg_policies` without `app.tenant_id` set — blocking all future migrations.
**Status:** Already mitigated — `alembic/env.py` uses `ALEMBIC_DATABASE_URL` which connects as `rotas_admin` (BYPASSRLS). However, the Railway deployment must have this env var set BEFORE the RLS migration runs. This is the key deployment task.

### Pitfall 3: ARQ Worker Cross-Tenant Queries Blocked by RLS
**What goes wrong:** ARQ background jobs (KPI refresh, PDF generation, maintenance scheduler) query across tenants (e.g., "find all vehicles with expiring documents"). Under `rotas_app` role with RLS active, these queries return empty results because no `app.tenant_id` is set.
**Status:** `ADMIN_DATABASE_URL` field exists in config but the ARQ worker startup may not use it yet. The planner must verify that the ARQ worker in `backend/app/worker.py` (or equivalent) creates its database engine using `settings.resolved_admin_database_url`.

### Pitfall 4: `export_jobs` Table Not in RLS Migration
**What goes wrong:** `export_jobs` table (added in migration `d4e5f6a7b8c9`) has a `tenant_id` column but is not in the `TENANT_SCOPED_TABLES` list in migration `4b0a7802dc3c`. Under `rotas_app`, a query like `SELECT * FROM export_jobs WHERE ...` would return rows from all tenants.
**Status:** NEEDS VERIFICATION. The planner must check the actual `TENANT_SCOPED_TABLES` list and cross-reference against all tables with `tenant_id`. A supplementary Alembic migration may be needed for tables added after `4b0a7802dc3c`.

### Pitfall 5: `files` Table Excluded From RLS — By Design
**What goes wrong:** The `files` table has `tenant_id` but was explicitly excluded from the RLS migration (comment in the migration: "accessed cross-tenant by the file service for uploads"). Adding RLS to `files` would break `GET /api/v1/files/upload` which currently resolves file ownership post-upload.
**Status:** Documented exclusion. The planner should not add RLS to `files` in Phase 9. This is a known design decision in the migration code.

### Pitfall 6: `test_rls.py` Tests Fail Without Live PostgreSQL + Roles
**What goes wrong:** `test_rls_blocks_cross_tenant_trip_access` uses `SET LOCAL ROLE rotas_app`. If the test database doesn't have the `rotas_app` role (i.e., the RLS migration hasn't run), this test fails with `ERROR: role "rotas_app" does not exist`.
**Status:** Tests are written correctly. The test infrastructure must have the RLS migration applied. In CI/CD, the Railway dev database must have `rotas_app` role. For local dev, `docker-compose up` spins up PostgreSQL where the migration creates the role.

### Pitfall 7: `GRANT` on New Tables Required After RLS Enabled
**What goes wrong:** New tables created after the RLS migration was run have no `GRANT` for `rotas_app`. The `rotas_app` role cannot insert/update/delete rows even though the RLS policy is set.
**Status:** The migration already runs `GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rotas_app` — but this applies only to tables existing at migration time. For v2.0 tables (clients, payments, etc.) created in Phases 5-12, each CREATE TABLE migration must include its own `GRANT ... TO rotas_app`.

---

## Code Examples

### Verify RLS Policy Coverage (Confirmation Gate)
```sql
-- Source: Phase 9 architecture constraints (ROADMAP.md)
-- Run after migration completes:
SELECT tablename, policyname, cmd, qual
FROM pg_policies
WHERE policyname = 'tenant_isolation'
ORDER BY tablename;

-- Count should match expected tenant-scoped table count:
SELECT count(*) FROM pg_policies WHERE policyname = 'tenant_isolation';

-- Cross-check: tables with tenant_id that don't have a policy:
SELECT table_name
FROM information_schema.columns
WHERE column_name = 'tenant_id'
  AND table_schema = 'public'
EXCEPT
SELECT tablename
FROM pg_policies
WHERE policyname = 'tenant_isolation';
-- Should return only: tenants, files (the intentional exclusions)
```

### Check ARQ Worker Uses Admin URL
```python
# Source: pattern from config.py resolved_admin_database_url
# In backend/app/worker.py (or wherever ARQ worker creates its engine):
from app.config import get_settings
settings = get_settings()
admin_engine = create_async_engine(settings.resolved_admin_database_url, ...)
```

### New Table RLS Template (For Phases 5-12)
```python
# Source: established pattern from 4b0a7802dc3c migration
# Add this block to every CREATE TABLE migration for v2.0 tables:
def upgrade() -> None:
    op.create_table('clients', ...)
    
    # RLS — must be in same migration as CREATE TABLE
    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON clients "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON clients TO rotas_app")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| App-layer tenant_id filtering only | PostgreSQL RLS + app-layer (defense in depth) | Phase 4/9 | Cross-tenant leak impossible even if WHERE clause accidentally removed |
| `SET app.tenant_id` (session-scoped) | `SET LOCAL app.tenant_id` (transaction-scoped) | Phase 4 implementation | Pool-safe; no tenant leakage across pooled connections |
| Single DATABASE_URL | Three URLs: DATABASE_URL / ALEMBIC_DATABASE_URL / ADMIN_DATABASE_URL | Phase 4 implementation | Alembic and ARQ use BYPASSRLS role; app uses RLS-enforced role |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL (local) | RLS migration, test_rls.py | ✓ (docker-compose) | 16 | — |
| Railway PostgreSQL | Production migration | Needs verification | 16 | — |
| `rotas_app` PG role | test_rls.py, production | Must be created by migration | — | Migration creates it |
| `rotas_admin` PG role | Alembic, ARQ | Must be created by migration | — | Migration creates it |
| ALEMBIC_DATABASE_URL | Railway production deploy | Not yet set in Railway | — | Falls back to DATABASE_URL (unsafe after RLS) |
| ADMIN_DATABASE_URL | ARQ worker | Not yet set in Railway | — | Falls back to DATABASE_URL (breaks ARQ) |

**Missing dependencies with no fallback:**
- `ALEMBIC_DATABASE_URL` in Railway — must be configured before the RLS migration deploy runs. If DATABASE_URL connects as `rotas_app` after the migration, Alembic will be blocked on all future migrations.
- `ADMIN_DATABASE_URL` in Railway — must be configured before Phase 9 closes. ARQ background jobs querying across tenants will silently return empty results.

**Configuration action required before execution:**
Railway must have `DATABASE_URL` use `rotas_app` credentials and `ALEMBIC_DATABASE_URL` / `ADMIN_DATABASE_URL` use `rotas_admin` credentials. The roles themselves are created by the migration — but passwords must be set on those roles post-migration: `ALTER ROLE rotas_app PASSWORD 'xxx'; ALTER ROLE rotas_admin PASSWORD 'xxx';`

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio 0.23 (`asyncio_mode = "auto"`) |
| Config file | `backend/pyproject.toml` (pytest section) |
| Quick run command | `cd backend && pytest tests/test_rls.py -x -v` |
| Full suite command | `cd backend && pytest tests/test_rls.py tests/test_cross_tenant_isolation.py -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RLS-01 | tenant_isolation policy exists on trips table | integration | `pytest tests/test_rls.py::test_rls_tenant_isolation_policy_exists -x` | ✅ |
| RLS-01 | SET LOCAL is transaction-scoped (not session) | integration | `pytest tests/test_rls.py::test_rls_set_local_scoped_to_transaction -x` | ✅ |
| RLS-01 | Confirmation gate: count of policies matches expected | SQL query | Manual SQL: `SELECT count(*) FROM pg_policies WHERE policyname='tenant_isolation'` | Manual only |
| RLS-02 | ALEMBIC_DATABASE_URL configured and Alembic runs clean | deployment | `alembic upgrade head` (Railway deploy log) | Deploy-time |
| RLS-02 | ADMIN_DATABASE_URL resolves to rotas_admin | smoke | `pytest tests/test_rls.py -x` (indirectly) | ✅ |
| RLS-03 | Cross-tenant trip access blocked under rotas_app role | integration | `pytest tests/test_rls.py::test_rls_blocks_cross_tenant_trip_access -x` | ✅ |
| RLS-03 | Cross-tenant vehicle/driver access blocked (app layer) | integration | `pytest tests/test_cross_tenant_isolation.py -x` | ✅ |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/test_rls.py -x -v`
- **Per wave merge:** `cd backend && pytest tests/test_rls.py tests/test_cross_tenant_isolation.py -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None — existing `test_rls.py` and `test_cross_tenant_isolation.py` cover all three requirements. However, the test for RLS-01 completeness (all 47+ tables covered) requires a SQL query, not an automated test. The planner should add a test that queries `pg_policies` count and compares it against the expected table list.

- [ ] `tests/test_rls.py::test_rls_all_tenant_tables_have_policy` — covers RLS-01 completeness gate (count of policies = expected count of tenant-scoped tables)

---

## Open Questions

1. **What is the actual count of tenant-scoped tables?**
   - What we know: The migration lists 44 tables. The requirement says 47+. The difference may be `export_jobs` (added in a later migration) plus other tables added after the initial schema.
   - What's unclear: Whether `export_jobs`, `checklist_responses`, and any Phase 3/4 additions are in the migration or missing.
   - Recommendation: The Wave 0 plan task should run the cross-check SQL query (tables with tenant_id minus tables with tenant_isolation policy) against the local dev database to identify any gaps before writing the Phase 9 migration.

2. **Does the ARQ worker already use `ADMIN_DATABASE_URL`?**
   - What we know: The config field `resolved_admin_database_url` exists. The migration and `get_session()` are wired correctly.
   - What's unclear: Whether `backend/app/worker.py` (the ARQ worker entry point) creates its engine from `admin_database_url` or `database_url`.
   - Recommendation: The planner should inspect `backend/app/worker.py` as the first task and patch it if it uses the wrong URL.

3. **Do role passwords need to be set separately in Railway?**
   - What we know: The migration creates `rotas_app` and `rotas_admin` roles without passwords. PostgreSQL allows passwordless roles but Railway connection strings require a password.
   - What's unclear: Whether Railway's PostgreSQL allows password-less role connections or requires explicit `ALTER ROLE ... PASSWORD '...'`.
   - Recommendation: The deployment task must include `ALTER ROLE rotas_app PASSWORD '...'; ALTER ROLE rotas_admin PASSWORD '...'` as a one-time admin SQL command in Railway's database console, or in the migration itself.

---

## Project Constraints (from CLAUDE.md)

- **Tech stack**: FastAPI + Next.js + Vite/React + PostgreSQL — do not change
- **Multitenant safety**: Every query must filter by `tenant_id` — never remove that filter in optimizations (RLS is defense-in-depth ON TOP of this, not a replacement)
- **GSD workflow**: All code changes must go through `/gsd:execute-phase` — no direct repo edits
- **Design system**: `DESIGN.md` must be read before any visual changes — not applicable to Phase 9 (no UI)

---

## Sources

### Primary (HIGH confidence)
- `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` — actual RLS migration already in codebase
- `backend/app/database.py` — SET LOCAL implementation, ContextVar pattern, after_begin event
- `backend/app/core/deps.py` — get_session with tenant injection
- `backend/app/config.py` — ALEMBIC_DATABASE_URL, ADMIN_DATABASE_URL fields
- `backend/alembic/env.py` — ALEMBIC_DATABASE_URL usage in migrations
- `backend/tests/test_rls.py` — existing test suite for RLS
- `.planning/ROADMAP.md` Phase 9 architecture constraints — locked decisions

### Secondary (MEDIUM confidence)
- `.planning/STATE.md` Key Decisions table — documents SET LOCAL choice, three-URL pattern
- PostgreSQL 16 docs on `current_setting('app.tenant_id', true)` — the `true` arg returns NULL on missing setting (no error), confirmed by migration comment

### Tertiary (LOW confidence)
- Railway PostgreSQL role password requirement — not verified against Railway docs; assumption based on standard PG connection string behavior

---

## Metadata

**Confidence breakdown:**
- What exists in codebase: HIGH — directly read source files
- What needs Railway config: MEDIUM — config fields exist in code, Railway side unverified
- Table count gap: MEDIUM — migration lists 44, requirement says 47+, need SQL query to confirm
- ARQ worker admin URL: MEDIUM — config property exists, worker usage unverified

**Research date:** 2026-06-06
**Valid until:** 2026-07-06 (stable domain, no fast-moving dependencies)
