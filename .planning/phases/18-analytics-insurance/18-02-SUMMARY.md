---
phase: 18-analytics-insurance
plan: "02"
subsystem: backend
tags: [analytics, export, xlsx, pdf, async-job]
key_files:
  created:
    - backend/app/modules/analytics/export_service.py
    - backend/app/modules/analytics/compliance_export_service.py
  modified:
    - backend/app/modules/analytics/router.py
metrics:
  completed_date: "2026-06-20"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 18 Plan 02: Fuel XLSX + Compliance PDF Async Exports — Summary

## One-liner

Async export endpoints for fuel consumption XLSX (ANA-02) and compliance PDF (ANA-03) using the existing ExportJob queue pattern.

## What Was Built

### export_service.py (ANA-02)

`generate_fuel_xlsx(db, tenant_id, month)` — queries FuelLog and Vehicle data for the given YYYY-MM period; builds openpyxl Workbook with per-vehicle columns: Matrícula, Combustível Total (L), Custo Total (MZN), Consumo Real (L/100km), Target (L/100km), Desvio %. Rows exceeding target are highlighted red. Returns `bytes`.

### compliance_export_service.py (ANA-03)

`generate_compliance_pdf(db, tenant_id)` — queries vehicle and driver compliance warnings via `vehicle_compliance_warnings` / `driver_compliance_warnings`; generates PDF report with expiry alerts grouped by severity (critical/urgent/warning). Returns `bytes`.

### Router endpoints (analytics/router.py)

- `GET /analytics/fuel-report?month=YYYY-MM` — idempotent: returns existing queued/processing job; creates ExportJob with `job_type="analytics_fuel_xlsx"`, enqueues `task_export_fuel_report` via ARQ.
- `GET /analytics/compliance-report` — same pattern, `job_type="analytics_compliance_pdf"`, enqueues `task_export_compliance_report`.

Both return 202 with `{job_id, status}`.

## Verification

- ruff: All checks passed on analytics module
- Endpoints present and return 202 with job_id
