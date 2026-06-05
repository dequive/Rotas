---
phase: "03"
plan: "08"
subsystem: manager-frontend
tags: [tailwind, css-migration, sidebar, control-tower, cost-margin]
dependency_graph:
  requires: ["03-07"]
  provides: [SidebarLayout-tailwind, ControlTowerOverview-tailwind, CostMarginBoard-tailwind, analytics-nav-entry]
  affects: [apps/manager]
tech_stack:
  added: []
  patterns: [tailwind-css-tokens, tailwind-arbitrary-values, bg-nav, bg-panel, border-line, text-muted, text-ink]
key_files:
  created: []
  modified:
    - apps/manager/app/components/SidebarLayout.tsx
    - apps/manager/app/components/ControlTowerOverview.tsx
    - apps/manager/app/components/CostMarginBoard.tsx
    - apps/manager/tailwind.config.ts
decisions:
  - "Kept .compliance-grid, .queue-icon, .operational-heading, .data-source, .eyebrow, .tool-btn, .despacho-launch, .error-text, .empty-state in CSS — out of scope for this plan"
  - "Fixed tailwind.config.ts muted token from hsl(var(--muted)) to var(--muted) — CSS variable is hex, not HSL"
metrics:
  duration: "15m"
  completed_date: "2026-06-05"
  tasks_completed: 2
  files_modified: 4
---

# Phase 03 Plan 08: Tailwind Migration — SidebarLayout, ControlTowerOverview, CostMarginBoard

**One-liner:** Migrated three core manager components from custom CSS classes to Tailwind utility tokens (bg-nav, bg-panel, border-line, text-muted, text-ink) and added /analytics BarChart2 nav entry to sidebar.

---

## What Was Built

All three components now use Tailwind utility classes instead of custom CSS class names. The `tailwind.config.ts` `muted` token was fixed so `text-muted` resolves correctly to `var(--muted)` (#667085).

**SidebarLayout.tsx:**
- `className="shell"` → `className="min-h-screen grid grid-cols-[248px_minmax(0,1fr)]"`
- `className="sidebar"` → `className="bg-nav text-white p-5 flex flex-col"`
- `className="brand"` → `className="text-[22px] font-extrabold mb-7 tracking-normal"`
- `className="nav"` → `className="grid gap-1.5 flex-1"`
- `className="logout-btn"` → full Tailwind utility string
- `className="main"` → `className="min-w-0 p-6"`
- New nav entry: `{ key: "analytics", label: "Análise", href: "/analytics", icon: BarChart2 }` between Viagens and Contratos

**ControlTowerOverview.tsx:**
- `className="tower-grid"` → `className="grid grid-cols-[repeat(6,minmax(0,1fr))] gap-[10px]"`
- `className="tower-metric ..."` → `className="min-h-[86px] min-w-0 p-3 flex items-center gap-[10px] bg-panel border border-line rounded-lg border-l-[4px] border-l-${tone}"`
- `className="worklist-grid"` → `className="grid grid-cols-[repeat(4,minmax(0,1fr))] gap-3 mt-[14px]"`
- `className="worklist"` → `className="min-w-0 p-[14px] bg-panel border border-line rounded-lg"`
- `className="worklist-item"` → inline Tailwind in map
- `className="fleet-strip"` → `className="flex flex-wrap gap-x-[18px] gap-y-[6px] mt-3 px-3 py-[10px] bg-[#edf2f7] border border-line rounded-md"`
- `className="fleet-fact"` → `className="flex items-center gap-[6px] text-muted text-[12px]"`

**CostMarginBoard.tsx:**
- `className="cost-kpis"` → `className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-3 mb-4"`
- `className="cost-work-grid"` → `className="grid grid-cols-[minmax(0,1fr)_minmax(0,0.8fr)] gap-[14px]"`
- `className="cost-panel"` → `className="min-w-0 p-[14px] bg-panel border border-line rounded-lg"`
- `className="cost-item ..."` → `className="min-w-0 grid grid-cols-[minmax(0,1fr)_auto] gap-3 items-center p-[10px] border border-line rounded-lg bg-panel"`
- `className="margin-governance"` → `className="grid gap-2 justify-items-end"` (inline on NegativeMarginItem)

---

## Commits

| Hash | Message |
|------|---------|
| 8190380 | feat(03-08): migrate SidebarLayout to Tailwind + add /analytics nav entry |
| 681e6a3 | feat(03-08): migrate ControlTowerOverview and CostMarginBoard to Tailwind |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed tailwind.config.ts muted color token**
- **Found during:** Task 1 preparation
- **Issue:** `muted` was defined as `hsl(var(--muted))` but `--muted` in globals.css is `#667085` (hex, not HSL). `text-muted` would render as invalid CSS `hsl(#667085)`.
- **Fix:** Changed `muted: { DEFAULT: 'hsl(var(--muted))', foreground: ... }` to flat `muted: 'var(--muted)'`
- **Files modified:** `apps/manager/tailwind.config.ts`
- **Commit:** 8190380

---

## Known Stubs

None — all migrations are structural (CSS class replacement). No data flows were changed.

---

## Self-Check: PASSED

All files found, commits verified:
- FOUND: apps/manager/app/components/SidebarLayout.tsx
- FOUND: apps/manager/app/components/ControlTowerOverview.tsx
- FOUND: apps/manager/app/components/CostMarginBoard.tsx
- FOUND: .planning/phases/03-manager-dashboard-reporting-layer/03-08-SUMMARY.md
- FOUND: commit 8190380 (SidebarLayout)
- FOUND: commit 681e6a3 (ControlTowerOverview + CostMarginBoard)
