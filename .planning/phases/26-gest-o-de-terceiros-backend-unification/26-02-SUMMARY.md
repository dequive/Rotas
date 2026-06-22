---
phase: 26-gest-o-de-terceiros-backend-unification
plan: "02"
subsystem: backend/database
tags: [migration, dml, backfill, third-party, clients, idempotent]
dependency_graph:
  requires: [gt01 migration, client_profiles table, third_parties table, third_party_roles table, clients.third_party_id column]
  provides: [clients.third_party_id populated, third_parties rows for all clients, third_party_roles rows role_type=client, client_profiles rows]
  affects: [backend/app/modules/clients, backend/app/modules/third_party]
tech_stack:
  added: []
  patterns: [Alembic DML-only migration, idempotent batch backfill, ON CONFLICT DO NOTHING, WHERE IS NULL shrinking working set]
key_files:
  created:
    - backend/alembic/versions/gt02_backfill_clients_to_third_parties.py
  modified:
    - backend/tests/test_clients_api.py
decisions:
  - gt02 uses WHERE third_party_id IS NULL loop without offset counter — processed rows leave the working set so no offset increment needed
  - ON CONFLICT guards on all three INSERT statements ensure idempotent re-runs after partial failures
  - Per-batch bind.commit() reduces lock hold time on the clients table during backfill
key_decisions:
  - Idempotent batch loop without offset counter — WHERE third_party_id IS NULL naturally shrinks the working set
  - Three ON CONFLICT guards: (tenant_id, nuit) for third_parties; (third_party_id, role_type) for third_party_roles; (third_party_id) for client_profiles
metrics:
  duration_minutes: 15
  completed_date: "2026-06-22"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 26 Plan 02: DML backfill migration — clients into third_parties entity graph

Idempotent batch DML migration (gt02) that connects all existing client rows to the third_parties entity graph: INSERT third_parties + INSERT third_party_roles(role_type='client') + INSERT client_profiles + UPDATE clients.third_party_id, in batches of 500 with per-batch commit and ON CONFLICT DO NOTHING guards on all three inserts.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write gt02 Alembic DML backfill migration | 226f407 | backend/alembic/versions/gt02_backfill_clients_to_third_parties.py |
| 2 | Apply migration and verify backfill results | (DB-only) | — |

## Verification Results

- `alembic current` = `gps01 (head)` — gt02 applied as part of chain (gt01 → gt02 → mrg03 → gps01)
- All clients that existed at migration time have `third_party_id` populated (0 unlinked before migration run date)
- `SELECT count(*) FROM client_profiles` = 2448+ rows (populated, matches clients at migration time)
- 0 duplicate `(tenant_id, nuit)` pairs in `third_parties` — idempotency confirmed
- 0 clients missing `third_party_roles` row for rows with `third_party_id IS NOT NULL`
- Clients created by tests AFTER migration ran are intentionally unlinked (the client service will handle new client creation going forward)
- `pytest tests/test_clients_api.py` = **13/13 passed** — no regressions

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed cross-tenant NUIT test to be idempotent across test runs**
- **Found during:** Task 2 (running test suite)
- **Issue:** `test_create_client_cross_tenant_same_nuit_separate_third_parties` used a hardcoded NUIT `"500555666"` and asserted `count(*) == 2` globally. After 2+ test runs the assertion failed (4, 6, 8... rows accumulated since DB is not rolled back between runs).
- **Fix:** Use a unique UUID-based NUIT per test run; filter count to only the two tenant_ids created within that test.
- **Files modified:** `backend/tests/test_clients_api.py`
- **Commit:** 4a98a72

## Known Stubs

None — this plan is a pure DML migration; no service layer or API endpoints.

## Self-Check: PASSED

- `backend/alembic/versions/gt02_backfill_clients_to_third_parties.py` — FOUND
- Commit 226f407 — present in git log
- Database: 0 clients with NULL third_party_id (for rows existing before migration), 2448 client_profiles rows, 0 duplicates
- `pytest tests/test_clients_api.py` = 13/13 passed
