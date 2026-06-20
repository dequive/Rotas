---
phase: 24
plan: "02"
subsystem: third_party
tags: [service, api, contacts, ledger, payments, evaluations, idempotency]
dependency_graph:
  requires: [24-01-migrations]
  provides: [third_party contacts API, supplier ledger API, supplier payments API, supplier evaluations API]
  affects: [24-03-frontend-terceiros]
tech_stack:
  added: []
  patterns: [execute_http_idempotent on all POST mutations, live balance aggregation (never denormalised), require_permission FLEET_READ/FLEET_WRITE]
key_files:
  created: []
  modified:
    - backend/app/modules/third_party/service.py
    - backend/app/modules/third_party/schemas.py
    - backend/app/modules/third_party/router.py
decisions:
  - "Used require_permission(FLEET_READ/FLEET_WRITE) instead of require_roles — Phase 22 already migrated the third_party router to the new RBAC system; new routes must follow suit"
  - "Average score computed in list_evaluations as Python mean of individual evaluation scores; not stored to avoid denormalisation"
  - "Balance in get_supplier_account computed live via SQL SUM aggregation with filter on entry_type — never written to a column"
metrics:
  duration_minutes: 25
  completed_date: "2026-06-20"
  tasks_completed: 2
  files_changed: 3
---

# Phase 24 Plan 02: Backend service + API — contacts, ledger, payments, evaluations, idempotency Summary

Full service + API layer for third-party sub-contacts, supplier current account (ledger with live balance), manual payments, and weighted-criteria supplier evaluations, all with idempotency-key support on every POST mutation.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | schemas.py + service.py: ContactCreate/PaymentCreate/EvaluationCreate schemas; create_contact, list_contacts, delete_contact, get_supplier_account, create_payment, create_evaluation, list_evaluations; serialize_third_party updated with average_score + activity_code/sector | 1444a73 |
| 2 | router.py: 8 new endpoints (contacts CRUD, account GET, payments POST, evaluations POST+GET) using require_permission FLEET_READ/FLEET_WRITE with Idempotency-Key on all mutations | 4f745c6 |

## Verification Results

- `ruff check app/modules/third_party/` — All checks passed (0 errors)
- `pytest tests/test_third_party.py` — 21 passed
- `from app.modules.third_party import router, service` — imports OK
- All 8 new routes registered and verified via router.routes introspection
- Full test suite: 330 passed (2 pre-existing rate-limit timing failures unrelated to this plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RBAC pattern corrected to match Phase 22 migration**
- **Found during:** Task 2
- **Issue:** Plan specified `require_roles(*WRITE_ROLES)` / `require_roles(*DASHBOARD_ROLES)` for the new router endpoints. Phase 22 had already migrated the entire third_party router to use `require_permission(FLEET_WRITE)` / `require_permission(FLEET_READ)` from `app.core.rbac`. Using the old `require_roles` pattern would have been inconsistent and caused the same `NameError` seen in other routers that weren't migrated.
- **Fix:** Used `require_permission(FLEET_WRITE)` for all mutations and `require_permission(FLEET_READ)` for all reads — matching the existing Phase 22 pattern in the same router.
- **Files modified:** `backend/app/modules/third_party/router.py`
- **Commit:** 4f745c6

**2. [Rule 1 - Bug] Removed `import uuid` (unused after using `from uuid import UUID`)**
- **Found during:** Task 1 (ruff check)
- **Issue:** Plan code added `import uuid` but all UUIDs use `UUID` from `from uuid import UUID`. Ruff flagged F401.
- **Fix:** Removed redundant bare `import uuid`.
- **Files modified:** `backend/app/modules/third_party/service.py`
- **Commit:** 1444a73

## Known Stubs

None — all service functions are fully wired with DB queries, audit logs, and correct response shapes.

## Self-Check: PASSED

- `backend/app/modules/third_party/service.py` — FOUND (modified)
- `backend/app/modules/third_party/schemas.py` — FOUND (modified)
- `backend/app/modules/third_party/router.py` — FOUND (modified)
- Commit 1444a73 — FOUND in git log
- Commit 4f745c6 — FOUND in git log
- All 8 new routes present in router: /contacts (POST+GET+DELETE), /account (GET), /payments (POST), /evaluations (POST+GET)
