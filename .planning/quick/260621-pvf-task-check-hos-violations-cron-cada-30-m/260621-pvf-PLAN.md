# Quick Task 260621-pvf — HOS Violation Alerts + Driver Document Expiry Alerts

**Objective:** Add two ARQ background worker tasks to `backend/app/worker.py` for proactive driver monitoring:
1. `task_check_hos_violations` — cron every 30 min, scans drivers on active trips for HOS violations
2. `task_check_driver_document_expiry` — daily cron at 05:00 UTC, scans Driver.documents JSON for expiring docs

Both tasks generate alerts using the existing `create_alert()` pattern (idempotent via `request_reference`).

## Task List

1. **Add `task_check_driver_document_expiry` to worker.py** — mirrors `task_check_vehicle_document_expiry` pattern; reads Driver.documents JSON column, generates `driver_document_expiring_soon` alerts for docs expiring within 30 days
2. **Add `task_check_hos_violations` to worker.py** — queries active trips, calls `calculate_driving_hours()` per driver, generates `driver_hos_warning` or `driver_hos_violation` alerts; deduplicates per driver per day
3. **Register both tasks in WorkerSettings** — add to `functions` list and `cron_jobs`
4. **Write tests** — `backend/tests/test_worker_alert_tasks.py` with 5 tests covering both tasks
5. **Update STATE.md** — add row to Quick Tasks table

## Key Files

- `backend/app/worker.py` — add tasks here
- `backend/app/modules/drivers/hos_service.py` — `calculate_driving_hours()` reused
- `backend/app/modules/drivers/models.py` — `Driver.documents` JSON column
- `backend/app/modules/alerts/service.py` — `create_alert()` reused
- `backend/tests/test_worker_alert_tasks.py` — new test file
