---
phase: 15
slug: fiscal-compliance-seguran-a-de-carga
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-18
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2 + pytest-asyncio (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` (`tool.pytest.ini_options`) |
| **Quick run command** | `cd backend && python -m pytest tests/test_fiscal_compliance.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds (quick) / ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_fiscal_compliance.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | FISC-01 | unit | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_first_two -x` | ❌ Wave 0 | ⬜ pending |
| 15-01-02 | 01 | 1 | FISC-01 | unit (asyncio) | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_concurrent -x` | ❌ Wave 0 | ⬜ pending |
| 15-01-03 | 01 | 1 | FISC-01 | unit | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_cross_tenant -x` | ❌ Wave 0 | ⬜ pending |
| 15-01-04 | 01 | 1 | FISC-01 | unit (mock) | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_integrity_error_retry -x` | ❌ Wave 0 | ⬜ pending |
| 15-02-01 | 02 | 1 | FISC-02 | unit | `pytest tests/test_fiscal_compliance.py::test_iva_calculation_standard -x` | ❌ Wave 0 | ⬜ pending |
| 15-02-02 | 02 | 1 | FISC-02 | unit | `pytest tests/test_fiscal_compliance.py::test_iva_mixed_rates -x` | ❌ Wave 0 | ⬜ pending |
| 15-02-03 | 02 | 2 | FISC-02 | unit | `pytest tests/test_billing_export.py::test_pdf_contains_iva_section -x` | ❌ Wave 0 | ⬜ pending |
| 15-02-04 | 02 | 2 | FISC-02 | unit | `pytest tests/test_billing_export.py::test_xlsx_iva_rows -x` | ❌ Wave 0 | ⬜ pending |
| 15-03-01 | 03 | 2 | FISC-03 | unit | `pytest tests/test_fiscal_compliance.py::test_compliance_report_xlsx_columns -x` | ❌ Wave 0 | ⬜ pending |
| 15-03-02 | 03 | 2 | FISC-03 | unit (mock arq) | `pytest tests/test_fiscal_compliance.py::test_compliance_report_job_lifecycle -x` | ❌ Wave 0 | ⬜ pending |
| 15-04-01 | 04 | 1 | LOAD-01 | integration | `pytest tests/test_fiscal_compliance.py::test_payload_exceeded_create_trip -x` | ❌ Wave 0 | ⬜ pending |
| 15-04-02 | 04 | 1 | LOAD-01 | integration | `pytest tests/test_fiscal_compliance.py::test_payload_within_limit -x` | ❌ Wave 0 | ⬜ pending |
| 15-04-03 | 04 | 1 | LOAD-01 | unit | `pytest tests/test_fiscal_compliance.py::test_payload_guard_null_vehicle_limit -x` | ❌ Wave 0 | ⬜ pending |
| 15-04-04 | 04 | 1 | LOAD-01 | integration | `pytest tests/test_fiscal_compliance.py::test_payload_override_admin -x` | ❌ Wave 0 | ⬜ pending |
| 15-04-05 | 04 | 1 | LOAD-01 | integration | `pytest tests/test_fiscal_compliance.py::test_payload_exceeded_start_trip -x` | ❌ Wave 0 | ⬜ pending |
| 15-05-01 | 05 | 2 | LOAD-02 | integration | `pytest tests/test_fiscal_compliance.py::test_hazmat_load_permit_missing_class -x` | ❌ Wave 0 | ⬜ pending |
| 15-05-02 | 05 | 2 | LOAD-02 | integration | `pytest tests/test_fiscal_compliance.py::test_hazmat_load_permit_with_class -x` | ❌ Wave 0 | ⬜ pending |
| 15-05-03 | 05 | 2 | LOAD-02 | integration | `pytest tests/test_fiscal_compliance.py::test_non_hazmat_load_permit -x` | ❌ Wave 0 | ⬜ pending |
| 15-05-04 | 05 | 2 | LOAD-02 | integration | `pytest tests/test_fiscal_compliance.py::test_hazmat_alert_on_start_trip -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_fiscal_compliance.py` — stub file with all 19 test functions listed above
- [ ] `backend/tests/test_billing_export.py` — extend existing file with `test_pdf_contains_iva_section` and `test_xlsx_iva_rows` stubs

*Existing infrastructure (`backend/pyproject.toml`, `conftest.py`) covers framework setup — no new installs needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Compliance XLSX opens in Excel/LibreOffice and columns display correctly | FISC-03 | Binary file rendering is visual | Download XLSX from compliance endpoint, open in spreadsheet app, verify column headers and data alignment |
| Invoice PDF with IVA line renders correctly for Mozambican characters (diacritics) | FISC-02 | PDF rendering is visual | Generate a billing PDF, verify IVA line shows "17%" and Mozambican tenant name renders without corruption |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
