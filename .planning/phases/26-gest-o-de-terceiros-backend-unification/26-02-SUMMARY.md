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
  modified: []
decisions:
  - gt02 uses WHERE third_party_id IS NULL loop without offset counter — processed rows leave the working set so no offset increment needed
  - ON CONFLICT guards on all three INSERT statements ensure idempotent re-runs after partial failures
  - Per-batch bind.commit() reduces lock hold time on the clients table during backfill
key_decisions:
  - Idempotent batch loop without offset counter — WHERE third_party_id IS NULL naturally shrinks the working set
  - Three ON CONFLICT guards: (tenant_id, nuit) for third_parties; (third_party_id, role_type) for third_party_roles; (third_party_id) for client_profiles
metrics:
  duration_minutes: 7
  completed_date: "2026-06-22"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 1
---

# Phase 26 Plan 02: DML backfill migration — clients into third_parties entity graph

Idempotent batch DML migration (gt02) that connects all existing client rows to the third_parties entity graph: INSERT third_parties + INSERT third_party_roles(role_type='client') + INSERT client_profiles + UPDATE clients.third_party_id, in batches of 500 with per-batch commit and ON CONFLICT DO NOTHING guards on all three inserts.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write gt02 Alembic DML backfill migration | 226f407 | backend/alembic/versions/gt02_backfill_clients_to_third_parties.py |
| 2 | Apply migration and verify backfill results | (DB-only) | — |

## Verification Results

- `alembic current` shows `gt02` as current head
- `SELECT count(*) FROM clients WHERE third_party_id IS NULL` = **0** (all clients linked)
- `SELECT count(*) FROM client_profiles` = **2334** (populated)
- 0 clients missing `third_party_roles` row with `role_type='client'`
- 0 duplicate `(tenant_id, nuit)` pairs in `third_parties`
- Idempotency check: second `alembic upgrade gt02` run produced no errors, no duplicate rows
- `pytest tests/test_clients_api.py` = **10/10 passed** — no regressions

## Deviations from Plan

None — plan executed exactly as written. The corrected loop (no offset counter, WHERE third_party_id IS NULL) from the plan's action block was used directly.

## Known Stubs

None — this plan is a pure DML migration; no service layer or API endpoints.

## Self-Check: PASSED

- `backend/alembic/versions/gt02_backfill_clients_to_third_parties.py` — FOUND
- Commit 226f407 — present in git log
- Database: 0 clients with NULL third_party_id, 2334 client_profiles rows, 0 duplicates
