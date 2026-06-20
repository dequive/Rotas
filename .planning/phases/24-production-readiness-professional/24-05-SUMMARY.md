---
phase: 24
plan: "05"
subsystem: frontend-terceiros
tags: [frontend, third-party, operational-documents, driver-vehicle-assignments, nextjs]
dependency_graph:
  requires: [24-01, 24-02, 24-03, 24-04]
  provides: [operational-documents-ui, vehicle-detail-page, driver-detail-page]
  affects: [motoristas, viaturas, terceiros]
tech_stack:
  added: []
  patterns:
    - OperationalDocumentsList reusable table component with expiry color coding
    - DocumentUploadModal form modal posting via Next.js API proxy route
    - Server Component data fetching pattern (parallel Promise.all with .catch fallbacks)
key_files:
  created:
    - apps/manager/app/components/OperationalDocumentsList.tsx
    - apps/manager/app/components/DocumentUploadModal.tsx
    - apps/manager/app/api/operational-documents/route.ts
    - apps/manager/app/viaturas/[id]/page.tsx
    - apps/manager/app/motoristas/[id]/page.tsx
  modified:
    - apps/manager/app/lib/third-party-api.ts
    - apps/manager/app/terceiros/[id]/page.tsx
decisions:
  - DocumentUploadModal posts to /api/operational-documents Next.js proxy (same pattern as /api/third-party from Plan 24-04) — client components cannot read httpOnly session cookies
  - OperationalDocumentsList receives pre-fetched docs array — keeps component pure/reusable across terceiros, vehicle, driver detail pages
  - Vehicle and driver detail pages use apiFetch directly (server components) — no proxy needed
  - driver-vehicle-assignments endpoint queried with vehicle_id or driver_id filter — reuses existing Phase 23 endpoint
metrics:
  duration_minutes: 25
  completed_date: "2026-06-20"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 2
---

# Phase 24 Plan 05: Operational Documents UI + Assignments Summary

**One-liner:** Reusable OperationalDocumentsList/DocumentUploadModal components wired into /terceiros/[id] Documentos tab, new /viaturas/[id] page with Motoristas Atribuidos section, and new /motoristas/[id] page with Viaturas Atribuidas section.

---

## What Was Built

### TP2-11: OperationalDocumentsList + DocumentUploadModal + Documentos Tab

**`OperationalDocumentsList`** (`apps/manager/app/components/OperationalDocumentsList.tsx`):
- Table of operational documents with columns: Tipo, Numero, Emissao, Validade, Entidade, Estado
- Expiry date color coding: red for expired (days < 0), amber for expiring within 30 days
- Verification status badge with colored dot: pending (amber), verified (green), rejected (red)
- All DESIGN.md conventions: Manrope body, IBM Plex Mono for data values, amber accent

**`DocumentUploadModal`** (`apps/manager/app/components/DocumentUploadModal.tsx`):
- Toggle button (closed state) / overlay modal (open state) — no external modal library
- Form fields: document_type (select from 9 types), document_number, issuing_authority, issued_at, expiry_date, notes
- POSTs to `/api/operational-documents` (Next.js proxy route) with subjectType + subjectId
- Inline error display, loading state, auto-reset on success

**`/api/operational-documents/route.ts`** (`apps/manager/app/api/operational-documents/route.ts`):
- Next.js App Router POST handler
- Reads session via `requireSession()`, forwards to `POST /api/v1/third-party/documents` with auth headers

**`/terceiros/[id]/page.tsx`** (modified):
- Added `loadOperationalDocuments("third_party", id)` to parallel fetch
- Documentos tab renders OperationalDocumentsList + DocumentUploadModal
- Tab shows count badge when documents exist

### TP2-12: Vehicle Detail Page + Driver Detail Page with Assignments

**`/viaturas/[id]/page.tsx`** (`apps/manager/app/viaturas/[id]/page.tsx`):
- New Server Component page for vehicle detail
- Header: plate (IBM Plex Mono 26px), brand/model/year subtitle, StatusBadge, "Ver Historico" link
- **Motoristas Atribuidos** section: table from `GET /api/v1/third-party/driver-vehicle-assignments?vehicle_id={id}`
  - Columns: Motorista (ID), Tipo, Atribuido em, Encerrado em, Estado
  - StatusBadge for active (activo) vs closed (inactivo) assignments
  - "Atribuir Motorista" link to `/viaturas/{id}/atribuir`
- **Documentos Operacionais** section: reuses OperationalDocumentsList + DocumentUploadModal(subjectType="vehicle")

**`/motoristas/[id]/page.tsx`** (`apps/manager/app/motoristas/[id]/page.tsx`):
- New Server Component page for driver detail
- Header: full_name, phone/email subtitle, StatusBadge, score display
- **Identidade e Documentos** panel: 3-column grid showing license, passport, BI with expiry color coding
- **Viaturas Atribuidas** section: table from `GET /api/v1/third-party/driver-vehicle-assignments?driver_id={id}`
  - Columns: Viatura (ID) as amber link to /viaturas/[id], Tipo, Atribuido em, Encerrado em, Estado
  - "Atribuir Viatura" link to `/motoristas/{id}/atribuir`
- **Documentos Operacionais** section: reuses OperationalDocumentsList + DocumentUploadModal(subjectType="driver")

---

## Commits

| Hash | Message |
|------|---------|
| 47f43aa | feat(24-05): TP2-11 OperationalDocumentsList, DocumentUploadModal, API route |
| 165f3f3 | feat(24-05): TP2-11 wire Documentos tab in /terceiros/[id] |
| a12ee1e | feat(24-05): TP2-12 vehicle and driver detail pages with assignments |

---

## Deviations from Plan

### Auto-added Missing Functionality

**1. [Rule 2 - Missing] Driver detail page `/motoristas/[id]`**
- **Found during:** TP2-12 execution
- **Issue:** Plan specified "Viaturas Atribuidas section in driver detail page" but `/motoristas/[id]/page.tsx` did not exist
- **Fix:** Created full driver detail page with Identity panel + Viaturas Atribuidas table + Documentos Operacionais section
- **Files modified:** `apps/manager/app/motoristas/[id]/page.tsx` (created)

**2. [Rule 2 - Missing] Driver detail page also shows expiry-colored document fields**
- **Found during:** TP2-12 implementation
- **Issue:** Driver's license/passport/BI validity dates are shown in the identity panel; applying the same color logic (red = expired, amber = expiring) improves compliance visibility
- **Fix:** Added inline `expiryColor()` function returning red/amber/default styles based on days-until-expiry

---

## Known Stubs

None. All data is fetched from live backend endpoints (Phase 23 API). No hardcoded placeholders.

- `/viaturas/[id]/atribuir` and `/motoristas/[id]/atribuir` are stub links (no target page yet) — these are out-of-scope for Plan 24-05 and will be addressed in Plan 24-06 or a future plan.

---

## TypeScript

`npx tsc --noEmit` — 0 errors after all files committed.

---

## Self-Check: PASSED

- `apps/manager/app/components/OperationalDocumentsList.tsx` — FOUND
- `apps/manager/app/components/DocumentUploadModal.tsx` — FOUND
- `apps/manager/app/api/operational-documents/route.ts` — FOUND
- `apps/manager/app/viaturas/[id]/page.tsx` — FOUND
- `apps/manager/app/motoristas/[id]/page.tsx` — FOUND
- Commit `47f43aa` — FOUND
- Commit `165f3f3` — FOUND
- Commit `a12ee1e` — FOUND
