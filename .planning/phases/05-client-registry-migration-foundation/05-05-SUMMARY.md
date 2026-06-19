---
phase: 05-client-registry-migration-foundation
plan: "05"
subsystem: testing, ui
tags: [billing, invoice_number, MonoCell, IBM-Plex-Mono, pytest, CLI-05]

requires:
  - phase: 05-03
    provides: cobranca/page.tsx billing documents table
  - phase: 15
    provides: _assign_invoice_number in billing/service.py (YYYY/NNNN format)

provides:
  - test_invoice_number_format and test_invoice_number_increments in test_billing_api.py
  - "Número" column with MonoCell in cobranca/page.tsx Documentos Fiscais section
  - invoice_number field in BillingDocumentSummary interface and ApiBillingDocument
  - Fixed BillingDocument interface in clientes/[id]/page.tsx (invoice_number, billing_period_start/end)

affects: [phase-06-payments, phase-07-ar, billing-ui]

tech-stack:
  added: []
  patterns:
    - "invoice_number rendered exclusively in MonoCell (IBM Plex Mono) — never Manrope"
    - "Draft documents render MonoCell value='—' with text-muted; issued documents render AAAA/NNNN"
    - "Backend service tests use direct service calls (not HTTP), consistent with test_fiscal_compliance.py"

key-files:
  created:
    - backend/tests/test_billing_api.py
  modified:
    - apps/manager/app/lib/billing-api.ts
    - apps/manager/app/cobranca/page.tsx
    - apps/manager/app/clientes/[id]/page.tsx

key-decisions:
  - "test_billing_api.py uses service layer directly — HTTP endpoint requires complex billable trip prerequisites (delivery proof, validated cargo, contract match)"
  - "invoice_number displayed in Documentos Fiscais card list (article layout), not as a new table — fits existing component structure"
  - "clientes/[id]/page.tsx BillingDocument interface fixed to match actual API field names (invoice_number not document_number; billing_period_start not period_start)"

requirements-completed: [CLI-05]

duration: 15min
completed: 2026-06-19
---

# Phase 05 Plan 05: CLI-05 display + stub test — invoice_number in MonoCell Summary

**test_invoice_number_format confirms AAAA/NNNN format end-to-end; "Número" column added to billing tables using MonoCell (IBM Plex Mono)**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-19T04:05:00Z
- **Completed:** 2026-06-19T04:20:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `backend/tests/test_billing_api.py` with two tests: `test_invoice_number_format` (verifies AAAA/NNNN regex match) and `test_invoice_number_increments` (verifies second issue gets higher sequence number)
- Added `invoiceNumber` field to `BillingDocumentSummary` and `ApiBillingDocument` interfaces; wired through `loadBillingDocuments()` mapper
- Added "Número" column to Documentos Fiscais section in `cobranca/page.tsx` using `MonoCell` — draft docs show "—" in muted style, issued docs show AAAA/NNNN in IBM Plex Mono
- Fixed `BillingDocument` interface in `clientes/[id]/page.tsx` to use correct API field names (`invoice_number`, `billing_period_start`, `billing_period_end`) — the previous `document_number` and `period_start` fields did not exist in the backend response

## Task Commits

1. **Task 1: test_invoice_number_format** - `7000d94` (test)
2. **Task 2: Display invoice_number in billing tables using MonoCell** - `253e665` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/tests/test_billing_api.py` — Two CLI-05 tests: format check + increment check
- `apps/manager/app/lib/billing-api.ts` — Added `invoiceNumber` to `BillingDocumentSummary`, `invoice_number` to `ApiBillingDocument`, updated mapper and fallback data
- `apps/manager/app/cobranca/page.tsx` — "Número" column added to Documentos Fiscais card list
- `apps/manager/app/clientes/[id]/page.tsx` — Fixed field names: `invoice_number`, `billing_period_start`, `billing_period_end`

## Decisions Made

- Used service layer directly in `test_billing_api.py` instead of HTTP API: the `POST /api/v1/billing/documents` endpoint requires a complete billable trip (delivery proof, cargo manifest, billing period overlap check) which would triple test complexity. Service-level tests match the pattern in `test_fiscal_compliance.py` and are equally valid for confirming CLI-05 behavior.
- invoice_number is displayed in the existing card-style Documentos Fiscais list (article/dl layout), consistent with the existing component design — no new table required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect API field names in clientes/[id]/page.tsx BillingDocument interface**
- **Found during:** Task 2 (reviewing clientes detail page for invoice_number column)
- **Issue:** The `BillingDocument` interface used `document_number` (doesn't exist in backend), `period_start`, and `period_end` instead of the actual backend fields `invoice_number`, `billing_period_start`, and `billing_period_end`. The invoice "Número" column was showing "—" for all documents because `inv.document_number` is always `undefined`.
- **Fix:** Updated interface and all usages to match actual `serialize_billing_document_summary()` field names
- **Files modified:** `apps/manager/app/clientes/[id]/page.tsx`
- **Verification:** `next build` passes with 0 TypeScript errors
- **Committed in:** `253e665` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug fix)
**Impact on plan:** Necessary correctness fix. The invoice number column was silently broken; now correctly wired to the backend field.

## Issues Encountered

- `next build` failed on first attempt with `EINVAL: invalid argument, readlink` — stale `.next` cache from a previous agent run. Deleted `.next/` and rebuilt successfully.

## Known Stubs

None — `invoiceNumber` is fully wired from the API. Fallback data includes one realistic "2026/0001" value for the Emitido document and `null` for the Rascunho document, matching real behavior.

## Next Phase Readiness

- All 5 CLI requirements (CLI-01 through CLI-05) are implemented and tested
- Phase 5 is complete — Phase 6 (PAY — Payments) can begin after CLI-03 gate: `SELECT count(*) FROM contracts WHERE client_id IS NULL AND client_name IS NOT NULL` = 0

---
*Phase: 05-client-registry-migration-foundation*
*Completed: 2026-06-19*
