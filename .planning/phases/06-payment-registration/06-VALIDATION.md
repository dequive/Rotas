---
phase: 6
slug: payment-registration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-19
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2 + pytest-asyncio 0.23 (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_payments.py -x -q` |
| **Full suite command** | `cd backend && python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds (payment tests only), ~60 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/test_payments.py -x -q`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | PAY-01, PAY-02, PAY-03 | stub/tdd | `cd backend && python -m pytest tests/test_payments.py --collect-only -q` | ❌ Wave 0 | ⬜ pending |
| 06-02-01 | 02 | 2 | PAY-01 | integration | `cd backend && python -m pytest tests/test_payments.py::test_register_full_payment tests/test_payments.py::test_register_partial_payment -x -q` | ❌ Wave 0 | ⬜ pending |
| 06-02-02 | 02 | 2 | PAY-01 | integration | `cd backend && python -m pytest tests/test_payments.py::test_payment_idempotency tests/test_payments.py::test_payment_client_mismatch tests/test_payments.py::test_payment_exceeds_balance -x -q` | ❌ Wave 0 | ⬜ pending |
| 06-02-03 | 02 | 2 | PAY-02 | integration | `cd backend && python -m pytest tests/test_payments.py::test_advance_payment tests/test_payments.py::test_apply_advance tests/test_payments.py::test_advance_over_applied -x -q` | ❌ Wave 0 | ⬜ pending |
| 06-02-04 | 02 | 2 | PAY-03 | integration | `cd backend && python -m pytest tests/test_payments.py::test_balance_updated_after_payment tests/test_payments.py::test_void_restores_balance -x -q` | ❌ Wave 0 | ⬜ pending |
| 06-03-01 | 03 | 3 | PAY-01, PAY-02, PAY-03 | integration | `cd backend && python -m pytest tests/test_payments.py -x -q` | ❌ Wave 0 | ⬜ pending |
| 06-04-01 | 04 | 4 | PAY-01, PAY-02, PAY-03 | manual | Human verification checkpoint — see manual verifications below | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_payments.py` — 10 test stubs for PAY-01, PAY-02, PAY-03 (created in Plan 06-01):
  - `test_register_full_payment` — PAY-01
  - `test_register_partial_payment` — PAY-01
  - `test_payment_idempotency` — PAY-01
  - `test_payment_client_mismatch` — PAY-01
  - `test_payment_exceeds_balance` — PAY-01
  - `test_advance_payment` — PAY-02
  - `test_apply_advance` — PAY-02
  - `test_advance_over_applied` — PAY-02
  - `test_balance_updated_after_payment` — PAY-03
  - `test_void_restores_balance` — PAY-03
- [ ] No new conftest fixtures needed — `db`, `tenant_id`, `auth_headers` from existing `conftest.py` are sufficient

*Existing test infrastructure covers all phase requirements — no new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| PaymentModal opens in /cobranca, renders invoice number, submits successfully | PAY-01 | Requires running browser + dev server | Navigate to /cobranca, click "Registar Pagamento", fill form, submit; verify modal closes and page refreshes |
| Advance payment flow in /clientes/[id] | PAY-02 | Requires running browser + dev server | Navigate to /clientes/[id], click "Registar Adiantamento", submit with no invoice; verify success |
| IBM Plex Mono rendered on amount input | PAY-01 | Visual check only | Open PaymentModal in browser, inspect amount input font in DevTools |
| Double-submit safety: second click shows "A registar..." disabled | PAY-01 | Requires timing-sensitive user interaction | Click "Registar" twice rapidly; verify button is disabled after first click |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
