---
plan: "05"
phase: 15-fiscal-compliance-seguran-a-de-carga
status: complete
wave: 3
---

# Plan 15-05 Summary — FISC-03 Monthly AT Compliance Report

## What was done

**ARQ task:**
- Created `backend/app/jobs/tasks/billing_export.py` with `task_export_compliance_report()`:
  - Queries `billing_documents LEFT JOIN contracts` for `tenant_id` and month (using `DATE_TRUNC('month', issued_at)`)
  - Generates XLSX with 9 columns: `invoice_number`, `client_nuit`, `client_name`, `issued_at`, `subtotal`, `iva_rate`, `iva_amount` (tax_amount), `total_amount`, `status`
  - Saves XLSX via `save_generated_file()` with `file_type="compliance_report"`
  - Transitions ExportJob: `queued → processing → done` (or `failed`)
- `backend/app/jobs/worker.py`: Registered `task_export_compliance_report` in `WorkerSettings.functions`

**Service:**
- `billing/service.py`: Added `create_compliance_report_job()`:
  - Validates `month` is YYYY-MM format
  - Idempotent: returns existing `queued`/`processing` job for same tenant
  - Creates `ExportJob(job_type="compliance_report", entity_id=None)`
  - Enqueues ARQ task `task_export_compliance_report`

**Router:**
- `billing/router.py`: Added `GET /billing/compliance-report?month=YYYY-MM` (status 202)
  - Requires `WRITE_ROLES` (owner/admin/manager)
  - Returns `{"job_id": "...", "status": "queued"}`
  - Polling via existing `GET /billing/jobs/{job_id}/status`
