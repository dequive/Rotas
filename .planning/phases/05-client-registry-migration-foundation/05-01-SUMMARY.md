---
phase: 05
plan: 01
subsystem: clients
tags: [backend, fastapi, sqlalchemy, alembic, rls, crud]
one_liner: "Clients module end-to-end: SQLAlchemy model, Alembic migration (a) with RLS, service CRUD, FastAPI router, 6 passing tests"

dependency_graph:
  requires: []
  provides:
    - "Client SQLAlchemy model (backend/app/modules/clients/models.py)"
    - "CRUD service: list_clients, get_client_with_balance, create_client, patch_client, serialize_client"
    - "Router: GET/POST /api/v1/clients, GET/PATCH /api/v1/clients/{id}"
    - "Migration a2b3c4d5e6f7: clients table + RLS tenant_isolation policy + GRANT rotas_app"
  affects:
    - "backend/app/database.py — MODEL_MODULES extended"
    - "backend/app/main.py — clients router registered"
    - "backend/tests/conftest.py — client_payload fixture added"

tech_stack:
  added: []
  patterns:
    - "serialize_client() decouples ORM from response shape — consistent with vehicle/driver modules"
    - "IntegrityError → ApiError(nuit_already_exists, 409) — matches contracts pattern"
    - "RLS + GRANT in same CREATE TABLE migration — CLAUDE.md v2.0 Migration Rules enforced"
    - "outstanding_balance interim stub (returns 0) documented in code; Plan 02 will wire client_id FK"

key_files:
  created:
    - backend/app/modules/clients/__init__.py
    - backend/app/modules/clients/models.py
    - backend/app/modules/clients/schemas.py
    - backend/app/modules/clients/service.py
    - backend/app/modules/clients/router.py
    - backend/alembic/versions/a2b3c4d5e6f7_add_clients_table.py
    - backend/alembic/versions/22fbf8416463_merge_clients_and_workshop_expansion.py
    - backend/tests/test_clients_api.py
  modified:
    - backend/app/database.py
    - backend/app/main.py
    - backend/tests/conftest.py

decisions:
  - "Used revision ID a2b3c4d5e6f7 (not the plan-specified a1b2c3d4e5f6, which is taken by add_waiver_status_pending_approval)"
  - "Created merge migration 22fbf8416463 to join clients head with pre-existing workshop_expansion head (a8f3b2c1d4e5) — both diverged from f4c8a12d9b30"
  - "_get_outstanding_balance returns Decimal('0.00') in Phase 5 Plan 01 — BillingDocument.client_id FK does not exist until Plan 02; documented as known stub with clear Plan 02 upgrade path"
  - "outstanding_balance_estimate: true flag in serialize_client alerts API consumers that balance is not yet accurate"

metrics:
  duration_seconds: 569
  completed_date: "2026-06-19"
  tasks_completed: 2
  tasks_total: 2
  files_created: 9
  files_modified: 3
---

# Phase 5 Plan 01: Clients Backend — Model, Migration (a), Service, Router — Summary

Clients module built end-to-end in one plan: SQLAlchemy model with NUIT-per-tenant uniqueness constraint, Alembic migration (a) with RLS policy and GRANT, Pydantic schemas with NUIT regex validation, service layer with tenant-scoped CRUD, and FastAPI router registered at `/api/v1/clients`. 6 tests pass covering all CLI-01 requirements; 1 CLI-03 stub remains skipped pending Plan 02 backfill.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Wave 0 — test stubs and clients module skeleton | 73931b1 | clients/__init__.py, test_clients_api.py, conftest.py |
| 2 | Clients module — model, migration (a), service, router, tests | b97c206 | models.py, schemas.py, service.py, router.py, migration a2b3c4d5e6f7, merge 22fbf8416463, database.py, main.py, test_clients_api.py |

## Verification Results

```
tests/test_clients_api.py::test_create_client PASSED
tests/test_clients_api.py::test_create_client_duplicate_nuit PASSED
tests/test_clients_api.py::test_list_clients_tenant_scoped PASSED
tests/test_clients_api.py::test_patch_client_deactivate PASSED
tests/test_clients_api.py::test_client_cross_tenant_isolation PASSED
tests/test_clients_api.py::test_credit_limit_warning_thresholds PASSED
tests/test_clients_api.py::test_backfill_zero_null_client_ids SKIPPED (post-migration)

6 passed, 1 skipped
```

Migration `a2b3c4d5e6f7` applied successfully. `clients` table has:
- `ENABLE ROW LEVEL SECURITY`
- `FORCE ROW LEVEL SECURITY`
- `CREATE POLICY tenant_isolation ON clients USING (tenant_id::text = current_setting('app.tenant_id', true))`
- `GRANT SELECT, INSERT, UPDATE, DELETE ON clients TO rotas_app`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migration revision ID collision**
- **Found during:** Task 2
- **Issue:** Plan specified `a1b2c3d4e5f6` as the revision ID for the clients migration, but this ID is already in use by `a1b2c3d4e5f6_add_waiver_status_pending_approval.py`
- **Fix:** Used `a2b3c4d5e6f7` as the revision ID instead
- **Files modified:** `backend/alembic/versions/a2b3c4d5e6f7_add_clients_table.py`
- **Commit:** b97c206

**2. [Rule 3 - Blocking] Multiple Alembic heads after migration creation**
- **Found during:** Task 2 verification (alembic upgrade head)
- **Issue:** A pre-existing untracked migration `a8f3b2c1d4e5_add_workshop_expansion.py` also pointed to `f4c8a12d9b30` as its `down_revision`, creating two heads
- **Fix:** Generated merge migration `22fbf8416463_merge_clients_and_workshop_expansion.py` via `alembic merge`; `alembic upgrade head` then succeeded
- **Files modified:** `backend/alembic/versions/22fbf8416463_merge_clients_and_workshop_expansion.py`
- **Commit:** b97c206

**3. [Rule 2 - Missing critical functionality] outstanding_balance interim stub**
- **Found during:** Task 2 service implementation
- **Issue:** Plan calls for `_get_outstanding_balance` to query `BillingDocument.client_id`, but `client_id` FK on `billing_documents` is not added until Plan 02 migration (b). Importing a non-existent column would cause runtime errors.
- **Fix:** `_get_outstanding_balance` returns `Decimal("0.00")` with detailed docstring explaining the Plan 02 upgrade path. `outstanding_balance_estimate: True` flag in serializer signals to API consumers that value is interim.
- **Files modified:** `backend/app/modules/clients/service.py`
- **Commit:** b97c206

## Known Stubs

| Stub | File | Reason |
|------|------|--------|
| `_get_outstanding_balance` always returns 0 | `backend/app/modules/clients/service.py` | `BillingDocument.client_id` FK added in Plan 02; documented with upgrade instructions |
| `test_backfill_zero_null_client_ids` skipped | `backend/tests/test_clients_api.py` | Post-migration assertion for Plan 02 (c) backfill — intentional per plan spec |

These stubs do not block the plan's goal (Client CRUD working end-to-end). Plan 02 will wire the FK and update `_get_outstanding_balance` with the real query.

## Self-Check: PASSED
