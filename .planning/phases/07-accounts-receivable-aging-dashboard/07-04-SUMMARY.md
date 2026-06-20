---
phase: 07-accounts-receivable-aging-dashboard
plan: "04"
subsystem: frontend
tags: [ar, client-statement, pdf-download, next-js-api-route]
dependency_graph:
  requires: [07-01]
  provides: [client-statement-ui, pdf-proxy-route]
  affects: [clientes-detail-page]
tech_stack:
  added: []
  patterns: [next-js-api-route-proxy, server-component-data-fetch, httponly-cookie-auth-forward]
key_files:
  created:
    - apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts
  modified:
    - apps/manager/app/clientes/[id]/page.tsx
decisions:
  - "Used SectionHeader actions prop for PDF button — avoids nesting a second flex container"
  - "Cookie name confirmed as rotas_access_token from auth.ts (not rotas_session)"
  - "StatusBadge used without labels override — falls back gracefully for unknown status keys"
  - "MonoCell used with children pattern (not value prop) as confirmed from component source"
metrics:
  duration: "~20min"
  completed: "2026-06-20"
  tasks_completed: 2
  files_changed: 2
---

# Phase 07 Plan 04: Client Detail — Extrato Conta Corrente + PDF Download Summary

**One-liner:** Extended /clientes/[id] with per-document AR statement table (amount_paid + outstanding columns) and a streaming PDF download proxy that injects auth cookies.

## Tasks Completed

| Task | Name | Files |
|------|------|-------|
| 1 | Create PDF proxy Next.js route | apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts |
| 2 | Add statement section to /clientes/[id]/page.tsx | apps/manager/app/clientes/[id]/page.tsx |

## What Was Built

### Task 1 — PDF Proxy Route
`apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts`

Next.js API route that:
- Reads `rotas_access_token` and `rotas_tenant_id` HttpOnly cookies (exact names from auth.ts)
- Forwards `Authorization: Bearer <token>` and `X-Tenant-Id: <tenant>` headers to the backend
- Calls `GET /api/v1/billing/clients/{id}/statement/pdf` (with optional `as_of` passthrough)
- Returns PDF bytes with `Content-Type: application/pdf` and `Content-Disposition: attachment; filename="extrato_{id}.pdf"`
- Returns 401 if unauthenticated, 503 if backend is unreachable

### Task 2 — Extrato Conta Corrente Section

Added to `apps/manager/app/clientes/[id]/page.tsx`:

1. **New TypeScript interfaces:** `StatementDoc` and `ClientStatement` (with `amount_paid`, `outstanding` per document)

2. **Statement fetch:** `apiFetch<ClientStatement>('/api/v1/billing/clients/${id}/statement')` — silent catch, renders nothing if backend returns error

3. **Balance summary bar:** IBM Plex Mono `text-2xl font-semibold`, `var(--error)` red when balance > 0, `var(--success)` green when 0. Shows total_invoiced and total_paid inline.

4. **7-column statement table:**
   - Fatura (invoice_number in MonoCell)
   - Emissão (issued_at)
   - Vencimento (due_date — red + bold if overdue)
   - Total MZN (total_amount in MonoCell)
   - Pago MZN (amount_paid in MonoCell)
   - Em Aberto MZN (outstanding in MonoCell — red if > 0, green if 0)
   - Estado (StatusBadge — falls back gracefully for overdue/paid/cancelled)

5. **Exportar PDF button:** `<a href="/api/billing/clients/${id}/statement/pdf" download="extrato_{id}.pdf">` using amber brand color `var(--amber)` — placed in SectionHeader's `actions` prop

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MonoCell takes children, not value prop**
- **Found during:** Task 2 implementation
- **Issue:** Plan template showed `<MonoCell value={...} />` but MonoCell component only accepts `children: React.ReactNode`
- **Fix:** Changed all MonoCell usages to `<MonoCell>{...}</MonoCell>` children pattern
- **Files modified:** apps/manager/app/clientes/[id]/page.tsx

**2. [Rule 1 - Bug] StatusBadge takes single label override, not labels map**
- **Found during:** Task 2 implementation
- **Issue:** Plan template showed `<StatusBadge labels={{issued: "Emitido", ...}} />` but component only accepts `label?: string`
- **Fix:** Removed labels prop — StatusBadge already has Portuguese labels for `issued` ("Emitida"), `draft` ("Rascunho") in its config; unknown keys (overdue, paid, cancelled) fall back to the raw status string
- **Files modified:** apps/manager/app/clientes/[id]/page.tsx

**3. [Rule 1 - Bug] SectionHeader wrapper div conflict**
- **Found during:** Task 2 implementation
- **Issue:** Plan template wrapped SectionHeader in another `flex items-center justify-between` div, creating a double flex container since SectionHeader already has that layout with `actions` slot
- **Fix:** Used SectionHeader's built-in `actions` prop to place the Exportar PDF button
- **Files modified:** apps/manager/app/clientes/[id]/page.tsx

## TypeScript

`npx tsc --noEmit -p apps/manager/tsconfig.json` — zero errors after all changes.

## Known Stubs

None — all data flows from the backend statement endpoint. If the statement endpoint returns an error, the section is hidden (not a stub — intentional graceful degradation).

## Self-Check: PASSED

- [x] `apps/manager/app/api/billing/clients/[id]/statement/pdf/route.ts` — created and confirmed readable
- [x] `apps/manager/app/clientes/[id]/page.tsx` — contains "Extrato Conta Corrente" (3 occurrences confirmed)
- [x] TypeScript: clean compilation (no output = no errors)
- [x] `amount_paid` present in statement table
- [x] `outstanding` present in statement table
- [x] `download` attribute on Exportar PDF anchor
- [x] `Content-Disposition: attachment` in PDF proxy route
- [x] Cookie name `rotas_access_token` matches auth.ts line 59
