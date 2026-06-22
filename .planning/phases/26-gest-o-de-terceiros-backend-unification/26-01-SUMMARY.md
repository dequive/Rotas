---
phase: 26-gest-o-de-terceiros-backend-unification
plan: "01"
subsystem: backend/database
tags: [migration, orm, third-party, clients, rls]
dependency_graph:
  requires: [adv03 migration, third_parties table, clients table]
  provides: [client_profiles table, clients.third_party_id FK, ClientProfile ORM model]
  affects: [backend/app/modules/clients, backend/app/modules/third_party]
tech_stack:
  added: []
  patterns: [Alembic DDL migration, SQLAlchemy mapped_column, RLS co-location rule]
key_files:
  created:
    - backend/alembic/versions/gt01_add_client_profiles_and_third_party_fk.py
  modified:
    - backend/app/modules/third_party/models.py
    - backend/app/modules/clients/models.py
decisions:
  - gt01 down_revision corrected to adv03 (actual DB head) — adv02/adv03 were applied after adv01 to patch RLS; using adv01 would have created a parallel branch
key_decisions:
  - gt01 chains from adv03 not adv01 — adv02/adv03 patched RLS on driver_advances and trip_settlements before this plan ran
metrics:
  duration_minutes: 12
  completed_date: "2026-06-22"
  tasks_completed: 3
  tasks_total: 3
  files_changed: 3
---

# Phase 26 Plan 01: client_profiles DDL migration and ORM models

client_profiles table (9 columns, Numeric(14,2) credit_limit, UNIQUE third_party_id) + clients.third_party_id nullable FK, both with RLS+GRANT in the same migration per v2.0 rule.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write gt01 Alembic DDL migration | 1a5da11 | backend/alembic/versions/gt01_add_client_profiles_and_third_party_fk.py |
| 2 | Add ClientProfile ORM model and Client.third_party_id | 36a0837 | backend/app/modules/third_party/models.py, backend/app/modules/clients/models.py |
| 3 | Confirm MODEL_MODULES registration and run migration | fbcd639 | backend/alembic/versions/gt01_add_client_profiles_and_third_party_fk.py (down_revision fix) |

## Verification Results

- `alembic current` = `gt01 (head)` — migration applied cleanly
- Migration parses: `ast.parse()` OK
- RLS block: 4 statements (ENABLE + FORCE + CREATE POLICY + GRANT) confirmed in migration
- `ClientProfile.credit_limit` uses `Mapped[Decimal | None]` — not float
- `Client.third_party_id` present as `Mapped[uuid.UUID | None]` with FK to third_parties.id
- `test_clients_api.py`: 10/10 passed — no regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected down_revision from adv01 to adv03**
- **Found during:** Task 3 (alembic current check before running migration)
- **Issue:** Plan specified `down_revision = "adv01"` but DB head was `adv03` — adv02 (RLS fix) and adv03 (policy rename) had been applied after adv01. Using adv01 would have created a parallel branch head instead of a linear chain.
- **Fix:** Updated `down_revision = "adv03"` in the migration file before applying.
- **Files modified:** `backend/alembic/versions/gt01_add_client_profiles_and_third_party_fk.py`
- **Commit:** fbcd639

## Known Stubs

None — this plan creates DDL schema only; no service layer or API endpoints.

## Self-Check: PASSED

- `backend/alembic/versions/gt01_add_client_profiles_and_third_party_fk.py` — FOUND
- `backend/app/modules/third_party/models.py` — FOUND (ClientProfile appended)
- `backend/app/modules/clients/models.py` — FOUND (third_party_id column added)
- Commits 1a5da11, 36a0837, fbcd639 — all present in git log
