# Phase 24 Third-Party Hardening — Summary

**Date:** 2026-06-20
**Scope:** Correctness gaps identified post-audit in the `third_party` module.
**Browser validation:** pending manual QA.

---

## What was fixed

### Block A — Currency column on supplier_ledger_entries (tp10 migration)

**Problem:** `supplier_ledger_entries` had no `currency` column. `get_supplier_account` summed
all amounts regardless of currency, producing a meaningless scalar when MZN and USD entries coexisted.

**Fix:**
- Migration `tp10_ledger_currency.py`: `ADD COLUMN currency String(3) NOT NULL DEFAULT 'MZN'`
  with CHECK constraint `ck_sle_currency` (`MZN/USD/ZAR/EUR`) and composite index
  `ix_sle_currency(tenant_id, third_party_id, currency)`.
- `SupplierLedgerEntry` model: `currency: Mapped[str]` column added.
- `get_supplier_account`: now GROUPs by `currency`, returns `{"balances": {"MZN": {...}, "USD": {...}}, ...}`.
  Legacy scalar fields (`balance`, `total_credits`, `total_debits`) preserved using MZN totals for backward compat.
- `PaymentCreate` schema: `currency: str = "MZN"` field with `model_post_init` validator against
  `VALID_CURRENCIES`.
- `create_payment` service: passes `currency=payload.currency` to `SupplierLedgerEntry`.
- `serialize_ledger_entry`: includes `"currency"` in output.

**Commits:** `1aae94e`

---

### Block B — Per-criterion validation in create_evaluation (service fix)

**Problem:** `create_evaluation` validated weight sum but not individual criteria. A negative
weight or score > 10 passed silently through to the DB.

**Fix:** Added per-criterion loop before `total_weight` check:
- Weight must be in `(0, 1]` — raises `ApiError("invalid_criterion_weight", ..., 422)`
- Score must be in `[0, 10]` — raises `ApiError("invalid_criterion_score", ..., 422)`

**Commits:** `858599d`

---

### Block C — Immutability triggers (tp11 migration)

**Problem:** No DB-level protection on `supplier_ledger_entries` or `supplier_evaluations`.
Protection by "absence of PATCH/DELETE route" was insufficient against direct DB access.

**Fix:** Migration `tp11_immutability_triggers.py`:
- `raise_immutable_ledger()` PL/pgSQL function + `trg_sle_immutable` BEFORE UPDATE OR DELETE trigger
  on `supplier_ledger_entries`
- `raise_immutable_evaluation()` PL/pgSQL function + `trg_se_immutable` BEFORE UPDATE OR DELETE
  trigger on `supplier_evaluations`
- Downgrade drops both triggers and functions cleanly.

**Commits:** `949f7c4`

---

### Block D — Correctness tests (12 new tests)

**File:** `backend/tests/test_third_party_phase24.py`

| Test | What it asserts |
|---|---|
| `test_create_and_list_contacts` | Create → 201 with name/role/phone; list contains it; delete → 204; list is empty |
| `test_contact_cross_tenant_isolation` | Tenant B gets 404 accessing Tenant A's third_party contacts |
| `test_supplier_account_balance_correctness` | Exact Decimal: credits=500.00, debits=200.00, balance=300.00; MZN in balances dict |
| `test_supplier_account_multi_currency` | MZN=1000.00 and USD=200.00 tracked separately, not summed |
| `test_create_payment_idempotency_replay` | Same key → same id; only 1 entry in account list |
| `test_create_evaluation_score_correctness` | 0.6×8.0 + 0.4×5.0 = exactly 6.80 |
| `test_create_evaluation_invalid_criteria_rejected` | Negative weight → 422; score > 10 → 422; weights sum 0.5 → 422 |
| `test_create_evaluation_idempotency_replay` | Same key → same id; only 1 evaluation in list |
| `test_list_evaluations_average_score` | (6.80 + 8.00) / 2 = exactly 7.40 |
| `test_ledger_immutability` | DB UPDATE raises; DB DELETE raises (trigger fires) |
| `test_evaluation_immutability` | DB UPDATE raises; DB DELETE raises (trigger fires) |
| `test_account_cross_tenant_isolation` | Tenant B gets 404 accessing Tenant A's third_party account |

**Commits:** `8240e8c`

---

## Final test counts

- **New tests:** 12 (all passing)
- **Full suite:** 351 passed, 2 skipped (no regressions)
- **Ruff:** 0 errors on `app/modules/third_party/`

---

## Open items

- **Browser validation:** pending manual QA — cannot be verified via CLI.
