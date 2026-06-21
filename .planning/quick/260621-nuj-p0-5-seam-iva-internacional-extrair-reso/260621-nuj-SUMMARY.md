---
phase: quick-260621-nuj
plan: 01
subsystem: billing
tags: [iva, domain, migration, service-wiring]
dependency_graph:
  requires: []
  provides: [resolve_iva, iva_basis columns]
  affects: [billing/domain.py, billing/models.py, billing/service.py, alembic/iva01]
tech_stack:
  added: []
  patterns: [domain-seam, fail-closed-guard, getattr-fallback]
key_files:
  created:
    - backend/alembic/versions/iva01_iva_basis_columns.py
  modified:
    - backend/app/modules/billing/domain.py
    - backend/app/modules/billing/models.py
    - backend/app/modules/billing/service.py
    - backend/tests/test_billing_domain.py
decisions:
  - "resolve_iva lives in domain.py, not service.py — keeps business rules testable without DB"
  - "International trips fail-closed with 422 until legal confirmation; contract.iva_rate override bypasses the guard"
  - "debit/credit note signatures changed from Decimal=DEFAULT_IVA_RATE to Decimal|None=None — callers unaffected, resolve_iva provides the default"
  - "Contract.iva_rate does not exist on the model — getattr(contract, 'iva_rate', None) fallback used throughout"
metrics:
  duration: ~25min
  completed: 2026-06-21
  tasks_completed: 2
  files_changed: 5
---

# Phase quick-260621-nuj Plan 01: IVA Seam — resolve_iva domain function + iva_basis columns + service wiring

**One-liner:** Fail-closed IVA resolution seam in domain.py — domestic trips get standard_16 (16%), international trips raise 422 until a contract override is configured, with iva_basis audit trail persisted on every billing row.

## What Was Built

### resolve_iva function (domain.py)

`resolve_iva(trip, contract) -> tuple[Decimal, str]` with priority order:

1. `contract.iva_rate is not None` → returns `(contract.iva_rate, "contract_override")` — bypasses all checks
2. `trip.is_international is True` → raises `ApiError("international_iva_rate_unconfirmed", ..., 422)` — fail-closed
3. Otherwise → returns `(Decimal("0.1600"), "standard_16")` — domestic default

`trip=None` and `contract=None` are safe (debit/credit note callers pass `None` for both).

### Basis strings

| Value | Meaning |
|---|---|
| `standard_16` | Domestic Mozambican transport, 16% IVA |
| `contract_override` | Explicit rate configured on the contract |
| *(422 raised)* | International trip with no override — operator must act |

### iva_basis columns

- `BillingDocument.iva_basis VARCHAR(40) NULLABLE` — added to model + migration
- `BillingItem.iva_basis VARCHAR(40) NULLABLE` — added to model + migration
- Migration revision: `iva01a1b2c3d4`, down_revision: `fisc01`
- Migration applied: `alembic upgrade head` confirmed at `iva01a1b2c3d4 (head)`

### service.py wiring

All 3 `DEFAULT_IVA_RATE` call sites replaced:

| Location | Before | After |
|---|---|---|
| `create_document` line ~618 | `iva_rate = DEFAULT_IVA_RATE` | `iva_rate, iva_basis = resolve_iva(trip, contract)` + `iva_basis=iva_basis` on BillingItem |
| `create_debit_note` signature | `iva_rate: Decimal = DEFAULT_IVA_RATE` | `iva_rate: Decimal \| None = None` + resolve_iva inside body |
| `create_credit_note` signature | `iva_rate: Decimal = DEFAULT_IVA_RATE` | `iva_rate: Decimal \| None = None` + resolve_iva inside body |

`DEFAULT_IVA_RATE` local definition removed from service.py. The constant remains in domain.py as the single source of truth.

### Contract.iva_rate note

`Contract` model does **not** have an `iva_rate` column. `getattr(contract, "iva_rate", None)` fallback is used throughout so the override path is ready the moment the column is added — no code change needed then.

## Tests

| Suite | Before | After |
|---|---|---|
| test_billing_domain.py | 5 tests | 8 tests (3 new resolve_iva tests) |
| Full billing suite | — | 43 passed |

New tests:
- `test_resolve_iva_domestic_returns_standard_16`
- `test_resolve_iva_international_raises_422`
- `test_resolve_iva_contract_override_wins_for_international`

## Commits

| Hash | Files | Description |
|---|---|---|
| `150e485` | models.py | iva_basis columns on BillingDocument and BillingItem |
| `076da7c` | iva01_iva_basis_columns.py | Alembic migration |
| *(earlier)* | domain.py, test_billing_domain.py | resolve_iva + 3 tests |
| `2db084a` | service.py | Wire resolve_iva at all 3 call sites |

## Deviations from Plan

None — plan executed exactly as written. The partial implementation found at start (domain.py + tests already done, models already done) was consistent with the plan's stated context. Remaining work (migration application confirmation, service.py wiring, ruff fix) completed as specified.

One minor auto-fix: ruff I001 (import sort) — `billing.domain` import placed after `billing.exporters` initially, reordered to satisfy isort.

## Known Stubs

None — all wiring is live. `contract.iva_rate` fallback via `getattr` is intentional and documented above.
