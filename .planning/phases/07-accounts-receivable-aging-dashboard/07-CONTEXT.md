# Phase 07 — Accounts Receivable + Aging Dashboard: Architecture Decisions

## Goal

A manager can see which clients owe money and for how long, generate a formal client
statement as a PDF, and export it — with all values correct relative to registered payments.

## What Already Exists (confirmed by code audit)

### Backend

- `get_ar_summary(db, tenant_id)` in `service.py` — fetches all `issued`/`overdue` invoices
  and buckets them by `_compute_aging()`. DOES NOT accept `as_of` param (uses `datetime.now()`
  internally). Must be extended — not replaced.
- `_compute_aging(document, today)` helper — computes `days_overdue` and `aging_bucket` from
  `due_date`. Correct logic, correct bucket names: `current / 1_30 / 31_60 / 61_90 / over_90`.
- `get_client_statement(db, tenant_id, client_id)` — returns total invoiced, total paid via
  `PaymentAllocation`, balance, and last 50 documents. Does NOT accept `as_of` param. Does NOT
  include `amount_paid` per document (only per-client totals). Statement table needs per-document
  outstanding for the UI.
- `GET /api/v1/billing/ar/summary` (router line 416) — uses `get_ar_summary` without `as_of`.
- `GET /api/v1/billing/clients/{client_id}/statement` (router line 425) — uses `get_client_statement`.
- Font path: `FONTS_DIR = Path(__file__).parent / "fonts"` → `DejaVuSans.ttf` confirmed present.
- `_RotasPDF` class in `exporters.py` — exact pattern to replicate for statement PDF.
- `BillingDocument` model has: `total_amount`, `due_date`, `issued_at`, `status`,
  `invoice_number`, `document_type`, `client_id`.
- `PaymentAllocation` model has: `payment_id`, `billing_document_id`, `amount_applied`.
- `ClientPayment` model has: `status` (confirmed/voided).

### Frontend

- `apps/manager/app/clientes/page.tsx` — Client registry list page. Has KPI strip (4 cards
  including "Saldo em Aberto"), DataTable, `loadClients()`. Uses `SidebarLayout active="clientes"`.
  THIS IS NOT THE AR PAGE — it shows the client registry, not aging buckets.
- `apps/manager/app/clientes/[id]/page.tsx` — Client detail page. Shows contracts, billing
  documents fetched from `/api/v1/billing/documents?client_id=...`. Has `PaymentModal`.
  MUST be EXTENDED with statement table and PDF download button — not replaced.
- `SidebarLayout.tsx` — Already has `{ key: "clientes", label: "Clientes", href: "/clientes",
  icon: Building2 }` under Financeiro section. No new sidebar entry needed — "Clientes" is
  already there.

## Architecture Decisions

### D-01: AR Dashboard is /ar page (not overwriting /clientes)

The `/clientes` page already exists as a client registry (list of clients with search/create).
The AR aging dashboard is a distinct concern. It lives at `/ar` as its own page.

Rationale: `/clientes` = "who are my clients", `/ar` = "who owes me money and for how long".
These are separate operational views. Mixing them would break the existing client registry.

Sidebar entry: Add `{ key: "ar", label: "Contas a Receber", href: "/ar", icon: ReceiptText }`
under Financeiro section, between "Cobrança" and "Análise".

### D-02: as_of param added to get_ar_summary service function

The existing `get_ar_summary` function accepts only `(db, tenant_id)`. The Phase 7 requirement
is to add `as_of: date | None = None` as an optional third parameter. When `as_of` is provided,
it is passed as the `today` argument to `_compute_aging()` so bucket assignment uses the
historical date, and `issued_at <= as_of` filtering is applied so future documents are excluded.

The router endpoint changes from `GET /api/v1/billing/ar/summary` to accept `?as_of=YYYY-MM-DD`.

Response gains `"as_of": as_of_date.isoformat()` field. When `as_of` is None, it echoes today.

### D-03: get_client_statement extended with as_of + per-document outstanding

The existing `get_client_statement` returns documents without per-row outstanding balances.
The Phase 7 statement table needs: invoice_number | issue_date | due_date | total_amount |
amount_paid | outstanding | status.

Extension: add `as_of: date | None = None` param. When provided, filter `issued_at <= as_of`
and `due_date <= as_of` on documents. Add per-document `amount_paid` and `outstanding` by
joining `PaymentAllocation` per document in a subquery (not N+1 — single aggregated query).

### D-04: Statement PDF uses _RotasPDF pattern from exporters.py

The `exporters.py` `_RotasPDF` class loads fonts from `FONTS_DIR = Path(__file__).parent / "fonts"`.
The statement PDF generator lives in `backend/app/modules/billing/service.py` (not a new file),
uses the same FONTS_DIR path, and replicates the `_RotasPDF` init pattern with a new
`_StatementPDF` subclass or a standalone function using `FPDF` directly.

Endpoint: `GET /api/v1/billing/clients/{client_id}/statement/pdf?as_of=YYYY-MM-DD`
Returns: `Response(content=pdf_bytes, media_type="application/pdf",
headers={"Content-Disposition": "attachment; filename=extrato_{client_id}.pdf"})`

### D-05: Frontend PDF download via Next.js API proxy

The PDF endpoint requires auth headers (JWT from HttpOnly cookie + X-Tenant-Id). The
manager app server actions can pass these via `apiFetch`, but a browser download requires
a same-origin URL that streams bytes. Solution: a Next.js API route at
`apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts` that calls `apiFetch`
and streams the bytes back as `application/pdf`.

The "Exportar PDF" button in `/clientes/[id]` POSTs to this proxy and triggers
`window.open(url)` or uses a `<a href="..." download>` link.

### D-06: Statement table added to existing /clientes/[id] page

The `/clientes/[id]/page.tsx` already shows billing documents. Rather than a separate
`/clientes/[id]/extrato` route, Phase 7 adds a "Extrato Conta Corrente" section to the
existing detail page using the extended `get_client_statement` data.

This avoids fragmenting the client detail across multiple routes.

### D-07: Top debtors on /ar uses ar-summary response + ranked client list

The AR summary endpoint returns aggregate bucket totals but not per-client breakdown.
To show "top 5 debtors", the service needs a companion query that groups by `client_id`,
sums outstanding, and returns the top 5. This is a new service function
`get_top_debtors(db, tenant_id, as_of, limit=5)` backed by a SQL GROUP BY query on
`BillingDocument` joined with `PaymentAllocation`. Returned data feeds the `/ar` dashboard.

### D-08: Composite index already exists

The ROADMAP notes: "Composite index `(tenant_id, client_id, due_date)` on `billing_documents`
is required for aging query performance — add in the Phase 7 migration if not already present."

The index `ix_billing_documents_tenant_client_due` on `(tenant_id, client_id, due_date)` is
confirmed present in the DB (Phase 5 migration). No new migration needed.

## Constraints (non-negotiable)

- Aging bucket source: `billing_documents.due_date` ONLY — not `issued_at + payment_terms_days`
- Outstanding per document: `total_amount - SUM(payment_allocations.amount_applied)` — NOT `paid_at`
- Only `status IN ('issued', 'overdue')` in aging — drafts and paid docs excluded
- `as_of` param makes aging testable without mocking `datetime.now()`
- PDF: fpdf2 + DejaVuSans.ttf — NO new PDF library
- All endpoints: tenant-scoped via JWT principal
- `PaymentAllocation.amount_applied` where `ClientPayment.status = 'confirmed'` — voided payments excluded

## Files Modified (summary across all plans)

### Wave 1 — Backend
- `backend/app/modules/billing/service.py` — extend `get_ar_summary`, `get_client_statement`,
  add `generate_client_statement_pdf`, `get_top_debtors`
- `backend/app/modules/billing/router.py` — add `as_of` param to `/ar/summary`,
  add `/clients/{client_id}/statement/pdf` endpoint
- `backend/tests/test_ar_phase7.py` — 6 new tests

### Wave 2 — Frontend
- `apps/manager/app/ar/page.tsx` — new AR dashboard page
- `apps/manager/app/components/SidebarLayout.tsx` — add "Contas a Receber" entry
- `apps/manager/app/clientes/[id]/page.tsx` — add statement section + PDF download
- `apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts` — PDF proxy

### Wave 3 — Checkpoint
- Visual verification of `/ar` and `/clientes/[id]` pages
