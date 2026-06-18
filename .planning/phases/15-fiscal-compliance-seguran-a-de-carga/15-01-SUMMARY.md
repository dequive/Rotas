---
plan: 15-01
phase: 15-fiscal-compliance-seguran-a-de-carga
status: complete
completed: 2026-06-18
wave: 1
---

# Plan 15-01 — DDL Migration + ORM Models Complete

## What Was Built

**Migration** `c7d8e9f0a1b2_phase15_fiscal_load_columns.py`:
- `billing_documents`: `invoice_number VARCHAR(12)`, `iva_rate NUMERIC(5,4)` + unique constraint `uq_billing_docs_tenant_invoice_number`
- `billing_items`: `iva_rate NUMERIC(5,4)`, `iva_amount NUMERIC(10,2)`
- `vehicles`: `max_payload_kg NUMERIC(10,2)`
- `trips`: `payload_override_reason TEXT`, `is_hazmat BOOLEAN DEFAULT false`, `hazmat_class VARCHAR(10)`, `un_number VARCHAR(10)`, `hazmat_label VARCHAR(50)`
- `cargo_manifests`: same 4 hazmat fields
- `contracts`: `client_nuit VARCHAR(20)`
- `tenants`: `nuit VARCHAR(20)`
- Per-tenant invoice sequences `invoice_seq_{tid_no_hyphens}_2026` for all existing tenants

**ORM models updated** (7 files): `billing/models.py`, `vehicles/models.py`, `trips/models.py`, `cargo/models.py`, `contracts/models.py`, `tenants/models.py` — all Mapped[] annotations added.

## Verification

```
alembic upgrade head → b9c8d7e6f5a4 -> c7d8e9f0a1b2 (success)
all models import OK
152 passed, 21 skipped, 0 failed
```

## Key Files

- `backend/alembic/versions/c7d8e9f0a1b2_phase15_fiscal_load_columns.py`
- All 7 ORM model files

## Self-Check: PASSED
