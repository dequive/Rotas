---
phase: 24
plan: 24-06
type: summary
subsystem: infra
tags: [alembic, seed, smoke-test, migrations, typescript, ruff]
dependency_graph:
  requires: [24-01, 24-02, 24-03, 24-04, 24-05]
  provides: [phase-24-complete]
key_files:
  created:
    - backend/tests/test_third_party_phase24.py
  modified:
    - backend/app/modules/third_party/service.py
  verified:
    - backend/alembic/versions/ (head: b4f2c9d8a1e6)
    - backend/scripts/seed_mz_provinces.py
decisions:
  - "alembic upgrade head: no pending migrations — already at head b4f2c9d8a1e6"
  - "11 provinces seeded idempotently (existing rows skipped)"
  - "pytest full suite: 348 passed, 2 skipped — zero failures"
  - "Phase 24 smoke tests: 7/7 PASSED (contacts CRUD, idempotency, ledger balance, payment credit, evaluation weighted score, invalid weights 422, provinces count)"
  - "ApiError positional status_code bug fixed in evaluation service (5 callers changed to keyword form)"
  - "TypeScript: 0 errors; Next.js build: clean; ruff: all checks passed"
metrics:
  duration: ~10 minutes
  completed_date: "2026-06-20"
  tasks_completed: 3
---

# Plan 24-06: Migrations + Seed + Smoke Test — Summary

**One-liner:** All Phase 24 migrations applied at head, 11 Mozambican provinces seeded, 7/7 smoke tests PASS, 348 total tests green, TypeScript and Next.js build clean — Phase 24 complete.

---

## Results

### Alembic

```
alembic current: b4f2c9d8a1e6 (head)
```

Migration chain (Phase 23 + 24):
- `tp01a` → mz_provinces
- `tp01b` → third_party tables
- `tp03/tp05/tp06` → nullable FKs, assignments, operational_documents
- `tp_merge_wave2` → merge point
- `b1c2d3e4f5a6` → billing issuer_name/issuer_nuit/parent_invoice_number + contracts.payment_terms_days
- `tp07` → third_party_contacts table + RLS
- `tp08` → supplier_ledger_entries table + RLS
- `tp09` → supplier_evaluations table + RLS
- `934b7fae14fc` → tenant_roles
- `b4f2c9d8a1e6` (HEAD) → restore indexes + tenant_roles RLS

Table existence and RLS verification:
```
third_party_contacts: OK, RLS ON
supplier_ledger_entries: OK, RLS ON
supplier_evaluations: OK, RLS ON
```

### Seed

```
Seeded 11 provinces (idempotent — existing rows skipped).
mz_provinces count: 11
PASS: 11 provinces seeded correctly
```

Provinces: Maputo Cidade, Maputo Província, Gaza, Inhambane, Sofala, Manica, Tete, Zambézia, Nampula, Niassa, Cabo Delgado.

### Phase 24 Smoke Tests (7/7 PASSED)

```
tests/test_third_party_phase24.py::test_contacts_crud PASSED
tests/test_third_party_phase24.py::test_idempotency_on_contact_create PASSED
tests/test_third_party_phase24.py::test_supplier_account_zero_balance PASSED
tests/test_third_party_phase24.py::test_payment_creates_credit_entry PASSED
tests/test_third_party_phase24.py::test_evaluation_weighted_score PASSED
tests/test_third_party_phase24.py::test_evaluation_invalid_weights_rejected PASSED
tests/test_third_party_phase24.py::test_provinces_seeded PASSED

7 passed in 4.33s
```

### Full Backend Suite

```
348 passed, 2 skipped in 130.45s (0:02:10)
```

Zero failures. 2 skips are pre-existing and unrelated to Phase 24.

### Frontend Verification

- TypeScript (`npx tsc --noEmit`): **0 errors**
- Ruff (`ruff check app/`): **All checks passed**
- Next.js build (`npx next build`): **Clean** — all Phase 24 routes compiled successfully

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ApiError positional status_code in create_evaluation service**
- **Found during:** Task 2 (test_evaluation_invalid_weights_rejected initially FAILED)
- **Issue:** `ApiError.__init__` declares `status_code` as keyword-only (after `*`). Five calls in the evaluation validation block passed it as the 3rd positional argument, causing `TypeError: ApiError.__init__() takes 3 positional arguments but 4 were given`
- **Fix:** Changed all 5 callers to `status_code=NNN` keyword form: `contact_not_found`, `empty_criteria`, `invalid_criterion_weight`, `invalid_criterion_score`, `invalid_weights`
- **Files modified:** `backend/app/modules/third_party/service.py`
- **Commit:** 8240e8c

**2. [Deviation] Test fixture pattern adapted from plan spec**
- **Found during:** Task 2 planning
- **Issue:** Plan spec used `auth_client` and `anon_client` fixture names that don't exist in conftest.py. The project uses `async_client` + `auth_headers` dict.
- **Fix:** Used `async_client` + `auth_headers` for authenticated calls; provinces endpoint has no auth required (uses `_get_anon_session` internally).
- **Impact:** None — semantically identical, correct fixture names for this codebase.

---

## Self-Check: PASSED

- [x] `alembic current` shows `b4f2c9d8a1e6 (head)` — all migrations applied
- [x] All 3 Phase 24 tables exist with RLS ON
- [x] `SELECT count(*) FROM mz_provinces` = 11
- [x] `test_third_party_phase24.py`: 7/7 PASSED
- [x] Full suite: 348 passed, 2 skipped, 0 failures
- [x] `npx tsc --noEmit`: 0 errors
- [x] `npx next build`: clean
- [x] `ruff check app/`: all checks passed
- [x] ROADMAP.md updated: Phase 24 → 7/7 | Complete | 2026-06-20
