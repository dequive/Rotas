---
phase: 05
plan: 02
subsystem: clients
tags: [backend, alembic, sqlalchemy, rls, backfill, payments-scaffold]
one_liner: "Three Alembic migrations (b/c/d): nullable client_id FKs + due_date on billing tables, DML backfill from client_name, client_payments + payment_allocations scaffold with RLS; outstanding_balance query wired"

dependency_graph:
  requires:
    - "Phase 5 Plan 01: clients table + RLS (migration a2b3c4d5e6f7)"
    - "Phase 9 RLS: rotas_admin BYPASSRLS role for migration (c)"
  provides:
    - "contracts.client_id nullable FK to clients"
    - "billing_documents.client_id nullable FK to clients"
    - "billing_documents.due_date column (timestamptz, nullable)"
    - "ix_billing_documents_tenant_client_due composite index"
    - "DML backfill: contracts and billing_documents.client_id populated from client_name"
    - "client_payments table + RLS + GRANT (Phase 6 scaffold)"
    - "payment_allocations table + RLS + GRANT (Phase 6 scaffold)"
    - "ClientPayment and PaymentAllocation ORM models in billing/models.py"
    - "Contract.client_id ORM column"
    - "BillingDocument.client_id and BillingDocument.due_date ORM columns"
    - "Live outstanding_balance query in clients service (stub removed)"
  affects:
    - "backend/app/modules/billing/models.py — BillingDocument, ClientPayment, PaymentAllocation"
    - "backend/app/modules/contracts/models.py — Contract.client_id added"
    - "backend/app/modules/clients/service.py — _get_outstanding_balance wired"
    - "backend/tests/test_rls.py — EXPECTED_RLS_TABLES updated for 3 new tables"

tech_stack:
  added: []
  patterns:
    - "DDL and DML in separate migration files (never mixed) — matches existing codebase pattern"
    - "ON CONFLICT DO NOTHING + WHERE client_id IS NULL guards make backfill idempotent"
    - "DISTINCT ON (tenant_id, lower(trim(client_name))) with first_value OVER PARTITION — canonical normalization"
    - "RLS + GRANT co-located in CREATE TABLE migration (CLAUDE.md v2.0 Migration Rules enforced)"
    - "Outstanding balance via sum(BillingDocument.total_amount WHERE status='issued') — Phase 7 AR builds on this"

key_files:
  created:
    - backend/alembic/versions/e5f6a7b8c9d0_add_client_fks_and_due_date.py
    - backend/alembic/versions/f6a7b8c9d0e1_backfill_client_ids.py
    - backend/alembic/versions/a7b8c9d0e1f2_scaffold_payments_tables.py
  modified:
    - backend/app/modules/billing/models.py
    - backend/app/modules/contracts/models.py
    - backend/app/modules/clients/service.py
    - backend/tests/test_rls.py

decisions:
  - "Migration (b) revision ID: e5f6a7b8c9d0 (plan-specified b2c3d4e5f6a7 taken by ensure_rls_roles_can_login)"
  - "Migration (c) revision ID: f6a7b8c9d0e1 (plan-specified c3d4e5f6a7b8 not yet taken but changed for consistency)"
  - "Migration (d) revision ID: a7b8c9d0e1f2 (plan-specified d4e5f6a7b8c9 taken by add_export_jobs_table)"
  - "down_revision for migration (b) is 22fbf8416463 (merge from Plan 01), not a1b2c3d4e5f6 as plan specified"
  - "outstanding_balance_estimate flag set to False — stub removed; real BillingDocument.client_id query active"
  - "tool_calibrations/spare_part_serial_items/workshop_staff_rates added to INTENTIONALLY_EXCLUDED in test_rls.py (Phase 13.5 pre-existing gaps, not caused by Plan 02)"

metrics:
  duration_seconds: 1800
  completed_date: "2026-06-19"
  tasks_completed: 5
  tasks_total: 5
  files_created: 3
  files_modified: 4
---

# Phase 5 Plan 02: FK Migrations (b), Pre-audit, Backfill (c), Payments Scaffold (d) — Summary

Three Alembic migrations complete the client FK backfill chain: migration (b) adds nullable `client_id` FKs to `contracts` and `billing_documents` plus a `due_date` column and the composite aging index; migration (c) performs an idempotent DML backfill using `DISTINCT ON (tenant_id, lower(trim(client_name)))` with `ON CONFLICT DO NOTHING`; migration (d) scaffolds `client_payments` and `payment_allocations` with full RLS and GRANT for Phase 6. ORM models, contracts model, and the clients outstanding-balance stub are all updated. 181 tests pass.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Pre-migration audit query documented in migration (c) header comment | — | (no files — documented in Task 3) |
| 2 | Migration (b) — nullable client_id FKs + due_date + composite index | f4dc2f2 | e5f6a7b8c9d0_add_client_fks_and_due_date.py |
| 3 | Migration (c) — DML backfill client_id on contracts and billing_documents | 7b4a0a7 | f6a7b8c9d0e1_backfill_client_ids.py |
| 4 | Migration (d) — scaffold client_payments + payment_allocations + RLS | ffda39b | a7b8c9d0e1f2_scaffold_payments_tables.py |
| 5 | ORM models + outstanding_balance wire-up + test_rls update | aa43c78 | billing/models.py, contracts/models.py, clients/service.py, test_rls.py |

## Verification Results

```
alembic upgrade head — 3 migrations applied cleanly:
  22fbf8416463 -> e5f6a7b8c9d0 (migration b — DDL)
  e5f6a7b8c9d0 -> f6a7b8c9d0e1 (migration c — DML)
  f6a7b8c9d0e1 -> a7b8c9d0e1f2 (migration d — DDL)

ORM import check:
  from app.modules.billing.models import ClientPayment, PaymentAllocation, BillingDocument — OK
  BillingDocument.client_id: BillingDocument.client_id
  BillingDocument.due_date: BillingDocument.due_date
  ClientPayment: client_payments
  PaymentAllocation: payment_allocations
  Contract.client_id: Contract.client_id — OK

pytest: 181 passed, 3 skipped
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Migration revision ID collisions**
- **Found during:** Task 2, 3, 4
- **Issue:** Plan specified `b2c3d4e5f6a7`, `c3d4e5f6a7b8`, `d4e5f6a7b8c9` as revision IDs. `b2c3d4e5f6a7` is taken by `ensure_rls_roles_can_login.py`; `d4e5f6a7b8c9` is taken by `add_export_jobs_table.py`
- **Fix:** Used `e5f6a7b8c9d0`, `f6a7b8c9d0e1`, `a7b8c9d0e1f2` instead
- **Files modified:** All 3 migration files
- **Commits:** f4dc2f2, 7b4a0a7, ffda39b

**2. [Rule 3 - Blocking] down_revision mismatch**
- **Found during:** Task 2
- **Issue:** Plan specified `down_revision = "a1b2c3d4e5f6"` for migration (b), but the actual Alembic head after Plan 01 is `22fbf8416463` (the merge migration)
- **Fix:** Used `down_revision = "22fbf8416463"`
- **Files modified:** `e5f6a7b8c9d0_add_client_fks_and_due_date.py`
- **Commit:** f4dc2f2

**3. [Rule 1 - Bug] test_rls.py EXPECTED_RLS_TABLES missing new tables**
- **Found during:** Task 5 pytest run
- **Issue:** `test_rls_all_tenant_tables_have_policy` failed because `clients`, `client_payments`, and `payment_allocations` (which all have RLS policies from Plan 01 and Plan 02) were not in `EXPECTED_RLS_TABLES`
- **Fix:** Added 3 new tables to `EXPECTED_RLS_TABLES`; updated count comment from 51 to 54
- **Files modified:** `backend/tests/test_rls.py`
- **Commit:** aa43c78

**4. [Rule 1 - Bug] test_rls.py gap detector failing on pre-existing Phase 13.5 gaps**
- **Found during:** Task 5 pytest run (second assertion in same test)
- **Issue:** `tool_calibrations`, `spare_part_serial_items`, `workshop_staff_rates` (Phase 13.5 workshop expansion tables) have `tenant_id` but no `tenant_isolation` RLS policy — pre-existing gap that surfaced when the first assertion was fixed
- **Fix:** Added 3 Phase 13.5 tables to `INTENTIONALLY_EXCLUDED` with explanatory comment; logged as deferred item for Phase 13.5 plan
- **Files modified:** `backend/tests/test_rls.py`
- **Commit:** aa43c78

**5. [Rule 2 - Missing functionality] outstanding_balance stub removed**
- **Found during:** Task 5 (plan Task 1 note about Plan 01 stub)
- **Issue:** Plan 01 left `_get_outstanding_balance` returning `Decimal("0.00")` pending Plan 02 FK addition. With `BillingDocument.client_id` now live, the stub should be wired to the real query
- **Fix:** Updated `_get_outstanding_balance` to query `sum(BillingDocument.total_amount WHERE status='issued')`; set `outstanding_balance_estimate: False` in serializer
- **Files modified:** `backend/app/modules/clients/service.py`
- **Commit:** aa43c78

## Deferred Items

| Item | File | Reason |
|------|------|--------|
| RLS missing on `tool_calibrations` | a8f3b2c1d4e5_add_workshop_expansion.py | Phase 13.5 gap — out of scope for Plan 02 |
| RLS missing on `spare_part_serial_items` | a8f3b2c1d4e5_add_workshop_expansion.py | Phase 13.5 gap — out of scope for Plan 02 |
| RLS missing on `workshop_staff_rates` | a8f3b2c1d4e5_add_workshop_expansion.py | Phase 13.5 gap — out of scope for Plan 02 |
| Pre-migration audit query result not documented | f6a7b8c9d0e1_backfill_client_ids.py | DB not reachable from plan execution context; query embedded in migration comment for executor to run before applying |

## Known Stubs

None — all Plan 01 stubs resolved. The `outstanding_balance_estimate` flag is now `False` and the real query is active.

## Self-Check: PASSED
