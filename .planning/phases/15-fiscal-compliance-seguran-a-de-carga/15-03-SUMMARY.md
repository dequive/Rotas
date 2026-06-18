---
plan: "03"
phase: 15-fiscal-compliance-seguran-a-de-carga
status: complete
wave: 2
---

# Plan 15-03 Summary — FISC-01 Sequential Invoice Numbers

## What was done

- `billing/service.py`: Added `_assign_invoice_number()` helper that:
  - Lazy-creates a per-tenant per-year PostgreSQL SEQUENCE (`invoice_seq_{tid_clean}_{year}`)
  - Calls `SELECT nextval(seq_name)` and formats as `YYYY/NNNN`
  - Is idempotent (returns existing number if already assigned)
- `billing/service.py`: `issue_document()` now calls `_assign_invoice_number()` BEFORE setting `status="issued"` (invoice number only assigned at issue time, never at draft creation)
- `billing/service.py`: IntegrityError retry loop around `db.flush()` handles the (theoretical) duplicate constraint case
- `billing/service.py`: `serialize_billing_document()` and `serialize_billing_document_summary()` now include `invoice_number` and `iva_rate` fields
- Audit log in `issue_document()` now records `invoice_number`

## Key decisions
- Sequence name uses `replace("-", "")` (no hyphens, no underscores) matching the migration that seeded sequences for existing tenants
- Annual reset is automatic: new sequence created per year
