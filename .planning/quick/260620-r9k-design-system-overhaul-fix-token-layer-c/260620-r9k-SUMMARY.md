---
phase: quick
plan: 260620-r9k
subsystem: manager-frontend
tags: [design-system, tokens, css, tailwind, components]
completed_at: "2026-06-20T18:06:23Z"
duration_minutes: 15
tasks_completed: 3
tasks_total: 3
files_created: 1
files_modified: 17
commits:
  - hash: "303f635"
    message: "fix CSS token layer — spacing/radius/shadow vars, amber primary, badge tokens, tms fixes"
  - hash: "5e54336"
    message: "extend Tailwind config with spacing/radius/shadow tokens + create Button.tsx component"
  - hash: "d1b8b31"
    message: "migrate all primary-btn/login-btn consumers to Button + fix TmsExecutiveDashboard tone purple->info"
key-decisions:
  - "Trigger buttons in form modals (ContractFormModal, DriverFormModal, KnownRouteFormModal, VehicleFormModal) use conditional className (isEdit ? 'icon-btn' : 'primary-btn') — triggers intentionally kept as CSS per plan spec; submit buttons migrated to Button component"
  - "verify-email/page.tsx Link with login-btn class retained as CSS — Link elements render as <a> tags and cannot accept Button component without semantic change"
  - "Button component uses rounded-r-md (var(--r-md) = 6px) matching existing .primary-btn border-radius: 6px"
  - "TmsExecutiveDashboard: tone='purple' changed to tone='info'; type union updated; .tms-metric-icon.purple CSS rule replaced with .tms-metric-icon.info using var(--info-bg)/var(--info) tokens"
---

# Quick Task 260620-r9k: Design System Overhaul — Fix Token Layer + Create Reusable Components

**One-liner:** Fixed 4-layer design token stack: CSS vars → Tailwind config → utility classes → React components — eliminating hardcoded hex values, establishing amber as primary action color, creating typed Button component, and migrating 13 call sites.

---

## What Was Built

### Task 1: globals.css Token Layer

- Added 16 new CSS custom properties to `:root`:
  - Spacing scale: `--s1` (4px) through `--s8` (48px)
  - Border radius: `--r-sm` (4px), `--r-md` (6px), `--r-lg` (8px), `--r-xl` (12px)
  - Elevation: `--shadow-sm`, `--shadow-md`
- Fixed `.eyebrow`: `var(--blue)` → `var(--amber)`
- Fixed `.badge`: added `gap: 6px` + `::before` colored dot pseudo-element
- Fixed `.badge.*` variants: all 5 color variants now use semantic tokens exclusively (no raw hex)
- Fixed `.primary-btn`: `var(--blue)` → `var(--amber)`, `#ffffff` → `var(--ink)`, added hover rule
- Fixed `.login-btn`: same amber/ink migration + hover rule
- Fixed `.tool-btn.primary`: amber migration + hover rule
- Fixed `.tms-hero`: replaced 3-layer gradient with `var(--sidebar-bg)`
- Fixed `.tms-line-chart span`: gradient → `var(--blue)`
- Replaced `.tms-metric-icon.purple` with `.tms-metric-icon.info` using `var(--info-bg)` / `var(--info)`
- Fixed `.tms-metric-icon.*` remaining variants to use semantic tokens (no raw hex)

### Task 2: Tailwind Config + Button.tsx

- Extended `tailwind.config.ts`:
  - `borderRadius`: added `r-sm`, `r-md`, `r-lg`, `r-xl` mapped to CSS vars
  - `spacing`: added `s1`–`s8` mapped to CSS vars
  - `boxShadow`: added `design-sm`, `design-md` mapped to CSS vars
- Created `apps/manager/app/components/ui/Button.tsx`:
  - `'use client'` directive (event handlers)
  - Exported `ButtonVariant` type: `'primary' | 'secondary' | 'ghost' | 'danger'`
  - Exported `ButtonSize` type: `'sm' | 'md'`
  - `loading` prop renders `'...'` and sets disabled
  - All styles via Tailwind utility classes derived from the token system — no hardcoded hex

### Task 3: Consumer Migration + TmsExecutiveDashboard Fix

- `TmsExecutiveDashboard.tsx`: `tone="purple"` → `tone="info"`, type union updated
- Migrated to `<Button variant="primary">`:
  - `login/page.tsx` — submit button
  - `register/page.tsx` — submit button
  - `reset-password/page.tsx` — submit button
  - `forgot-password/page.tsx` — submit button
  - `security/page.tsx` — 2 MFA buttons (Confirmar MFA + Ativar MFA)
  - `clientes/NovoClienteButton.tsx` — trigger button
  - `ClientFormModal.tsx` — submit button
  - `ContractFormModal.tsx` — submit button (trigger kept as conditional CSS class)
  - `DriverFormModal.tsx` — submit button (trigger kept as conditional CSS class)
  - `KnownRouteFormModal.tsx` — submit button (trigger kept as conditional CSS class)
  - `VehicleFormModal.tsx` — submit button (trigger kept as conditional CSS class)
  - `TripFormModal.tsx` — trigger button + submit button
  - `CostMarginBoard.tsx` — 2 `tool-btn primary` action buttons

---

## Verification Results

All plan verification criteria pass:

1. `grep -r "primary-btn\|login-btn" apps/manager/app --include="*.tsx"` → Only conditional trigger buttons (isEdit pattern) and one Link anchor remain — all intentional per plan spec
2. `grep "var(--blue)\|var(--amber)" apps/manager/app/globals.css | grep "primary-btn\|login-btn\|tool-btn"` → All hits show `var(--amber)`
3. `grep "purple" apps/manager/app/globals.css` → No hits
4. `grep "purple" apps/manager/app/components/TmsExecutiveDashboard.tsx` → No hits
5. `grep "#[0-9a-fA-F]" apps/manager/app/globals.css | grep -E "badge\.|tms-metric"` → No hits
6. `npx tsc --noEmit` from apps/manager → exit 0, 0 errors

---

## Deviations from Plan

None — plan executed exactly as written. The plan spec explicitly documented the conditional trigger button pattern and the Link anchor exception as expected non-changes.

---

## Known Stubs

None — no stub data or placeholder content introduced.

## Self-Check: PASSED

- `apps/manager/app/components/ui/Button.tsx` — FOUND
- `apps/manager/app/globals.css` contains `--s1` — FOUND
- `apps/manager/tailwind.config.ts` contains `s1:` — FOUND
- Commit `303f635` — FOUND
- Commit `5e54336` — FOUND
- Commit `d1b8b31` — FOUND
