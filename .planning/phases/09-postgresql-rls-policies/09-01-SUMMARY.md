---
phase: 09-postgresql-rls-policies
plan: "01"
subsystem: backend/rls
tags: [rls, security, testing, worker, multitenancy]
dependency_graph:
  requires: []
  provides: [RLS completeness gate test, DB-role isolation test, BYPASSRLS worker session]
  affects: [backend/tests/test_rls.py, backend/app/worker.py]
tech_stack:
  added: []
  patterns:
    - asyncpg direct connection for DB-role-based RLS testing (bypasses SQLAlchemy event listeners)
    - resolved_admin_database_url fallback pattern for BYPASSRLS worker sessions
key_files:
  modified:
    - backend/tests/test_rls.py
    - backend/app/worker.py
decisions:
  - "ARQ worker uses resolved_admin_database_url (rotas_admin BYPASSRLS) not AsyncSessionLocal (rotas_app RLS-scoped)"
  - "RLS completeness test intentionally RED until plan 09-02 adds export_jobs policy"
  - "DB-role isolation test uses asyncpg direct connect to activate rotas_app role context explicitly"
  - "pytest.skip guards gracefully when rotas_app role is absent (local dev without init SQL)"
metrics:
  duration: "~8 minutes"
  completed: "2026-06-07"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 2
---

# Phase 9 Plan 01: RLS Pre-flight Verification and Patch Summary

**One-liner:** Patched ARQ worker to use BYPASSRLS admin DB URL and added two RLS test functions — a 47-table completeness gate (intentionally RED for export_jobs) and a DB-role-based cross-tenant vehicle isolation proof.

---

## What Was Done

### Task 1 — test_rls_all_tenant_tables_have_policy (commit 8535f23)

Added `test_rls_all_tenant_tables_have_policy` to `backend/tests/test_rls.py`.

The test defines `EXPECTED_RLS_TABLES` (47 tables: the 46 from migration `4b0a7802dc3c_add_rls_policies` plus `export_jobs` which will be added by the plan 09-02 gap-closure migration). It:

1. Queries `pg_policies WHERE policyname = 'tenant_isolation'` and compares the result against `EXPECTED_RLS_TABLES`.
2. Runs a cross-check gap query (`information_schema.columns WHERE column_name='tenant_id' EXCEPT pg_policies WHERE policyname='tenant_isolation'`) and asserts the only rows returned are `{"tenants", "files"}` (the two documented intentional exclusions).

**Expected state:** RED until plan 09-02 applies — `export_jobs` has a `tenant_id` column but no RLS policy yet. The failure message explicitly lists the missing table, making the gap visible and auditable.

### Task 2 — worker.py BYPASSRLS fix (commit 6db8f97)

Replaced the `startup()` body in `backend/app/worker.py`. Previously:

```python
from app.database import AsyncSessionLocal
ctx["db_factory"] = AsyncSessionLocal  # rotas_app role — subject to RLS
```

Now:

```python
admin_engine = create_async_engine(_settings.resolved_admin_database_url, pool_pre_ping=True)
ctx["db_factory"] = async_sessionmaker(admin_engine, expire_on_commit=False)
ctx["admin_engine"] = admin_engine
```

`shutdown()` now disposes the engine:

```python
if "admin_engine" in ctx:
    await ctx["admin_engine"].dispose()
```

`resolved_admin_database_url` falls back to `database_url` when `ADMIN_DATABASE_URL` is not set — no local dev config change required. All existing `generate_billing_export` tenant filters (`BillingDocument.tenant_id == UUID(tenant_id)`) are preserved per CLAUDE.md: "never remove tenant_id filter in optimizations".

### Task 3 — test_rls_blocks_cross_tenant_vehicle_access (commit df43c42)

Added `test_rls_blocks_cross_tenant_vehicle_access` to `backend/tests/test_rls.py`.

The test:
1. Creates tenant_A and tenant_B plus one vehicle for tenant_A using the admin SQLAlchemy session (BYPASSRLS — setup only).
2. Builds a `rotas_app` DSN from `settings.database_url` by substituting credentials (`rotas_app:rotas_app_dev`).
3. Connects via `asyncpg` directly (bypassing SQLAlchemy event listeners so `SET ROLE` behaviour is fully explicit).
4. Within a transaction: `SET LOCAL app.tenant_id = '<tenant_B_id>'` then `SELECT * FROM vehicles` with **no WHERE clause**.
5. Asserts tenant_A's vehicle is not in the result — proving the `tenant_isolation` policy filters at the PostgreSQL layer.
6. Wraps the asyncpg connect in `try/except` and calls `pytest.skip(...)` if the `rotas_app` role is unavailable.

**Expected state:** RED until plan 09-02 migration enables `ENABLE ROW LEVEL SECURITY; FORCE ROW LEVEL SECURITY` on the vehicles table (already covered by migration `4b0a7802dc3c` if it has run against the test DB). Will turn GREEN once the RLS migration is applied.

---

## Deviations from Plan

None — plan executed exactly as written.

---

## Known Stubs

None. No placeholder data or hardcoded empty values introduced.

---

## Self-Check: PASSED

- `backend/tests/test_rls.py` exists and contains all required functions
- `backend/app/worker.py` imports cleanly: `from app.worker import WorkerSettings` succeeds
- Commits verified:
  - `8535f23` — test_rls_all_tenant_tables_have_policy
  - `6db8f97` — worker BYPASSRLS patch
  - `df43c42` — test_rls_blocks_cross_tenant_vehicle_access
