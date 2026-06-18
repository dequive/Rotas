---
phase: 05
slug: client-registry-migration-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-19
---

# Phase 05 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && python -m pytest tests/test_clients_api.py tests/test_billing_api.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest -x -q` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_clients_api.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 0 | CLI-01 | stub | `pytest tests/test_clients_api.py -x -q` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | CLI-01 | integration | `pytest tests/test_clients_api.py::test_create_client -x -q` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | CLI-01 | integration | `pytest tests/test_clients_api.py::test_list_clients_tenant_scoped -x -q` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | CLI-03 | migration | `cd backend && alembic upgrade head` | ✅ | ⬜ pending |
| 05-02-02 | 02 | 1 | CLI-03 | sql | `psql -c "SELECT count(*) FROM contracts WHERE client_id IS NULL"` | ✅ | ⬜ pending |
| 05-03-01 | 03 | 2 | CLI-02 | integration | `pytest tests/test_clients_api.py::test_credit_limit_warning -x -q` | ❌ W0 | ⬜ pending |
| 05-04-01 | 04 | 2 | CLI-04 | integration | `pytest tests/test_contracts_api.py::test_create_contract_with_client_id -x -q` | ✅ | ⬜ pending |
| 05-05-01 | 05 | 3 | CLI-05 | integration | `pytest tests/test_billing_api.py::test_invoice_number_format -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_clients_api.py` — stubs for CLI-01 (CRUD), CLI-02 (credit limit), CLI-03 (backfill assertion)
- [ ] Fixtures in `backend/tests/conftest.py` — `client_payload` fixture with NUIT, trading_name, address, phone, email, payment_terms, credit_limit

*CLI-04 and CLI-05 use existing test files (`test_contracts_api.py`, `test_billing_api.py`) — no new stub files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Client combobox search UX in contract form | CLI-04 | Browser interaction required | Open /contratos → new contract → type 2+ chars in client field → assert dropdown appears with matching results |
| Credit limit warning renders on /clientes/[id] | CLI-02 | UI rendering in Next.js | Create client with credit_limit=1000 → create billing doc for 1200 → open /clientes/[id] → assert amber/red warning strip visible |
| /clientes page search and KPIs load | CLI-01 | SSR page with real data | Navigate to /clientes → assert KPI cards render → type in search → assert list filters |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
