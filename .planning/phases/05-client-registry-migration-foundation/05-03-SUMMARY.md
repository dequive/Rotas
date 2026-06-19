---
phase: 05-client-registry-migration-foundation
plan: 03
subsystem: ui
tags: [nextjs, react, typescript, client-registry, sidebar, modal]

# Dependency graph
requires:
  - phase: 05-01
    provides: "clients API endpoints (GET /api/v1/clients, POST, PATCH), ClientResponse type, outstanding_balance service"
  - phase: 05-02
    provides: "client_id FK on billing_documents and contracts, due_date on billing_documents"
provides:
  - "/clientes list page — KPI strip, searchable DataTable (7 columns), NovoClienteButton, ClientsTable"
  - "/clientes/[id] detail page — info card, credit limit warning strip (80%/100% thresholds), contracts panel, invoices panel"
  - "ClientFormModal — 9-field create/edit dialog with Portuguese labels, field validation, deactivate action"
  - "SidebarLayout Financeiro section includes Clientes as first item with Building2 icon"
  - "StatusBadge extended with 'activo' (success) and 'inactivo' (error) client statuses"
  - "clients-api.ts — ClientResponse interface and loadClients() helper"
  - "/api/clients and /api/clients/[id] — Next.js proxy routes injecting auth headers"
affects: [05-04, 05-05, phase-06-payments, phase-07-ar]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Server Component data loading with apiFetch() + client-side sub-component for interactivity (NovoClienteButton, ClientsTable, EditarClienteButton)"
    - "ClientFormModal uses /api/* proxy routes (not direct backend URL) to inject httpOnly cookie auth headers"
    - "Credit limit warning computed client-side: pct = (outstanding_balance / credit_limit) * 100; 80% = warning, 100% = error"
    - "KPI computations from list response rather than separate summary endpoint"

key-files:
  created:
    - apps/manager/app/clientes/page.tsx
    - apps/manager/app/clientes/ClientsTable.tsx
    - apps/manager/app/clientes/NovoClienteButton.tsx
    - apps/manager/app/clientes/[id]/page.tsx
    - apps/manager/app/clientes/[id]/EditarClienteButton.tsx
    - apps/manager/app/components/ClientFormModal.tsx
    - apps/manager/app/lib/clients-api.ts
    - apps/manager/app/api/clients/route.ts
    - apps/manager/app/api/clients/[id]/route.ts
  modified:
    - apps/manager/app/components/SidebarLayout.tsx
    - apps/manager/app/components/ui/StatusBadge.tsx

key-decisions:
  - "KPI card 'Contratos Activos' shows '—' placeholder — contract count by client not available from /api/v1/clients list endpoint; deferred to Phase 6+ when client_id filter on /api/v1/contracts is confirmed"
  - "Contracts and billing documents filtered client-side (client_id === id) since backend may not support ?client_id= query param yet"
  - "ClientFormModal uses Next.js API proxy routes (/api/clients) to avoid exposing backend URL to browser and to inject httpOnly cookie auth headers"
  - "Credit warning strip implemented with inline style vars (not shadcn Alert) to match exact DESIGN.md warning-bg/error-bg tokens"

patterns-established:
  - "Server Component page + 'use client' sub-components: page.tsx fetches data server-side; ClientsTable/NovoClienteButton manage UI state client-side"
  - "Modal mutation pattern: fetch /api/* proxy → router.refresh() to revalidate Server Component data"
  - "MonoCell used for all monetary values (MZN), NUIT (9-digit tax ID), and invoice numbers — never Manrope"

requirements-completed: [CLI-01, CLI-02]

# Metrics
duration: 45min
completed: 2026-06-19
---

# Phase 05 Plan 03: /clientes Frontend — List, Detail, Sidebar Nav Summary

**Manager dashboard gains a full client registry UI: searchable list page with 4 KPI cards, detail page with credit limit warning strip (amber at 80%, red at 100%), ClientFormModal with 9 fields and Portuguese copywriting, and Clientes added as first item in the Financeiro sidebar section.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-06-19T00:00:00Z
- **Completed:** 2026-06-19
- **Tasks:** 4
- **Files modified:** 11

## Accomplishments

- Full /clientes list page: 4 KPI cards (active clients, outstanding balance, limit exceeded, contracts), searchable 7-column DataTable, EmptyState for zero clients
- Full /clientes/[id] detail page: two-column info card with NUIT/email/phone/address, credit limit warning strip at 80% (amber) and 100% (red/destructive), contracts panel with EmptyState, invoices panel with EmptyState
- ClientFormModal with all 9 fields per UI-SPEC (trading_name, legal_name, NUIT, address, city, phone, email, payment_terms_days, credit_limit), two-column layout, field validation, API error display, deactivate action in edit mode
- StatusBadge extended with 'activo' (success/green) and 'inactivo' (error/red) client status keys
- SidebarLayout Financeiro section: Clientes added as first item with Building2 icon (nav key: "clientes")
- `npx next build` passes with 0 TypeScript errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Sidebar nav — add Clientes to Financeiro section** - Pre-existing in `SidebarLayout.tsx` (Building2 import + clientes nav entry already committed)
2. **Task 2: ClientFormModal — create/edit dialog** - `e2aaee5` (feat(05-03): add ClientFormModal with 9 fields, create/edit modes, and API proxy routes)
3. **Task 3: /clientes list page** - `294426f` (feat(05-03): add /clientes list page with KPI strip, searchable table, and StatusBadge client statuses)
4. **Task 4: /clientes/[id] detail page** - `8fbff65` (feat(05-03): add /clientes/[id] detail page with info card, credit warning strip, contracts and invoices panels)

## Files Created/Modified

- `apps/manager/app/clientes/page.tsx` — Server Component: SidebarLayout, PageHeader, 4 KpiCards, ClientsTable
- `apps/manager/app/clientes/ClientsTable.tsx` — Client component: search input + DataTable with 7 columns + edit modal trigger
- `apps/manager/app/clientes/NovoClienteButton.tsx` — Client component: "Novo Cliente" amber CTA + ClientFormModal in create mode
- `apps/manager/app/clientes/[id]/page.tsx` — Server Component: info card, credit warning strip, contracts + invoices panels
- `apps/manager/app/clientes/[id]/EditarClienteButton.tsx` — Client component: "Editar" outline button + ClientFormModal in edit mode
- `apps/manager/app/components/ClientFormModal.tsx` — 9-field modal, create/edit/deactivate, Portuguese labels, validation
- `apps/manager/app/lib/clients-api.ts` — ClientResponse interface + loadClients() server-side helper
- `apps/manager/app/api/clients/route.ts` — Next.js proxy: GET/POST → /api/v1/clients with auth headers
- `apps/manager/app/api/clients/[id]/route.ts` — Next.js proxy: GET/PATCH → /api/v1/clients/{id} with auth headers
- `apps/manager/app/components/SidebarLayout.tsx` — Building2 import + clientes nav entry in Financeiro section
- `apps/manager/app/components/ui/StatusBadge.tsx` — Added 'activo' and 'inactivo' status keys

## Decisions Made

- KPI card "Contratos Activos" shows "—" placeholder because contract count per client is not in the /api/v1/clients list response. This is a known limitation — Phase 6 or 7 will add this when contract filtering by client_id is confirmed available.
- Contracts and billing documents on the detail page filtered client-side (c.client_id === id) since the backend ?client_id= query param availability was not confirmed; client-side filter is safe for ≤200 records.
- ClientFormModal uses Next.js /api/* proxy routes (not direct fetch to backend URL) to correctly inject httpOnly cookie auth headers from the server session.
- Credit warning implemented with direct style vars from DESIGN.md tokens (--warning-bg/--error-bg) rather than shadcn Alert component to ensure exact color fidelity.

## Deviations from Plan

None — plan executed exactly as written. All 4 tasks match the spec. The SidebarLayout was confirmed to already have the Clientes nav entry from prior session work.

## Known Stubs

- **KPI card "Contratos Activos"** — `apps/manager/app/clientes/page.tsx` line ~65: value is hardcoded `"—"`. Contract count by client is not available from the current /api/v1/clients endpoint. This does not prevent the plan's goal (client list/detail/modal) — it is a display placeholder. Future plan (Phase 5 plan 4 or Phase 6) should add an aggregate count or separate endpoint.

## Issues Encountered

- Windows `.next` cache caused `EINVAL: invalid argument, readlink` on the first build attempt. Resolved by deleting `.next/` before rebuild — this is a known Windows/OneDrive symlink issue with the Next.js cache, not a code error.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 05 Plan 04: ContractFormModal ClientCombobox — the /clientes infrastructure is now live; ClientCombobox can fetch GET /api/v1/clients and display results with the ClientResponse type
- Phase 05 Plan 05: backend client API completeness (list, get, create, patch, deactivate)
- Phase 06 (Payments): client_id FK on billing_documents is live; payment recording can reference clients by ID
- Phase 07 (AR): client detail page panels (contracts, invoices) provide the data structure template for statement + aging views

---
*Phase: 05-client-registry-migration-foundation*
*Completed: 2026-06-19*
