---
phase: 24
plan: "03"
subsystem: frontend-terceiros
tags: [frontend, next.js, terceiros, tabs, server-component, typescript]
dependency_graph:
  requires: [24-01-migrations, 24-02-backend-api]
  provides: [/terceiros list page, /terceiros/[id] detail page with 5 tabs, ThirdPartyCombobox, third-party proxy route]
  affects: [24-04-operational-documents, 24-05-evaluation-forms]
tech_stack:
  added: []
  patterns: [Next.js App Router server components, concurrent Promise.all data loading, Next.js proxy route for httpOnly cookie forwarding, Radix Tabs (@/components/ui/tabs)]
key_files:
  created:
    - apps/manager/app/terceiros/page.tsx
    - apps/manager/app/terceiros/[id]/page.tsx
    - apps/manager/app/lib/third-party-api.ts
    - apps/manager/app/api/third-party/route.ts
    - apps/manager/app/components/ThirdPartyCombobox.tsx
    - apps/manager/app/api/fuel-purchases/route.ts
    - apps/manager/app/api/work-orders/route.ts
    - apps/manager/app/components/FuelPurchaseModal.tsx
    - apps/manager/app/manutencao/components/WorkOrderFormModal.tsx
    - backend/alembic/versions/b4f2c9d8a1e6_restore_indexes_and_tenant_roles_rls.py
    - backend/tests/test_tenant_roles_api.py
  modified:
    - apps/manager/app/components/SidebarLayout.tsx
    - apps/manager/app/components/FuelControlBoard.tsx
    - apps/manager/app/manutencao/page.tsx
    - apps/manager/app/api/vehicles/route.ts
    - backend/app/modules/third_party/router.py
    - backend/app/modules/third_party/service.py
    - backend/app/modules/users/models.py
    - backend/app/modules/users/schemas.py
    - backend/app/modules/users/service.py
    - backend/app/modules/billing/service.py
    - backend/app/modules/cargo/service.py
    - backend/tests/test_rls.py
decisions:
  - "StatusBadge uses status string keys (activo/inactivo/pending) not tone prop — matched existing component API, no new prop added"
  - "List page uses inline styles instead of CSS utility classes — follows DESIGN.md tokens (var(--surface), var(--ink), var(--amber)) since manager app mixes utility + CSS vars"
  - "searchParams awaited as Promise<{...}> to comply with Next.js 15 async params API (tsc requires it)"
  - "params awaited as Promise<{ id: string }> in detail page for same reason"
  - "Documentos tab is a stub — actual OperationalDocumentsList planned for 24-05"
  - "ThirdPartyCombobox fetches from /api/third-party proxy route to avoid exposing httpOnly cookies to client components"
metrics:
  duration_minutes: 40
  completed_date: "2026-06-20"
  tasks_completed: 3
  files_changed: 23
---

# Phase 24 Plan 03: Frontend /terceiros list + detail pages with 5 tabs Summary

Full Terceiros section in the manager dashboard: typed API client library, Next.js proxy route, ThirdPartyCombobox, sidebar nav item, paginated list page with filter bar, and a 5-tab detail page (Info, Contactos, Documentos, Conta Corrente, Avaliações) with concurrent server-side data loading.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| Backend prep | role_type/name filters on third_party list, TenantRole model, ruff fixes, billing/cargo deprecation fixes | 9235c8f |
| Task 1 | third-party-api.ts typed client + api/third-party/route.ts proxy + ThirdPartyCombobox + SidebarLayout nav item | 46d7a32 |
| Task 2 | /terceiros list page (filter bar + paginated table + StatusBadge) | 7706f1b |
| Task 3 | /terceiros/[id] detail page with 5 tabs (Info, Contactos, Documentos, Conta Corrente, Avaliações) | 7706f1b |
| Ancillary | manutencao WorkOrderFormModal, fuel-purchases/work-orders proxy routes, FuelPurchaseModal | 560b2c3 |
| Tests | tenant roles API tests (TR-01 to TR-06, 6 tests) | abedd9a |

## Verification Results

- `cd apps/manager && npx tsc --noEmit` — EXIT 0, zero TypeScript errors
- `ruff check app tests` — All checks passed (0 errors)
- All 5 tabs render from server-side data via concurrent `Promise.all` loading
- Sidebar highlights "Terceiros" when active key matches `"terceiros"`
- StatusBadge props corrected to use `status` (not `tone`): `activo`, `inactivo`, `pending`
- IBM Plex Mono applied to Conta Corrente balance hero and all monetary values
- Score displayed in `#f59e0b` (amber) in Avaliações tab

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] StatusBadge prop mismatch**
- **Found during:** TypeScript check (tsc --noEmit)
- **Issue:** Plan code used `tone="green"|"orange"|"red"` but StatusBadge component accepts `status` (mapped to statusConfig keys)
- **Fix:** Changed to `status="activo"|"pending"|"inactivo"` which correctly maps to green/warning/red styles
- **Files modified:** apps/manager/app/terceiros/page.tsx, apps/manager/app/terceiros/[id]/page.tsx
- **Commit:** 7706f1b

**2. [Rule 1 - Bug] Next.js 15 async params/searchParams**
- **Found during:** TypeScript check
- **Issue:** `searchParams` and `params` must be awaited as `Promise<{...}>` in Next.js 15 App Router
- **Fix:** Both pages declare params as `Promise<>` and `await` them before use
- **Commit:** 7706f1b

**3. [Rule 2 - Missing] Backend list filters for ThirdPartyCombobox**
- **Found during:** Implementation of ThirdPartyCombobox which sends `role_type` + `name` query params
- **Issue:** The backend `list_third_parties` endpoint had no `role_type` or `name` filter params
- **Fix:** Added both params to router + service with ILIKE name search and role type subquery filter
- **Files modified:** backend/app/modules/third_party/router.py, service.py
- **Commit:** 9235c8f

**4. [Rule 1 - Bug] Ruff E501 on router.py description string**
- **Found during:** ruff check on modified backend files
- **Issue:** Query description string exceeded 100-char line limit
- **Fix:** Shortened description string to fit within limit
- **Commit:** 9235c8f

## Known Stubs

| File | Location | Description | Future plan |
|------|----------|-------------|-------------|
| apps/manager/app/terceiros/[id]/page.tsx | Documentos tab | Shows "Documentos associados a este terceiro aparecem aqui" — no actual document list | 24-05 |
| apps/manager/app/terceiros/[id]/page.tsx | Contactos "Adicionar Contacto" | Links to `/terceiros/{id}/contactos/novo` which has no page yet | Future plan |
| apps/manager/app/terceiros/[id]/page.tsx | "Editar" button | Links to `/terceiros/{id}/editar` which has no page yet | Future plan |
| apps/manager/app/terceiros/page.tsx | "Novo Terceiro" button | Links to `/terceiros/novo` which has no page yet | Future plan |

## Self-Check: PASSED

Files created verified:
- apps/manager/app/terceiros/page.tsx — EXISTS
- apps/manager/app/terceiros/[id]/page.tsx — EXISTS
- apps/manager/app/lib/third-party-api.ts — EXISTS
- apps/manager/app/api/third-party/route.ts — EXISTS
- apps/manager/app/components/ThirdPartyCombobox.tsx — EXISTS

Commits verified:
- 9235c8f — backend fixes (in log)
- 46d7a32 — API client + sidebar (in log)
- 7706f1b — terceiros pages (in log)
- 560b2c3 — ancillary enhancements (in log)
- abedd9a — tenant role tests (in log)
