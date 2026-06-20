---
phase: 24
plan: "01"
subsystem: third_party
tags: [migrations, alembic, postgresql, rls, third-party]
dependency_graph:
  requires: []
  provides: [third_party_contacts table, supplier_ledger_entries table, supplier_evaluations table, activity_code/sector columns]
  affects: [24-02-backend-service-api]
tech_stack:
  added: []
  patterns: [v2.0 RLS+GRANT co-located with CREATE TABLE, CheckConstraint in __table_args__]
key_files:
  created:
    - backend/alembic/versions/tp07_add_third_party_contacts.py
    - backend/alembic/versions/tp08_add_supplier_ledger_entries.py
    - backend/alembic/versions/tp09_add_supplier_evaluations.py
  modified:
    - backend/app/modules/third_party/models.py
decisions:
  - "tp07 down_revision set to b1c2d3e4f5a6 (current head) not tp06 — tp06 already merged via tp_merge_wave2; using tp06 would create a parallel branch head"
metrics:
  duration_minutes: 15
  completed_date: "2026-06-20"
  tasks_completed: 4
  files_changed: 4
---

# Phase 24 Plan 01: Migrations — third_party_contacts, supplier_ledger_entries, supplier_evaluations + activity_code/sector columns Summary

Three Alembic migrations (tp07, tp08, tp09) creating the three new Phase 24 tables with RLS + GRANT co-located per v2.0 rules, plus SQLAlchemy models for all three tables.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Migration tp07: third_party_contacts table + activity_code/sector on third_parties | a2c99ff |
| 2 | Migration tp08: supplier_ledger_entries table | f908f16 |
| 3 | Migration tp09: supplier_evaluations table | e0c79de |
| 4 | SQLAlchemy models: ThirdPartyContact, SupplierLedgerEntry, SupplierEvaluation + ThirdParty fields | c73015e |

## Verification Results

- `alembic upgrade head` applied tp07 → tp08 → tp09 cleanly against the live database
- `python -c "from app.modules.third_party.models import ThirdPartyContact, SupplierLedgerEntry, SupplierEvaluation; print('OK')"` returns OK
- `alembic heads` shows single head: `tp09 (head)`
- `ruff check` passes on all modified files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected down_revision for tp07**
- **Found during:** Task 1
- **Issue:** Plan specified `down_revision = "tp06"` for tp07. However, tp06 is already merged into the main revision chain via `tp_merge_wave2 -> restore_composite_indexes -> b1c2d3e4f5a6`. Using `tp06` would have created a new parallel branch head, requiring an additional merge migration.
- **Fix:** Set `down_revision = "b1c2d3e4f5a6"` (the actual current head) so tp07 chains linearly after the existing head, keeping a single clean head throughout.
- **Files modified:** `backend/alembic/versions/tp07_add_third_party_contacts.py`
- **Commit:** a2c99ff

## Known Stubs

None — this plan creates only schema (migrations + models), no service or API layer.

## Self-Check: PASSED

- `backend/alembic/versions/tp07_add_third_party_contacts.py` — FOUND
- `backend/alembic/versions/tp08_add_supplier_ledger_entries.py` — FOUND
- `backend/alembic/versions/tp09_add_supplier_evaluations.py` — FOUND
- `backend/app/modules/third_party/models.py` modified — FOUND
- Commits a2c99ff, f908f16, e0c79de, c73015e — all present in git log
