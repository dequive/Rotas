# Quick Task 260620-vlw — Summary

**Task:** Design system migration wave 1  
**Date:** 2026-06-20 / 2026-06-21  
**Commits:** 04411ed → e33adc6 (6 task commits)  
**Status:** Complete

## What was implemented

### Task 1 — Quick-win sweep
- **IssueDocumentButton.tsx**: removed `style={{ backgroundColor: "#d97706" | "#f59e0b" }}` inline hex; replaced raw `<button>` with `<Button>` component
- **`.secondary-btn` → `<Button variant="secondary">`** in 9 files: ClientFormModal, ContractFormModal, DriverFormModal, KnownRouteFormModal, TripFormModal, PairingCodeButton, security/page, forgot-password/page, verify-email/page (Links got inline token classes)
- **Raw `.badge` → `<StatusBadge>`** in 3 files: viagens/page (trip + billing status), MaintenanceImminentPanel (3 badge instances), rotas-config/page (cyan → info, red → alerta/error)

### Task 2 — Input component + off-token migration
- Created `apps/manager/app/components/ui/Input.tsx` — forwardRef component with `default` and `mono` variants; consistent focus ring `focus:ring-2 focus:ring-amber/20 focus:border-amber`
- **PaymentModal.tsx**: full token migration — `bg-white`→`bg-surface`, `border-gray-200`→`border-border`, `text-gray-*`→`text-ink`/`text-ink-2`/`text-placeholder`, cancel button → `<Button variant="secondary">`, all inputs → `<Input>`
- **FleetComplianceBoard.tsx** filter inputs: `bg-white` → `bg-surface`
- **ar/page.tsx** filter input: inline var() → Tailwind token classes

### Task 3 — IconButton component + .icon-btn migration
- Created `apps/manager/app/components/ui/IconButton.tsx` — square icon-only button with `default` and `danger` variants, sizes `sm`/`md`
- Migrated 14+ `.icon-btn` instances across: ContractFormModal, DriverFormModal, VehicleFormModal, KnownRouteFormModal, KnownRouteDeleteButton, TripFormModal, PairingCodeButton, ClientsTable, ClientFormModal, viaturas/page
- `isEdit ? "icon-btn" : "primary-btn"` ternary pattern converted to `isEdit ? <IconButton> : <Button>` in 4 modal trigger components

### Task 4 — PaymentModal token migration
Already completed as part of Task 2 (modal was the primary target of Input migration).

### Task 5 — PageHeader in missing pages
Added `<PageHeader>` to 5 app pages (auth pages correctly excluded):
- `viagens/page.tsx` — title="Viagens" eyebrow="Operações"
- `motoristas/page.tsx` — title="Motoristas" eyebrow="Frota"
- `terceiros/page.tsx` — title="Terceiros" eyebrow="Frota"
- `analytics/page.tsx` — title="Analytics" eyebrow="Financeiro"
- `viaturas/page.tsx` — title="Viaturas" eyebrow="Frota"
- `contratos/page.tsx` — committed with Task 6

### Task 6 — Mop-up
- `rotas-config/page.tsx` lines 78, 87: `{money(tier.amount)}` wrapped with `<span className="font-mono tabular-nums">`
- `contratos/page.tsx` line 74: `<td className="font-mono tabular-nums">` on price column
- `clientes/ClientsTable.tsx`: `focus:ring-amber-500/20 focus:border-amber-500` → `focus:ring-amber/20 focus:border-amber` (token-based, removed inline style)

## Components created

| Component | Path | Variants |
|-----------|------|---------|
| `Input` | `apps/manager/app/components/ui/Input.tsx` | `default`, `mono` |
| `IconButton` | `apps/manager/app/components/ui/IconButton.tsx` | `default`, `danger` |

## Verification

- TypeScript: `npx tsc --noEmit` → 0 errors
- Zero `.secondary-btn` in TSX
- Zero raw `.badge` in TSX
- Zero `.icon-btn` in TSX
- Zero hex inline styles in TSX
- Zero `bg-white`/`border-gray-*`/`text-gray-*` in PaymentModal
- Zero `focus:ring-amber-500` in TSX

## Deviations

- `motoristas/[id]/page.tsx`, `viaturas/[id]/page.tsx`, `terceiros/[id]/page.tsx` — detail pages not included in Task 5 commit (separate task if needed; they were not in the uncommitted changes)
- `rotas-config/page.tsx` PageHeader added in Task 5 executor commit (before session limit)
