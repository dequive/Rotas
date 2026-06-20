---
phase: 13-frontend-completeness
plan: "03"
subsystem: billing-frontend
tags: [billing, server-action, next-app-router, client-component]
dependency_graph:
  requires: []
  provides: [FE-02]
  affects: [apps/manager/app/cobranca]
tech_stack:
  added: []
  patterns:
    - Server action with revalidatePath in Next.js App Router
    - Client component IssueDocumentButton with loading/error state
    - apiFetch POST call from server action
key_files:
  created:
    - apps/manager/app/cobranca/actions.ts
    - apps/manager/app/cobranca/IssueDocumentButton.tsx
  modified:
    - apps/manager/app/cobranca/page.tsx
decisions:
  - "IssueDocumentButton extracted as a separate Client Component file (not inline in Server Component) to avoid mixing 'use client' with Server Component module"
  - "Gerar Documento button disabled with tooltip — creating a new billing document requires contract/period selection (modal out of scope for this plan)"
  - "PDF export button tooltip updated to clarify async nature; no interactive wiring (export job polling is complex, deferred)"
  - "revalidatePath('/cobranca') called server-side in actions.ts; router.refresh() also called client-side to ensure instant UI update"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-20"
  tasks_completed: 2
  files_changed: 3
---

# Phase 13 Plan 03: /cobranca Action Wiring Summary

Wire the Emitir button on draft billing documents in `/cobranca` — calling `POST /billing/documents/{id}/issue` via a typed server action with client-side loading and error state.

## What Was Built

### Task 1 — actions.ts
`apps/manager/app/cobranca/actions.ts` — new file, `"use server"` directive.

- `issueBillingDocument(documentId: string)` — calls `apiFetch` with `POST /api/v1/billing/documents/{documentId}/issue`, body `{}`.
- Returns `{ ok: true }` on success (after `revalidatePath("/cobranca")`), or `{ ok: false; error: string }` on catch.
- Error message extracted from `Error.message` (which `apiFetch` already populates from the ROTAS error envelope).

### Task 2 — IssueDocumentButton.tsx + page.tsx
`apps/manager/app/cobranca/IssueDocumentButton.tsx` — new Client Component.

- Accepts `{ documentId: string }`.
- Calls `issueBillingDocument` on click, shows "A emitir..." during loading.
- On success: calls `router.refresh()` to re-render the page with updated document status.
- On error: displays inline error message below the button (`text-error`, max 160px, right-aligned).
- Button styled with amber-500 background (`#f59e0b`), dark ink text (`#0f1623`), per DESIGN.md primary button spec.

`apps/manager/app/cobranca/page.tsx` changes:
- Import added: `IssueDocumentButton` from `./IssueDocumentButton`.
- Documents section footer logic updated:
  - `status === "Emitido" && clientId` → PaymentModal (unchanged)
  - `status !== "Emitido"` → `<IssueDocumentButton documentId={document.id} />`
  - Both wrapped in `<div className="flex-shrink-0">` for layout consistency.
- "Gerar Fatura" button: renamed "Gerar Documento", set `disabled`, opacity 50, `cursor-not-allowed`, tooltip explains pre-condition.
- PDF export button: tooltip updated to "Exportar Relatório — a preparar download, disponível em breve", `aria-label` added for accessibility.

## Verification

TypeScript: `cd apps/manager && npx tsc --noEmit` — **exits 0, no errors.**

Files exist:
- `apps/manager/app/cobranca/actions.ts` — FOUND
- `apps/manager/app/cobranca/IssueDocumentButton.tsx` — FOUND

Commit: `07d2787 feat(13-03): wire Emitir button and issueBillingDocument server action on /cobranca`

## Deviations from Plan

None — plan executed exactly as written. The plan suggested adding both `revalidatePath` (server-side) and `router.refresh()` (client-side); both were applied for belt-and-suspenders cache invalidation.

## Known Stubs

- PDF export button: renders with informative tooltip but no functional onClick. Export job polling is deferred (architectural complexity). This does not prevent the plan's goal (FE-02 = issue billing documents from /cobranca).
- "Gerar Documento" button: disabled, no modal. Creating a new billing document from scratch requires contract + period selection (modal), which is out of scope.

Neither stub prevents FE-02 from being achieved — the critical Emitir → issue flow is fully wired.

## Self-Check: PASSED

- `apps/manager/app/cobranca/actions.ts` — FOUND
- `apps/manager/app/cobranca/IssueDocumentButton.tsx` — FOUND
- `apps/manager/app/cobranca/page.tsx` — FOUND (modified)
- Commit `07d2787` — exists in git log
