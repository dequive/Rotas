---
phase: 03-manager-dashboard-reporting-layer
plan: "06"
subsystem: billing-exports
tags: [fpdf2, openpyxl, utf8, pdf, xlsx, arq, async-export, mozambique]
dependency_graph:
  requires: [03-03, 03-04]
  provides: [render_billing_export, generate_billing_export_arq, export_job_endpoints]
  affects: [billing-router, billing-service, arq-worker]
tech_stack:
  added: [fpdf2>=2.8.7, openpyxl>=3.1, DejaVuSans TTF 2.37]
  patterns: [ARQ background task, tenant-isolated file download, idempotent job creation]
key_files:
  created:
    - backend/app/modules/billing/fonts/DejaVuSans.ttf
    - backend/app/modules/billing/fonts/DejaVuSans-Bold.ttf
    - backend/tests/test_billing_export.py
    - backend/tests/test_cargo_billing_flow.py
  modified:
    - backend/pyproject.toml
    - backend/app/modules/billing/exporters.py
    - backend/app/modules/billing/service.py
    - backend/app/modules/billing/router.py
    - backend/app/worker.py
decisions:
  - fpdf2+DejaVuSans for UTF-8 PDF: DejaVuSans covers full Latin Extended range; Portuguese diacritics (ã ç â ê é ô) render correctly; font path is Path(__file__)-relative so it works in both FastAPI and ARQ worker contexts
  - openpyxl for XLSX: native bold cell support and number_format attribute; no hand-rolled XML/ZIP
  - Idempotent job creation: enqueue_export_job returns existing queued/processing job rather than spawning duplicates
  - Backward-compatible sync export preserved: GET /billing/documents/{id}/export still works via existing service.export_document
metrics:
  duration: 15
  completed: "2026-06-06"
  tasks: 2
  files: 8
---

# Phase 03 Plan 06: Billing Export Rewrite (fpdf2 + openpyxl) Summary

**One-liner:** UTF-8 safe billing exports via fpdf2+DejaVuSans PDF and openpyxl XLSX, with async ARQ job pipeline and three new job management endpoints.

---

## What Was Built

### Task 1: Replace hand-rolled exporters with fpdf2 + openpyxl

`backend/app/modules/billing/exporters.py` was fully replaced. The previous implementation used a hand-rolled PDF builder that encoded page streams with `latin-1` — silently corrupting Mozambican names containing diacritics (ã, ç, â, ê, etc.). The XLSX path built raw XML/ZIP strings with no formatting support.

**New implementation:**
- `_render_pdf()`: uses `fpdf2.FPDF` with DejaVuSans TTF (Unicode, Latin Extended). Font path is `Path(__file__).parent / "fonts"` — absolute, never CWD-relative, works in both FastAPI request context and ARQ worker subprocess.
- `_render_xlsx()`: uses `openpyxl.Workbook`. Header row has `Font(bold=True)` on every cell. Currency columns 7 and 8 have `number_format = "#,##0.00"`.
- `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` (v2.37) downloaded from GitHub and committed to `backend/app/modules/billing/fonts/`.
- `fpdf2>=2.8.7` and `openpyxl>=3.1` added to `pyproject.toml`.
- Deprecated `ln=True/False` API replaced with `XPos`/`YPos` enums.

### Task 2: ARQ worker + job endpoints + tests green

**`backend/app/worker.py`** — `generate_billing_export` stub replaced with full implementation:
- Opens DB session via `ctx["db_factory"]`
- Loads `ExportJob`, advances status: `queued → processing → done/failed`
- Queries `BillingDocument` and `BillingItem` (tenant-scoped)
- Calls `render_billing_export()`, writes bytes to `LOCAL_UPLOAD_DIR/{tenant_id}/{filename}`
- On exception: sets `job.status = "failed"`, records `error_message[:500]`

**`backend/app/modules/billing/service.py`** — Two new functions:
- `enqueue_export_job()`: creates `ExportJob` record, enqueues ARQ task via `arq_redis.enqueue_job()`. Idempotent: returns existing `queued`/`processing` job if present.
- `get_export_job_status()`: tenant-scoped lookup of `ExportJob` by ID.

**`backend/app/modules/billing/router.py`** — Three new endpoints:
- `POST /billing/documents/{document_id}/export-job?export_format=pdf|xlsx` → 202 + `{job_id, status}`
- `GET /billing/jobs/{job_id}/status` → `{job_id, status, job_type}`
- `GET /billing/jobs/{job_id}/download` → `FileResponse` (tenant-isolated, checks `job.status == "done"`, verifies file exists on disk)

**`backend/tests/test_billing_export.py`** — All 4 `NotImplementedError` stubs replaced:
- `test_pdf_renders_utf8_characters`: `client_name="João Machanga..."`, no `UnicodeEncodeError`, output starts with `%PDF`
- `test_pdf_contains_header_text`: valid `%PDF` header, non-empty bytes
- `test_xlsx_header_row_is_bold`: `ws.cell(1,1).font.bold is True`
- `test_xlsx_currency_columns_have_format`: columns 7 and 8 have `number_format == "#,##0.00"`

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed PDF version assertion in integration test**
- **Found during:** Task 2 verification (full suite run)
- **Issue:** `test_cargo_billing_flow.py` line 531 asserted `content.startswith(b"%PDF-1.4")`. fpdf2 emits `%PDF-1.3` (valid per PDF spec). The assertion was an implementation detail of the hand-rolled builder, not a real requirement.
- **Fix:** Changed to `content.startswith(b"%PDF")` — checks PDF validity without locking to a specific version.
- **Files modified:** `backend/tests/test_cargo_billing_flow.py`
- **Commit:** 03119c1

**2. [Rule 1 - Quality] Fixed deprecated fpdf2 ln= API**
- **Found during:** Task 1 test run (DeprecationWarnings in output)
- **Issue:** fpdf2 v2.5.2+ deprecated `ln=True/False` on `cell()` in favour of `new_x=XPos.*`, `new_y=YPos.*` enums.
- **Fix:** Replaced all `ln=False` with `new_x=XPos.RIGHT, new_y=YPos.TOP` and `ln=True` with `new_x=XPos.LMARGIN, new_y=YPos.NEXT`. Added `from fpdf.enums import XPos, YPos` import.
- **Files modified:** `backend/app/modules/billing/exporters.py`
- **Commit:** 03119c1

### Pre-existing Failure (Out of Scope)

`test_workshop_operations_api.py::test_tool_checkout_return_and_critical_calibration_controls` was already failing before any changes in this plan (confirmed via `git stash` + rerun). It is not caused by this plan's changes and is logged in deferred items.

---

## Test Results

```
tests/test_billing_export.py     4 passed
tests/test_billing_domain.py     5 passed
tests/test_cargo_billing_flow.py 3 passed
Full suite (excl. pre-existing workshop failure): 108 passed
```

---

## Known Stubs

None — all export stubs resolved. `generate_billing_export` worker stub is fully replaced.

---

## Commits

| Hash | Message |
|------|---------|
| b9208f5 | feat(03-06): replace hand-rolled exporters with fpdf2+DejaVuSans and openpyxl |
| 03119c1 | feat(03-06): implement ARQ export task, job endpoints, and export tests |

## Self-Check: PASSED

- FOUND: backend/app/modules/billing/fonts/DejaVuSans.ttf
- FOUND: backend/app/modules/billing/fonts/DejaVuSans-Bold.ttf
- FOUND commit: b9208f5
- FOUND commit: 03119c1
- exporters.py has 5 FPDF/fpdf references, 5 Workbook/openpyxl references
- router.py has 3 new job endpoint patterns
- service.py has 2 new export job functions
- worker.py has 3 ExportJob references
