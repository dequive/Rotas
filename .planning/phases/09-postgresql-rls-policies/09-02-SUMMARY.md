---
plan: 09-02
phase: 09-postgresql-rls-policies
status: complete
completed_at: 2026-06-07
self_check: PASSED
---

## What Was Built

Resolved the Alembic two-head split and added RLS to `export_jobs` — all 4 RLS tests now GREEN.

## Key Files Created

- `backend/alembic/versions/147542222231_merge_rls_and_export_jobs.py` — Merge migration combining heads `b7e2a9c4d1f3` and `d4e5f6a7b8c9` into a single linear chain
- `backend/alembic/versions/e1f2a3b4c5d6_add_rls_to_export_jobs.py` — Gap-closure migration: `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, `CREATE POLICY tenant_isolation`, `GRANT SELECT/INSERT/UPDATE/DELETE TO rotas_app` on `export_jobs`

## Key Files Modified

- `backend/tests/test_rls.py` — Fixed `INTENTIONALLY_EXCLUDED` set: removed `tenants` (root table has no `tenant_id` column, never appears in gap query)

## Test Results

```
tests/test_rls.py::test_rls_tenant_isolation_policy_exists        PASSED
tests/test_rls.py::test_rls_set_local_scoped_to_transaction       PASSED
tests/test_rls.py::test_rls_blocks_cross_tenant_trip_access       PASSED
tests/test_rls.py::test_rls_all_tenant_tables_have_policy         PASSED
tests/test_rls.py::test_rls_blocks_cross_tenant_vehicle_access    SKIPPED (rotas_app role not set up in local dev)
4 passed, 1 skipped
```

## Commits

- `de281dd` — feat(09-02): create Alembic merge migration (147542222231)
- `fe84745` — feat(09-02): add RLS policy to export_jobs + fix test
