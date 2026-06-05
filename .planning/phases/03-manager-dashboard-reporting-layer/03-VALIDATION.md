---
phase: 3
slug: manager-dashboard-reporting-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio (backend); no frontend test framework detected |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q --tb=short` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v` |
| **Estimated runtime** | ~30–60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q --tb=short`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 0 | CT-01 | unit | `pytest tests/test_control_tower_optimized.py -x -q` | ❌ W0 | ⬜ pending |
| 3-01-02 | 01 | 0 | CT-02 | unit | `pytest tests/test_control_tower_optimized.py -k "cache" -x -q` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | CT-01 | integration | `pytest tests/test_control_tower_optimized.py -k "n_plus_one" -v` | ❌ W0 | ⬜ pending |
| 3-01-04 | 01 | 1 | CT-03 | integration | `pytest tests/test_control_tower_optimized.py -k "pagination" -v` | ❌ W0 | ⬜ pending |
| 3-02-01 | 02 | 0 | BILL-01 | unit | `pytest tests/test_billing_export.py -k "pdf" -x -q` | ❌ W0 | ⬜ pending |
| 3-02-02 | 02 | 0 | BILL-02 | unit | `pytest tests/test_billing_export.py -k "xlsx" -x -q` | ❌ W0 | ⬜ pending |
| 3-02-03 | 02 | 1 | BILL-03 | integration | `pytest tests/test_waiver_flow.py -k "waiver" -v` | ❌ W0 | ⬜ pending |
| 3-03-01 | 03 | 1 | RPT-01 | integration | `pytest tests/test_analytics_api.py -x -q` | ❌ W0 | ⬜ pending |
| 3-03-02 | 03 | 1 | RPT-02 | integration | `pytest tests/test_analytics_api.py -k "expiry" -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_control_tower_optimized.py` — stubs for CT-01, CT-02, CT-03 (N+1 query count assertions, Redis cache hit/miss, pagination)
- [ ] `backend/tests/test_billing_export.py` — stubs for BILL-01, BILL-02 (PDF UTF-8 output, XLSX column format)
- [ ] `backend/tests/test_waiver_flow.py` — stubs for BILL-03 (waiver create/approve/reject flow)
- [ ] `backend/tests/test_analytics_api.py` — stubs for RPT-01 (KPI calculations), RPT-02 (document expiry query)
- [ ] `backend/tests/conftest.py` — add Redis mock fixture and ARQ worker fixture

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PDF renders Mozambican names (ã, ç, â, ê) correctly | BILL-01 | Requires visual inspection of PDF output | Generate invoice PDF for a trip where driver/vehicle names contain diacritics; open and verify characters are not corrupted |
| XLSX currency columns right-aligned with `#,##0.00` | BILL-02 | Requires spreadsheet application to verify formatting | Open generated XLSX in LibreOffice or Excel; confirm currency columns are right-aligned with two decimal places |
| Waiver modal flow (request → approve → invoice) | BILL-03 | Multi-user UI flow | Login as manager → open billing queue → click "Solicitar waiver" on negative-margin trip → submit justification → login as owner → approve → confirm trip enters billing queue |
| Control Tower loads in under 3 seconds for 20 vehicles | CT-01 | Requires populated DB with real data volume | Seed DB with 20 vehicles + 50 trips; open Control Tower; measure network tab load time |
| Document expiry 3-level color thresholds (30/15/7 days) | RPT-02 | Visual color inspection | Seed vehicles with documents expiring at 31, 15, 7, 6 days; open Control Tower; verify correct orange/light-red/red colors |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
