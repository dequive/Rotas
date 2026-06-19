---
phase: 23-third-party-registry
plan: "07"
subsystem: worker / third_party / alerts
tags: [arq, cron, alerts, document-expiry, background-task]
dependency_graph:
  requires: [23-06]
  provides: [task_check_document_expiry, cron-doc-expiry-04utc]
  affects: [backend/app/worker.py, backend/tests/test_third_party.py]
tech_stack:
  added: []
  patterns: [ARQ cron task, BYPASSRLS admin session, alert idempotency via request_reference]
key_files:
  created:
    - backend/tests/test_third_party.py
  modified:
    - backend/app/worker.py
decisions:
  - Cross-tenant query in admin session (no per-tenant enumeration) — single SELECT across all tenants is simpler and consistent with existing worker pattern
  - request_reference includes doc.id (not just expiry_date) to prevent collisions between different documents with the same expiry date
  - Catch all exceptions per-document so one bad alert write cannot abort the entire batch
  - create_alert raises ApiError(409) on duplicate request_reference with different values; same-value duplicates return silently — exception handler covers both safe-to-ignore and unexpected cases
metrics:
  duration: "~10 minutes"
  completed: "2026-06-19"
  tasks_completed: 2
  files_changed: 2
---

# Phase 23 Plan 07: Document Expiry Alerts Summary

Daily ARQ cron task that scans all tenants for operational documents expiring within 30 days and emits idempotent `document_expiring_soon` alerts via the existing `create_alert` service.

## What Was Built

### `task_check_document_expiry` (backend/app/worker.py)

- Opens a BYPASSRLS admin session and queries `operational_documents` cross-tenant for rows with `expiry_date` between today and today+30 days
- For each document: computes `priority` (`critical` if ≤7 days, `high` if 8-30 days) and calls `create_alert(db, doc.tenant_id, AlertCreate(...))` with `request_reference = f"doc_expiry:{doc.id}:{doc.expiry_date.isoformat()}"`
- Per-document exception handling ensures one failed alert write does not abort the rest of the batch
- Registered in `WorkerSettings.functions` and `WorkerSettings.cron_jobs` at `hour=4, minute=0` (04:00 UTC = 06:00 Africa/Maputo)

### Test coverage (backend/tests/test_third_party.py) — 5 tests, all pass

| Test | Assertion |
|------|-----------|
| `test_doc_expiry_alerts` | 15-day doc → 1 alert, priority=high, correct request_reference fields |
| `test_doc_expiry_critical_priority` | 5-day doc → priority=critical |
| `test_doc_expiry_alert_error_continues` | Exception on first doc → task still processes second doc |
| `test_doc_expiry_no_docs` | Empty result → 0 alerts, no crash |
| `test_worker_settings_registration` | task in `.functions` and `.cron_jobs` |

## Acceptance Criteria

- [x] `task_check_document_expiry` runs and calls `create_alert` for each expiring document
- [x] `request_reference` includes `doc.id` to prevent cross-document collisions
- [x] Running the task twice does NOT create duplicate alerts (idempotent via `create_alert`'s `request_reference` uniqueness)
- [x] Task is registered in `WorkerSettings.functions` and `WorkerSettings.cron_jobs`
- [x] Documents expiring ≤7 days → `priority="critical"`, 8-30 days → `priority="high"`
- [x] `pytest tests/test_third_party.py -x` — 5 passed
- [x] `python -c "from app.worker import task_check_document_expiry, WorkerSettings; assert task_check_document_expiry in WorkerSettings.functions"` exits 0

## Deviations from Plan

None — plan executed exactly as written, with one adaptation: `get_expiring_documents` service function returns serialized dicts, but the worker performs a direct ORM query on `OperationalDocument` (as the plan specified) to access attribute fields. The plan's code block was followed directly and works correctly with ORM objects.

## Self-Check: PASSED

- `backend/app/worker.py` — modified, `task_check_document_expiry` present before `WorkerSettings`
- `backend/tests/test_third_party.py` — created, 5 tests pass
- Commit `df17187` — verified present
