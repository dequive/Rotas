---
phase: 06-payment-registration
plan: "04"
subsystem: frontend
tags: [payments, modal, next-js, api-routes, idempotency, design-system]
dependency_graph:
  requires:
    - "06-03"
  provides:
    - PaymentModal component
    - registerPayment / voidPayment / getClientStatement API functions
    - 4 Next.js API route handlers (payments proxy, void, apply, statement)
  affects:
    - apps/manager/app/cobranca/page.tsx
    - apps/manager/app/clientes/[id]/page.tsx
tech_stack:
  added: []
  patterns:
    - Next.js App Router server component + client component co-location
    - Cookie-based auth forwarding in Next.js route handlers
    - Idempotency-Key generated on modal open (not on submit)
    - String amounts throughout payment flow (no float precision loss)
key_files:
  created:
    - apps/manager/app/api/payments/route.ts
    - apps/manager/app/api/payments/[id]/void/route.ts
    - apps/manager/app/api/payments/[id]/apply/route.ts
    - apps/manager/app/api/clients/[id]/statement/route.ts
    - apps/manager/app/components/PaymentModal.tsx
  modified:
    - apps/manager/app/lib/billing-api.ts
    - apps/manager/app/cobranca/page.tsx
    - apps/manager/app/clientes/[id]/page.tsx
decisions:
  - "window.location.reload() as default onSuccess fallback — avoids useRouter requirement in Server Component callers"
  - "BillingDocumentSummary extended with clientId field — required to pass client_id to PaymentModal from /cobranca"
  - "amount sent as string (not number) — avoids IEEE 754 float precision loss on MZN values"
  - "UUID generated on handleOpen (not handleSubmit) — safe against double-click; new key on each open"
metrics:
  duration_minutes: 25
  tasks_completed: 4
  tasks_total: 4
  files_created: 5
  files_modified: 4
  completed_date: "2026-06-20"
---

# Phase 06 Plan 04: Payment Registration Frontend Summary

**One-liner:** Next.js API route proxies + PaymentModal client component with idempotent invoice-linked and advance payment flows integrated into /cobranca and /clientes/[id].

## What Was Built

### Task 1 — Next.js API Route Handlers (commit `157f384`)

Four route handlers created under `apps/manager/app/api/`:

| Route | Method | Backend target |
|---|---|---|
| `/api/payments` | POST | `/api/v1/billing/payments` (forwards `Idempotency-Key`) |
| `/api/payments/[id]/void` | POST | `/api/v1/billing/payments/{id}/void` |
| `/api/payments/[id]/apply` | POST | `/api/v1/billing/payments/{id}/apply` |
| `/api/clients/[id]/statement` | GET | `/api/v1/clients/{id}/statement` (forwards `period_start`/`period_end`) |

All routes read `rotas_access_token` and `rotas_tenant_id` from httpOnly cookies, matching the existing pattern in `apps/manager/app/api/clients/route.ts`.

### Task 2 — billing-api.ts additions (commit `7e72ea4`)

Three exported functions appended to `apps/manager/app/lib/billing-api.ts`:

- `registerPayment(payload, idempotencyKey)` — POSTs to `/api/payments`, sends `Idempotency-Key` header, amounts as strings
- `voidPayment(paymentId, voidReason)` — POSTs to `/api/payments/{id}/void`
- `getClientStatement(clientId, options?)` — GETs `/api/clients/{id}/statement` with optional period filters

New TypeScript interfaces: `ClientPaymentPayload`, `ClientPayment`, `PaymentAllocationSummary`, `ClientStatement`.

`BillingDocumentSummary` extended with `clientId: string | null` to enable PaymentModal integration from the cobranca page.

### Task 3 — PaymentModal Client Component (commit `c2c1a13`)

`apps/manager/app/components/PaymentModal.tsx` — `"use client"` component.

- UUID generated via `crypto.randomUUID()` on modal open (`handleOpen`), not on submit — safe against double-click without needing server round-trip
- Supports two modes: invoice-linked (`invoiceId` prop) and advance (`advanceMode={true}`)
- Modal title adapts: "Registar Adiantamento — {client}" / "Registar Pagamento — Fatura {number}" / "Registar Pagamento — {client}"
- Amount input: `font-mono` class (IBM Plex Mono per DESIGN.md), shows outstanding balance hint
- Client-side validation: rejects submit if amount > outstanding balance (invoice mode)
- Submit button: `bg-amber-500 hover:bg-amber-600` per DESIGN.md; shows "A registar..." while loading
- `onSuccess` callback or `window.location.reload()` fallback for Server Component callers
- Inline error display; modal stays open on error

### Task 4 — Page Integrations (commit `5b4c4da`)

**`/cobranca` page:** `PaymentModal` imported and rendered for each billing document with `status === "Emitido"` and a non-null `clientId`. Button: "Registar Pagamento" (amber-600, bordered).

**`/clientes/[id]` page:**
1. New "Acção" column in the invoices table — `PaymentModal` rendered for `status === "issued"` or `status === "overdue"` rows, pre-filled with `invoiceId`, `invoiceNumber`, `invoiceTotal`, `invoiceOutstanding`
2. "Registar Adiantamento" button added to the page header actions area (`advanceMode={true}`, amber-500 fill button)

## Decisions Made

| Decision | Rationale |
|---|---|
| `window.location.reload()` default fallback | Server Component pages cannot use `useRouter`; the simplest approach that works without wrapping in a Client Component |
| `clientId` added to `BillingDocumentSummary` | The `/cobranca` page renders billing documents from `BillingDocumentSummary` which didn't carry `client_id` — needed to pass to `PaymentModal` |
| Amounts as strings | `ClientPaymentPayload.amount: string` avoids IEEE 754 float rounding on MZN values; matches backend `Numeric(10,2)` expectation |
| UUID on `handleOpen` not `handleSubmit` | Generates a fresh idempotency key each time the modal is opened; prevents same-key reuse across separate payment attempts |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing field] Added `clientId` to BillingDocumentSummary**
- **Found during:** Task 4 integration into `/cobranca`
- **Issue:** The plan referenced `doc.client_id` in the cobranca page but `BillingDocumentSummary` had no such field — it only had `client` (display name string). The `ApiBillingDocument` type also lacked `client_id`.
- **Fix:** Added `client_id?: string | null` to `ApiBillingDocument`, `clientId: string | null` to `BillingDocumentSummary`, updated the map function and fallback data.
- **Files modified:** `apps/manager/app/lib/billing-api.ts`
- **Commit:** `7e72ea4`

## Build Verification

- `npx tsc --noEmit` — exit 0, no TypeScript errors
- `npm run build` — compiled successfully, types valid; build terminated at static export rename step due to pre-existing Windows/OneDrive filesystem ENOENT on `.next/export/500.html` (unrelated to this plan's changes — same error exists on prior commits)

## Known Stubs

None. All data flows are wired: PaymentModal calls `registerPayment()` which hits `/api/payments` which proxies to the FastAPI backend.

## Self-Check: PASSED

Files verified:
- `apps/manager/app/api/payments/route.ts` — FOUND
- `apps/manager/app/api/payments/[id]/void/route.ts` — FOUND
- `apps/manager/app/api/payments/[id]/apply/route.ts` — FOUND
- `apps/manager/app/api/clients/[id]/statement/route.ts` — FOUND
- `apps/manager/app/components/PaymentModal.tsx` — FOUND

Commits verified:
- `157f384` — FOUND
- `7e72ea4` — FOUND
- `c2c1a13` — FOUND
- `5b4c4da` — FOUND
