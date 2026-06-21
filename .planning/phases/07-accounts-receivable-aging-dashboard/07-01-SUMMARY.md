---
phase: 07
plan: 01
status: done
completed: 2026-06-21
---

# 07-01 SUMMARY — AR Backend Extensions

## What shipped

- `get_ar_summary(db, tenant_id, as_of)` — `as_of` param controls aging reference date; response includes `"as_of"` ISO field
- `get_client_statement(db, tenant_id, client_id, as_of)` — per-document `amount_paid` and `outstanding` via bulk allocation query; excludes voided payments
- `get_top_debtors(db, tenant_id, as_of, limit)` — aggregates by client, sorts by outstanding desc, returns worst aging bucket
- `generate_client_statement_pdf(db, tenant_id, client_id, as_of)` — fpdf2 + DejaVuSans, navy header, 7-column table, total footer in MZN
- `GET /api/v1/billing/ar/summary?as_of=` — updated endpoint
- `GET /api/v1/billing/clients/{id}/statement?as_of=` — updated with per-doc amounts
- `GET /api/v1/billing/ar/top-debtors?as_of=&limit=` — new endpoint
- `GET /api/v1/billing/clients/{id}/statement/pdf?as_of=` — new PDF streaming endpoint

## Result

ruff clean. All functions verified via ast.parse checks.
