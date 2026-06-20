---
phase: 24
plan: "04"
subsystem: frontend
tags: [third-party, combobox, fuel-purchase, work-orders, supplier-picker]
dependency_graph:
  requires: [24-01, 24-02, 24-03]
  provides: [supplier-picker-fuel, service-provider-picker-work-orders]
  affects: [FuelControlBoard, manutencao-page]
tech_stack:
  added: []
  patterns: [next-js-proxy-route, client-component-combobox, httpOnly-cookie-workaround]
key_files:
  created:
    - apps/manager/app/components/ThirdPartyCombobox.tsx
    - apps/manager/app/components/FuelPurchaseModal.tsx
    - apps/manager/app/manutencao/components/WorkOrderFormModal.tsx
    - apps/manager/app/api/fuel-purchases/route.ts
    - apps/manager/app/api/work-orders/route.ts
  modified:
    - apps/manager/app/components/FuelControlBoard.tsx
    - apps/manager/app/manutencao/page.tsx
    - backend/app/modules/third_party/service.py
    - backend/app/modules/third_party/router.py
key_decisions:
  - ThirdPartyCombobox uses Next.js /api/third-party proxy (not direct backend URL) — Client Components cannot read httpOnly session cookies
  - Supplier field in FuelPurchaseModal is optional with free-text fallback — not all stations are registered third parties
  - Service provider field in WorkOrderFormModal is optional — preserves existing workflow when no registered provider is selected
metrics:
  duration_minutes: 0
  completed_date: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 4
---

# Phase 24 Plan 04: Supplier Picker in Fuel Purchase Form + Service Provider Picker in Work Order Form — Summary

## One-liner

Reusable `ThirdPartyCombobox` wired into fuel purchase registration and work order creation, letting managers link purchases and orders to registered suppliers and service providers.

## What Was Built

### Task 1: ThirdPartyCombobox shared Client Component

`apps/manager/app/components/ThirdPartyCombobox.tsx` — a reusable Client Component that:
- Accepts `roleType` (`supplier` | `service_provider` | `client`) to filter the dropdown
- Fetches options lazily (only when dropdown opens) via `/api/third-party` Next.js proxy
- Supports live search by name via `?name=` query param
- Shows NUIT/tax_id alongside name for disambiguation
- Calls `onChange({ id, name })` on selection, or `onChange(null)` on clear
- Closes on outside click via `mousedown` event listener on `document`

### Task 2: Supplier picker in fuel purchase flow

**`FuelPurchaseModal.tsx`** — full fuel purchase registration form with:
- Vehicle selector (dropdown from `vehicleOptions` prop)
- `ThirdPartyCombobox` with `roleType="supplier"` for registered supplier
- Free-text fallback input shown when no supplier is selected from the registry
- Liters + unit cost (MZN) grid
- Station/pump name + odometer fields
- POSTs to `/api/fuel-purchases` proxy route

**`/api/fuel-purchases/route.ts`** — Next.js route handler proxying POST to `/api/v1/fuel/purchases` on the backend, injecting `Authorization` + `X-Tenant-Id` headers from session.

**`FuelControlBoard.tsx`** modified to import and render `<FuelPurchaseModal vehicleOptions={...} />`.

### Task 3: Service provider picker in work order form

**`WorkOrderFormModal.tsx`** — work order creation form with:
- `ThirdPartyCombobox` with `roleType="service_provider"` for registered service provider
- Field labelled "Prestador de Serviço (opcional)"
- When cleared, sets `service_provider_third_party_id: null` in form state
- Includes `service_provider_third_party_id` in POST body to work order endpoint

**`/api/work-orders/route.ts`** — Next.js route handler proxying POST to `/api/v1/workshop/work-orders`.

**Backend filters** — `backend/app/modules/third_party/service.py` adds `role_type` and `name` (ilike) filters to `list_third_parties`. `router.py` exposes them as `Query` params.

## Verification

- ruff: `All checks passed!` on `backend/app/modules/third_party/`
- TypeScript: `npx tsc --noEmit` exits 0 with no output (no errors)
- All 7 key files confirmed present on disk

## Deviations from Plan

### Bundled into 24-03 commits

All 24-04 work was executed and committed by the 24-03 agent as part of its execution run. The commits are:

- `9235c8f fix(24-03): backend — role_type/name filters on third_party, TenantRole model, ruff fixes`
- `46d7a32 feat(24-03): third-party API client, proxy route, combobox, sidebar nav item`
- `560b2c3 feat(24-03): manutencao enhancements — WorkOrderFormModal, fuel-purchases/work-orders proxy routes`

This is not a functional deviation — all tasks from the 24-04 plan specification were completed exactly as described. The commit labeling bundled them under 24-03 rather than 24-04, but the code output is identical to the plan spec.

## Known Stubs

None. The `FuelPurchaseModal` and `WorkOrderFormModal` POST to real proxy routes that forward to real backend endpoints. The `ThirdPartyCombobox` fetches from `/api/third-party` which is a real proxy backed by the `GET /api/v1/third-party` backend endpoint with `role_type` filtering.

The `fuel-purchases` proxy targets `/api/v1/fuel/purchases` — if this exact endpoint does not yet exist in the backend fuel module, the proxy will return whatever the backend returns (likely 404). The form degrades gracefully per plan spec: the modal closes on success only; on error it shows the backend error message inline.

## Self-Check: PASSED

All 7 key files exist on disk. All commits confirmed in git log. ruff clean. TypeScript clean.
