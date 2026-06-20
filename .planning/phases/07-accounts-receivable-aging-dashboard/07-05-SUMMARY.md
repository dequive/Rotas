---
phase: 07
plan: 07-05
type: summary
subsystem: billing, frontend
tags: [ar, aging, client-statement, pdf, accounts-receivable]
dependency_graph:
  requires: [06]
  provides: [ar-dashboard-complete]
metrics:
  duration: ~2h total (waves 1+2)
  completed_date: "2026-06-20"
  tasks_completed: 4
  tests_added: 6
  tests_total: 363
---

# Phase 7: Accounts Receivable + Aging Dashboard — Complete

**One-liner:** AR dashboard live with point-in-time aging, per-doc outstanding from payment_allocations, client statement PDF, and 6 correctness tests that assert Decimal values.

---

## What Was Delivered

### Backend (07-01)
- `get_ar_summary`: optional `as_of: date` param; aging uses `billing_documents.due_date`; response includes `as_of` field; only `status='issued'` docs
- `get_client_statement`: `as_of` param; outstanding per doc = `total_amount - SUM(payment_allocations.amount_applied)` — NOT `paid_at`
- `generate_client_statement_pdf`: fpdf2 + DejaVuSans, tenant header, client block, 7-col table, footer totals
- `GET /billing/ar/summary?as_of=YYYY-MM-DD` — with as_of
- `GET /billing/ar/top-debtors?limit=N&as_of=` — top N clients by outstanding
- `GET /billing/clients/{id}/statement/pdf?as_of=` — streams PDF bytes

### Tests (07-02) — 6/6 pass, all assert Decimal values
- `test_ar_summary_buckets_correct`: invoice in 31_60 bucket asserted by amount
- `test_ar_summary_as_of_param`: as_of=yesterday excludes today's invoice
- `test_ar_summary_excludes_drafts`: draft not in AR
- `test_client_statement_outstanding_correct`: 1000 MZN invoice - 400 MZN payment = "600.00" outstanding
- `test_client_statement_pdf_returns_bytes`: PDF endpoint returns real bytes (len > 1000)
- `test_ar_cross_tenant`: tenant B cannot see tenant A AR

### Frontend (07-03 + 07-04)
- `apps/manager/app/ar/page.tsx`: KPI cards, 5-bucket aging grid (amber/red coding), top debtors table, as_of date picker, sidebar "Contas a Receber"
- `apps/manager/app/clientes/[id]/page.tsx`: balance hero (IBM Plex Mono, red if >0), 7-col statement table, "Exportar PDF" button
- `apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts`: PDF proxy with Content-Disposition: attachment

### Final Suite
- `pytest`: **363 passed, 2 skipped** — 0 failures
- `tsc --noEmit`: **0 errors**

## Self-Check: PASSED
- [x] as_of param works and returns as_of in response
- [x] Outstanding computed from payment_allocations, not paid_at
- [x] Drafts excluded from aging
- [x] PDF streams real bytes via fpdf2+DejaVuSans
- [x] Composite index already existed — no migration needed
- [x] 363 tests pass, 0 failures
- [x] tsc clean
- [x] Browser validation: pending manual QA
