---
quick_id: 260621-pbc
slug: fix-photo-sync-and-consolidate-arq-worke
status: done
created: 2026-06-21
---

# Fix photo sync bug + consolidate ARQ workers + railway.toml

## Task 1: Fix silent photo upload bug in sync.ts

**File:** `apps/driver/src/sync.ts:33`

**Bug:** `uploadQueuedPhotos()` has an allowlist `["fuel_log", "checklist"]` that silently drops
photos for `delivery_proof` and `load_permit` entity types. Any offline photo taken during cargo
delivery or permit generation never reaches the server.

**Fix:** Add `"delivery_proof"` and `"load_permit"` to the allowlist.

## Task 2: Consolidate ARQ workers

**Problem:** Two WorkerSettings exist:
- `backend/app/worker.py` — main worker (billing export, SM crons, insurance, heartbeat, Prometheus)
- `backend/app/jobs/worker.py` — jobs worker (maintenance, housekeeping, document expiry, notifications)

**Overlapping functions:**
- Notifications: `task_process_notification_outbox` (basic, 3 retries) vs
  `deliver_queued_notifications` (exponential backoff, 5 retries, dead-letter, HTML, superior)
- Document expiry: `task_check_document_expiry` (OperationalDocument table) vs
  `scan_expiring_documents` (driver+vehicle docs via analytics) — different entity types, BOTH needed

**Unique to `app/jobs/worker.py`** (missing from `app/worker.py`):
- `check_maintenance_schedules` + `check_vehicle_maintenance` (MAINT-01)
- `scan_expiring_documents` (driver/vehicle docs)
- `run_housekeeping` (idempotency key + audit log cleanup)
- `task_export_compliance_report` (AT compliance XLSX)
- `deliver_queued_notifications` (superior notification delivery)

**Changes to `backend/app/worker.py`:**
1. Import all 5 missing task groups from `app.jobs.tasks.*`
2. In `startup()`: alias `ctx["session_factory"] = ctx["db_factory"]` so jobs tasks can find the DB factory
3. Remove `task_process_notification_outbox()` function body — superseded by `deliver_queued_notifications`
4. Update `WorkerSettings.functions` — add new 6, remove `task_process_notification_outbox`
5. Update `WorkerSettings.cron_jobs` — add maintenance (02:00), scan_expiring_docs (03:00),
   housekeeping (04:15), deliver_queued_notifications every 5 min (replacing outbox cron)

**Replace `backend/app/jobs/worker.py`:** Thin shim re-exporting `WorkerSettings` from `app.worker`
so any Railway service still using `arq app.jobs.worker.WorkerSettings` continues to work.

## Task 3: Fix incompatible railway.toml files

**Root `railway.toml`:** `uvicorn backend.app.main:app` — runs from repo root, wrong module path
**`backend/railway.toml`:** `gunicorn -k uvicorn.workers.UvicornWorker ... app.main:app` — correct

**Fix:** Delete root `railway.toml`. The `backend/railway.toml` is authoritative.
