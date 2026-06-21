---
phase: 18-analytics-insurance
plan: "04"
subsystem: frontend
tags: [analytics, insurance, next-js, client-components, proxy-routes]
key_files:
  created:
    - apps/manager/app/analytics/ExportButtons.tsx
    - apps/manager/app/viaturas/[id]/InsuranceTab.tsx
    - apps/manager/app/api/analytics/fuel-report/route.ts
    - apps/manager/app/api/analytics/compliance-report/route.ts
    - apps/manager/app/api/vehicles/[id]/insurance/route.ts
  modified:
    - apps/manager/app/analytics/page.tsx
    - apps/manager/app/viaturas/[id]/page.tsx
    - apps/manager/app/lib/analytics-api.ts
metrics:
  completed_date: "2026-06-21"
  tasks_completed: 5
  tasks_total: 5
  typescript_errors: 0
---

# Phase 18 Plan 04: Analytics Frontend + Vehicle Insurance Tab — Summary

## One-liner

Analytics page extended with 4 new KPI sections and async export buttons; vehicle detail page gains a Seguros tab with full insurance policy CRUD.

## What Was Built

### ExportButtons.tsx (Client Component)

Polling-based export trigger — "Exportar Combustível" (XLSX) and "Exportar Conformidade" (PDF). Calls Next.js proxy routes, receives `job_id`, polls every 3 seconds, shows "A preparar..." spinner during processing, "Pronto" on completion.

### Analytics page.tsx (Server Component updates)

Added 4 new KPI sections below existing cards:
- **Route Profitability** table: Origem → Destino, Viagens, Custo Médio (font-mono MZN)
- **Contract Margins** table: Doc ID (truncated), Receita, Custo, Margem (all font-mono)
- **Delivery NPS** gauge: large percentage number, amber if >70, red if <50, label "NPS de Entrega"
- **Top 5 Drivers** list: driver_id (truncated), trips, km (font-mono)
- Empty states for all sections when arrays are empty

### InsuranceTab.tsx (Client Component)

Fetches `GET /api/v1/vehicles/{vehicleId}/insurance` directly with localStorage auth headers (rotas_access_token + rotas_tenant_id). Lists policies in a table: policy_number (IBM Plex Mono), insurer, coverage_type, premium_amount (IBM Plex Mono), valid_until, and status badge. Status dot badges: green (vigente >30d), amber (a_renovar ≤30d), red (expirado). Modal overlay form ("Registar Apólice"): policy_number, insurer, coverage_type (select), premium_amount, valid_from, valid_until, notes. POSTs to `POST /api/v1/vehicles/{vehicleId}/insurance` with auth headers; refetches list on success.

### Next.js proxy routes

- `GET /api/analytics/fuel-report?month=YYYY-MM` → forwards to backend
- `GET /api/analytics/compliance-report` → forwards to backend
- `GET/POST /api/vehicles/{id}/insurance` → forwards to backend vehicles insurance endpoints

### Vehicle detail page.tsx

Added "Seguros" tab in the tab row; renders `<InsuranceTab vehicleId={params.id} />` when active.

### analytics-api.ts extensions

New TypeScript interfaces: `RouteProfileItem`, `ContractMarginItem`, `TopDriverItem`, `AnalyticsDashboard`. New helper `fetchAnalyticsDashboard(periodStart, periodEnd)`.

## Verification

- TypeScript: `npx tsc --noEmit` exits 0 — no errors
- All key files present on disk
- Commits: `41f53aa feat(18-04): analytics dashboard`, `3b41359 feat(18-04): InsuranceTab`, `3ff84de feat(18-04): fix InsuranceTab — modal form + correct API path + auth headers`
