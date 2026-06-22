---
phase: 26-gest-o-de-terceiros-backend-unification
plan: "03"
subsystem: backend/clients
tags: [service, third-party, find-or-create, clients, GT-05]
dependency_graph:
  requires: [gt01 migration, gt02 backfill, client_profiles table, third_parties table, third_party_roles table, clients.third_party_id column]
  provides: [create_client wired to third_parties, find-or-create pattern, race condition guard via rollback]
  affects: [backend/app/modules/clients/service.py, backend/tests/test_clients_api.py]
tech_stack:
  added: []
  patterns: [find-or-create with IntegrityError race guard, SQLAlchemy scalar_one_or_none, rollback on concurrent INSERT]
key_files:
  created: []
  modified:
    - backend/app/modules/clients/service.py
    - backend/tests/test_clients_api.py
decisions:
  - create_client uses SELECT before INSERT on third_parties — avoids duplicate rows on replay
  - IntegrityError on third_party INSERT triggers await db.rollback() + re-SELECT — handles concurrent requests
  - third_party_role and client_profile are upserted via scalar_one_or_none guard — idempotent on re-run
  - serialize_client return value unchanged — no API response schema change
key_decisions:
  - find-or-create by (tenant_id, nuit) — UNIQUE constraint on third_parties is the atomic guard
  - rollback on race: full session rollback on IntegrityError at Step 1 — safe because no prior work exists at that point
  - client_profile payment_terms_days/credit_limit copied from ClientCreate payload at profile creation time
metrics:
  duration_minutes: 20
  completed_date: "2026-06-22"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 26 Plan 03: create_client find-or-create against third_parties

`create_client` rewritten as a 4-step find-or-create: SELECT existing third_party by (tenant_id, nuit) before INSERT, with IntegrityError rollback+re-select for concurrent races; adds third_party_role('client') + client_profile in the same session; three GT-05 tests verify deduplication, pre-existing third_party linking, and cross-tenant isolation.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add find-or-create tests to test_clients_api.py | 4a98a72 | backend/tests/test_clients_api.py |
| 2 | Rewrite create_client as find-or-create in service.py | 4a98a72 | backend/app/modules/clients/service.py |

## Verification Results

- `pytest tests/test_clients_api.py` = **13/13 passed** — all pre-existing tests + 3 new GT-05 tests GREEN
- `grep "ThirdParty\|ThirdPartyRole\|ClientProfile" backend/app/modules/clients/service.py` — imports present at line 14
- `grep "find-or-create" backend/app/modules/clients/service.py` — docstring marker present at line 105
- `grep "rollback" backend/app/modules/clients/service.py` — one occurrence inside IntegrityError handler at Step 1
- `grep "serialize_client" backend/app/modules/clients/service.py` — unchanged `serialize_client(client)` call at end
- `grep "third_party_id" backend/app/modules/clients/service.py` — assignment before Client() at line 141

## Deviations from Plan

### Auto-fixed Issues

None — both files had already been implemented and committed in commit `4a98a72` by a prior execution session. This SUMMARY.md was the only missing artifact (written to wrong path `26-third-party-unification/` instead of `26-gest-o-de-terceiros-backend-unification/`).

## Known Stubs

None — service layer implementation is complete. All four steps (find ThirdParty, add ThirdPartyRole, add ClientProfile, insert Client) are wired with real DB queries.

## Self-Check: PASSED

- `backend/app/modules/clients/service.py` — FOUND, contains find-or-create pattern
- `backend/tests/test_clients_api.py` — FOUND, contains 3 GT-05 tests
- Commit 4a98a72 — present in git log
- `pytest tests/test_clients_api.py` = 13/13 passed
