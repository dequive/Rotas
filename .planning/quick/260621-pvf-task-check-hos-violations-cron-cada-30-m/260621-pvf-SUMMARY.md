---
phase: quick-260621-pvf
plan: 01
subsystem: alerts, workers, drivers
tags: [hos, alerts, cron, driver-documents, worker]
key-decisions:
  - "task_check_hos_violations uses calculate_driving_hours() from hos_service — no duplication"
  - "HOS alert deduplication: request_reference includes ISO date (one alert per driver per day per severity)"
  - "Driver document expiry mirrors task_check_vehicle_document_expiry pattern exactly (same JSON shape)"
  - "Tests call service functions directly — no ARQ/Redis required in test env"
key-files:
  modified:
    - backend/app/worker.py
    - backend/tests/test_worker_alert_tasks.py
metrics:
  completed_date: "2026-06-21"
  tasks: 2
  files: 2
---

# Quick Task 260621-pvf: HOS Violation Alerts + Driver Document Expiry Alerts

**One-liner:** Two new ARQ worker crons — HOS violations detected every 30 min for active drivers, driver document expiry scanned daily — close the last alerting gap in the fleet compliance layer.

## What Was Done

### Task 1 — task_check_driver_document_expiry (daily, 05:00 UTC)

Added to `backend/app/worker.py`:

- Scans all `Driver.documents` JSON column (shape: `{doc_type: {"expiry_date": "YYYY-MM-DD"}}`)
- Generates `driver_document_expiring_soon` alerts for documents expiring within 30 days
- Priority: `critical` if ≤ 7 days, `high` otherwise
- Deduplication via `request_reference = f"driver_doc:{driver.id}:{doc_type}:{expiry_date}"`
- Error-isolated per document — one bad entry does not abort the batch
- Registered in `WorkerSettings.cron_jobs`: `cron(task_check_driver_document_expiry, hour=5, minute=0)`

### Task 2 — task_check_hos_violations (every 30 min)

Added to `backend/app/worker.py`:

- Finds all distinct drivers with trips in `("in_progress", "delayed", "incident")` statuses
- Calls `calculate_driving_hours(driver_id, tenant_id, db)` from `drivers/hos_service.py` per driver
- Generates alerts:
  - `driver_hos_warning` (priority=high) when `status == "warning"` (≥ 8h today)
  - `driver_hos_violation` (priority=critical) when `status == "violation"` (≥ 9h/day or ≥ 48h/week)
- Deduplication: `request_reference = f"hos:{driver_id}:{today_iso}:{status}"` — at most 1 alert per driver per day per severity
- Registered: `cron(task_check_hos_violations, minute={0, 30})`

Both tasks use BYPASSRLS admin session (cross-tenant scan, consistent with all other worker crons).

### Task 3 — Tests

`backend/tests/test_worker_alert_tasks.py` — 5 tests, all passing:

1. `test_task_check_driver_document_expiry_generates_alert` — doc expiring in 5 days → alert created
2. `test_task_check_driver_document_expiry_skips_non_expiring` — doc expiring in 60 days → no alert
3. `test_task_check_driver_document_expiry_idempotent` — task run twice → still 1 alert
4. `test_task_check_hos_violations_generates_warning` — driver with 8.5h active trip → warning alert
5. `test_task_check_hos_violations_ok_driver_no_alert` — driver with 2h trip → no alert

## Alert Coverage — Complete Picture

| Alert type | Source | Cron |
|---|---|---|
| `document_expiring_soon` (third-party) | TP-10 `task_check_document_expiry` | 04:00 UTC daily |
| `insurance_renewal` (vehicle) | INS-02 `task_check_insurance_renewals` | 05:00 UTC daily |
| `vehicle_document_expiring_soon` | `task_check_vehicle_document_expiry` | 04:30 UTC daily |
| `driver_document_expiring_soon` | **260621-pvf** `task_check_driver_document_expiry` | 05:00 UTC daily |
| `driver_hos_warning` / `driver_hos_violation` | **260621-pvf** `task_check_hos_violations` | Every 30 min |

## Known Stubs

None — all code paths fully wired.

## Self-Check: PASSED

- `task_check_driver_document_expiry` in `WorkerSettings.functions` and `cron_jobs` — confirmed
- `task_check_hos_violations` in `WorkerSettings.functions` and `cron_jobs` — confirmed
- 5/5 tests pass
