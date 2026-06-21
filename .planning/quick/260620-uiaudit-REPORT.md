# ROTAS Manager — UI Design Audit Report

**Audited:** 2026-06-20  
**Baseline:** DESIGN.md (root of repo)  
**Screenshots:** Not captured (no dev server running — code-only audit)  
**Scope:** `apps/manager/app/` — all TSX files (75 files examined)

---

## Executive Summary

**Overall Score: 5.5 / 10**

The design system infrastructure is solid. Tokens are defined correctly in `globals.css`, Tailwind mappings exist in `tailwind.config.ts`, and the canonical `Button`, `StatusBadge`, `KpiCard`, `DataTable`, and `PageHeader` components are well-implemented and correct. The architecture is sound.

The problem is uneven adoption. Approximately half the codebase — particularly older modal components, the `ar/`, `terceiros/`, and `cobranca/` pages — bypasses the token system entirely through a mix of: raw inline `style={{}}` objects, Tailwind arbitrary color classes (`amber-500`, `gray-200`, `slate-700`), hardcoded hex values in JSX, and legacy CSS classes (`primary-btn`, `icon-btn`, `secondary-btn`, `login-btn`) that DESIGN.md declared deprecated in favour of `<Button variant="...">`.

### Top 3 Blockers

1. **`PaymentModal.tsx` is fully off-system** — uses `gray-200`, `gray-700`, `gray-50`, `gray-500`, `bg-white`, `bg-amber-500`, `hover:bg-amber-600`, `text-white`, `shadow-2xl` throughout. Every input, label, and button in this modal violates design tokens. This is a high-visibility modal (triggered from both `cobranca/` and `clientes/[id]/`).

2. **`bg-primary` / `border-primary` / `text-primary` used as button/tab colours in 4 files** — `AlertsClient.tsx` (tab active state), `cobranca/page.tsx` (disabled generate button), `SettingsClient.tsx` (3 save buttons). `--primary` maps to amber via shadcn HSL tokens, so the visual result may be correct, but it breaks the design contract — code should use `bg-amber` + `text-ink` (the canonical primary button pattern), not shadcn's `bg-primary`. If the HSL mapping ever drifts, these silently break.

3. **332 raw Tailwind spacing values (`p-4`, `gap-3`, `mt-6`, etc.) vs. 0 design-token spacing classes (`p-s4`, `gap-s2`, `mt-s6`)** — the `--s1`–`--s8` spacing tokens and their Tailwind utilities are mapped in `tailwind.config.ts` but never used anywhere in the codebase. All spacing is raw Tailwind numbers, making the system non-scalable and inconsistent in density.

---

## Section-by-Section Findings

### 1. Token Compliance — FLAG

**Verdict: FLAG**

**Rule:** No hex values outside `:root`. No inline styles with hardcoded values. Only `var(--token)` or mapped Tailwind classes in component code.

**Findings:**

**A — Hardcoded hex in TSX (CRITICAL violations):**

| File | Line | Value | Issue |
|------|------|-------|-------|
| `cobranca/IssueDocumentButton.tsx` | 29–30 | `#d97706`, `#f59e0b`, `#0f1623` | Three hardcoded hex values in a single button's inline style |
| `components/DocumentUploadModal.tsx` | 79, 268 | `color: "#fff"` | Hardcoded white on amber button trigger and submit button |
| `components/FuelPurchaseModal.tsx` | 107, 333 | `color: "#fff"` | Same pattern — amber button with hardcoded white text |
| `manutencao/components/WorkOrderFormModal.tsx` | 112, 347 | `color: "#fff"` | Same pattern |
| `components/TmsExecutiveDashboard.tsx` | 177 | `#16a34a`, `#2563eb`, `#f59e0b`, `#dc2626` in conic-gradient | Four hex values hardcoded in donut chart gradient |
| `analytics/page.tsx` | 262 | `bg-[#fee4e2]` | Tailwind arbitrary hex in className |

**B — Inline style objects that bypass Tailwind entirely:**

`DocumentUploadModal.tsx` — the entire modal is built with `style={{}}` objects: 241 inline `var()` references and hardcoded values. Not a single Tailwind class in the modal body. This is the most severe single-file violation.

`components/ClientCombobox.tsx` and `components/ThirdPartyCombobox.tsx` — both comboboxes are constructed entirely with inline style objects including hardcoded pixel values for widths, max-heights, and paddings.

`components/DriverScorecardPanel.tsx` — uses inline style objects throughout including hardcoded `fontSize: 14`, `marginBottom: 16` values.

**C — Legacy CSS var() aliases still referenced in JSX:**

`--muted` (not `--muted-color`), `--border` (not `--border-color`), `--font-mono` (non-standard variable) — appear in inline styles across `ClientFormModal.tsx` (line 214), `clientes/[id]/page.tsx` (line 276), `ar/page.tsx` (line 178), `DocumentUploadModal.tsx` (line 113). The globals.css keeps these as aliases for compatibility but DESIGN.md marks them deprecated.

**D — `amber-light` border missing from globals.css:**

DESIGN.md documents `--amber-light-border` — not present in `globals.css`. The spec is ahead of the implementation.

---

### 2. Color Harmony and Hierarchy — FLAG

**Verdict: FLAG**

**A — `bg-primary` / `text-primary` used for buttons and tab indicators (4 files):**

- `apps/manager/app/alertas/AlertsClient.tsx` lines 98, 108: Tab active state uses `border-primary text-primary`. Should be `border-amber text-amber-dark`.
- `apps/manager/app/cobranca/page.tsx` line 127: Disabled "Gerar Documento" button uses `bg-primary text-primary-foreground`. Should be `bg-amber text-ink opacity-50`.
- `apps/manager/app/settings/SettingsClient.tsx` lines 256, 387, 455: Three save/submit buttons use `bg-primary text-primary-foreground`. Should use `<Button variant="primary">`.

**B — Raw Tailwind color classes bypassing semantic tokens:**

- `ar/page.tsx` lines 62–116: Ageing buckets use `bg-slate-50`, `border-slate-200`, `text-slate-700`, `text-red-700`, `text-red-800`, `bg-red-50`, `border-red-300`, `bg-amber-50`, `border-amber-300`, `text-amber-700`. Should use `bg-surface-2`, `border-border`, `text-muted`, `bg-error-bg`, `border-error-border`, `text-error`, `bg-warning-bg`, `border-warning-border`, `text-warning`.
- `PaymentModal.tsx` lines 126–229: `bg-white`, `border-gray-200`, `text-gray-700`, `hover:bg-gray-50`, `bg-amber-500`, `hover:bg-amber-600`, `text-white`. Should use `bg-surface`, `border-border`, `text-ink`, `hover:bg-surface-2`, `bg-amber`, `hover:bg-amber-dark`, `text-ink`.
- `components/DocumentExpiryBanner.tsx` and `components/LimitWarningBanner.tsx` lines 43–73: `bg-red-600`, `text-white`, `bg-amber-700`. The `bg-red-600` bypasses `--error` and `bg-error`. The `text-white` bypasses design system text colours for dark backgrounds. These banners are visible on every authenticated page.
- `viaturas/page.tsx` lines 28–29: Document status pills use `bg-success text-white` and `bg-warning text-white`. The `text-white` conflicts with the design system where `--success-bg` / `text-success` are the canonical pattern (coloured dot + text, not filled + white).
- `clientes/[id]/page.tsx` line 143: Call-to-action button uses `bg-amber-500 hover:bg-amber-600 text-white`. Should be `bg-amber hover:bg-amber-dark text-ink`.

**C — No purple found** — PASS. No purple anywhere in the codebase.

**D — Blue used correctly** — PASS. Blue is used for links, informational states, and secondary indicators, not primary actions.

---

### 3. Typography — PASS (minor gaps)

**Verdict: PASS with minor issues**

**Font loading:** Both Manrope and IBM Plex Mono loaded correctly via Google Fonts in `layout.tsx` (lines 96–101). Font family is set on `body` in globals.css.

**IBM Plex Mono (font-mono) coverage:** 71 uses across the codebase. KPI values, plate numbers, work order numbers, monetary amounts, IDs, and dates are generally using `font-mono` or `className="font-mono"`. The `KpiCard`, `MonoCell`, `MoneyCell` components enforce it structurally.

**Gaps found:**

- `motoristas/page.tsx` lines 73–80: License numbers, passport numbers, BI numbers rendered as plain `<td>` text without `font-mono`. These are document IDs that should use `MonoCell` or `className="font-mono"`.
- `viagens/page.tsx` line 88: Vehicle plates rendered as `<strong>` without `font-mono`. Should use `className="plate font-mono"` or `<MonoCell>`.
- `contratos/page.tsx` (not read — likely has similar issues given it uses the legacy `.table` pattern).
- `manutencao/page.tsx` line 152: Work order number uses `className="font-mono font-medium"` — CORRECT. Good example.
- `alertas/AlertsClient.tsx` lines 226, 232: `alert_type` and `created_at` timestamps use `font-mono` — correct.
- Date columns in `motoristas/page.tsx` use raw string formatting without `font-mono`.

**Typography scale:** The canonical sizes (`text-[11px]`, `text-[13px]`, `text-[26px]`) are used consistently in the ui/ components. Pages largely follow the pattern. No `text-5xl`, `text-4xl` or outsize font sizes detected.

---

### 4. Component Consistency — BLOCK

**Verdict: BLOCK**

**A — Legacy CSS button classes still in active use (not migrated to `<Button>`):**

`Button.tsx` exists and is correct. The problem is that the majority of interactive buttons in the app still use the legacy CSS classes.

Files using `.primary-btn`:
- `components/ContractFormModal.tsx` line 84
- `components/DriverFormModal.tsx` line 54
- `components/KnownRouteFormModal.tsx` line 48
- `components/VehicleFormModal.tsx` line 54

Files using `.secondary-btn`:
- `clientes/[id]/EditarClienteButton.tsx` line 13
- `components/ClientFormModal.tsx` line 322
- `components/ContractFormModal.tsx` line 175
- `components/DriverFormModal.tsx` line 100
- `components/KnownRouteFormModal.tsx` line 89
- `components/PairingCodeButton.tsx` line 78
- `components/TripFormModal.tsx` line 282
- `components/VehicleFormModal.tsx` line 102
- `forgot-password/page.tsx` line 83
- `security/page.tsx` lines 162, 183
- `verify-email/page.tsx` line 61

Files using `.icon-btn`:
- `clientes/ClientsTable.tsx` line 133
- `components/ClientFormModal.tsx` line 165
- `components/ContractFormModal.tsx` lines 84 (as `icon-btn`), 93
- `components/DriverFormModal.tsx` line 63
- `components/KnownRouteDeleteButton.tsx` line 24
- `components/KnownRouteFormModal.tsx` lines 48, 56
- `components/PairingCodeButton.tsx` lines 49, 60, 70
- `components/TripFormModal.tsx` line 146
- `components/VehicleFormModal.tsx` lines 54, 63
- `viaturas/page.tsx` line 118

Files using `.login-btn`:
- `verify-email/page.tsx` line 53

**Total:** 28 individual button instances across 14 files bypassing the `<Button>` component.

**B — Shadcn `<Badge>` used directly (bypasses `<StatusBadge>`):**

`components/BillingTripActions.tsx` lines 314, 316, 329, 331, 346, 348, 353, 355, 503 — uses shadcn `<Badge>` component with manual class overrides instead of `<StatusBadge>`. The shadcn Badge does not guarantee dot rendering.

`components/DriverScorecardPanel.tsx` lines 18–21, 132, 142 — uses raw `.badge` CSS class string directly instead of `<StatusBadge>`.

`components/MaintenanceImminentPanel.tsx` lines 42, 67, 73 — uses raw `.badge`, `.badge.red` CSS strings directly.

**C — `viagens/page.tsx` and `motoristas/page.tsx` use raw `.table`, `.panel` classes** (lines 61, 78 in viagens) instead of the `DataTable`, `RotasTableRow`, `RotasTableHeader` components. This means no consistent hover state, no sticky actions column behaviour, and no ARIA labels.

---

### 5. Badge Dots — FLAG

**Verdict: FLAG**

**`StatusBadge.tsx` is correct** — uses `<span className={cn('h-1.5 w-1.5 rounded-full flex-shrink-0', cfg.dot)} />` as the dot element. Good.

**`globals.css` `.badge::before`** also correctly defines a dot via pseudo-element.

**Issues:**

- `components/DriverScorecardPanel.tsx` line 21: `cls: "badge"` (no colour class) for "insuficiente" tier produces a badge with no background and a dot that inherits whatever colour is current — visually invisible. Should map to a neutral or muted variant.
- `components/MaintenanceImminentPanel.tsx` line 73: `<span className="badge">` with no colour modifier — same issue, no visible dot colour.
- `ar/page.tsx` line 270: Custom inline badge `inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium` uses a dot span (`bucketDotClass`) — dot is present. But `rounded-full` instead of DESIGN.md's `--r-sm` (4px) on badges. Minor.
- `viagens/page.tsx` lines 102, 105: Uses `<span className={`badge ${statusMeta.tone}`}>` — this uses the `.badge::before` pseudo-element which is correct. However the tone values include `"blue"`, `"cyan"`, `"orange"`, `"green"`, `"red"` which map to the CSS colour modifiers in globals.css. These are present and correct. PASS for this specific case.

---

### 6. Sidebar — PASS

**Verdict: PASS**

`components/SidebarLayout.tsx` implements the DESIGN.md mandated structure exactly:

- 4 sections: Operações / Frota / Financeiro / Config
- Items per section match the spec (Torre de Controlo, Viagens, Despachos / Viaturas, Motoristas, Manutenção, Terceiros / Clientes, Contratos, Cobrança, Contas a Receber, Análise / Destinos, Alertas, Segurança, Definições)
- Active item has `border-l-2 border-amber` (line 172: `"border-amber pl-[10px]"`)
- Section labels hidden on collapse, dividers shown
- 248px width / 56px collapsed
- Hover states via `onMouseEnter`/`onMouseLeave` with CSS var values — correct though slightly verbose (could be Tailwind)
- One minor issue: hover behaviour uses imperative `element.style.background` manipulation instead of Tailwind hover classes. Functional but not idiomatic — and `style={{ background: "var(--sidebar-bg)" }}` on the aside (line 103) uses inline style instead of `bg-sidebar-bg` Tailwind class.

---

### 7. Spacing and Layout — BLOCK

**Verdict: BLOCK**

**Design-token spacing usage: 0 instances.** The `--s1`–`--s8` tokens are defined in `:root` and mapped to `p-s1`–`p-s8`, `gap-s1`–`gap-s8`, etc. in `tailwind.config.ts`. Zero components or pages use them.

Instead: 332 instances of raw Tailwind spacing (`p-4`, `gap-3`, `mt-6`, `space-y-6`, `px-3`, `py-2.5`, `mb-4`, etc.) are used throughout the codebase.

This is not purely cosmetic — it means:
- Spacing density cannot be adjusted from a single token
- No guarantee that similar elements use the same spacing
- The `p-6` used in page content areas matches `--s6` (24px) in value, but not by reference — a token change would not propagate

**Specific inconsistencies observed:**

- `manutencao/page.tsx` uses `space-y-6` and `gap-4` throughout
- `cobranca/page.tsx` uses `gap-3`, `mb-4`, `mb-6`, `mb-8` — three different bottom margin values for section separation
- `alertas/AlertsClient.tsx` uses `space-y-6`, `gap-4`, `mt-3`, `mb-4`
- `globals.css` utility classes use raw CSS pixel values (`gap: 6px`, `padding: 14px`) that don't reference `--s*` tokens

The only consistent exception is `p-6` on the main content area in `SidebarLayout.tsx` (line 232), which happens to match `--s6` (24px) numerically.

**Border radius:** `rounded-lg` is used 115 times. This maps to `--radius` (0.375rem / 6px via shadcn) NOT to `--r-lg` (8px / DESIGN.md). The DESIGN.md utilities are `rounded-r-sm`, `rounded-r-md`, `rounded-r-lg`, `rounded-r-xl` (defined in `tailwind.config.ts` as `r-sm`, `r-md`, `r-lg`, `r-xl`). Every `rounded-lg` in a card or panel should be `rounded-r-lg` to match DESIGN.md's 8px card radius. This affects virtually every card in the app.

---

### 8. Motion and Transitions — PASS (minor issues)

**Verdict: PASS**

`globals.css` defines three transition tokens: `--transition-fast: 80ms ease-out`, `--transition-base: 100ms ease-out`, `--transition-modal: 150ms ease-out`.

The `Button.tsx` canonical component uses `transition-colors duration-100` — correct.

Table rows in `DataTable.tsx` use `transition-colors duration-75` — correct (maps to 75ms, close to `--transition-fast`).

`SidebarLayout.tsx` uses `transition-colors duration-100` on nav links — correct.

Modal components do not use `transition-modal` (150ms) — they appear/disappear without animation, which per DESIGN.md should be `150ms ease-out`. Not a blocking issue since the spec says "minimal-functional" but it's a gap.

**Issues:**

- `FuelPurchaseModal.tsx`, `WorkOrderFormModal.tsx`, `ClientCombobox.tsx`, `ThirdPartyCombobox.tsx`: Use inline `transition: "background 80ms ease-out"` or `"border-color 80ms ease-out"` in style objects. Should be Tailwind `transition-colors duration-75` instead.
- `DocumentExpiryBanner.tsx`, `LimitWarningBanner.tsx`: Use `transition-opacity` on action links — not in the token set, but acceptable for links.

---

### 9. Table Design — FLAG

**Verdict: FLAG**

`DataTable.tsx` with `RotasTableHeader`, `RotasTableRow`, `RotasTableCell` is correctly designed:
- Header: `text-[11px] font-semibold uppercase tracking-wide text-muted h-9 px-3` — matches spec
- Row hover: `hover:bg-surface-2 transition-colors duration-75` — correct
- Sticky actions: `sticky right-0 bg-surface shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)]` — correct

**Issues:**

1. **`viagens/page.tsx`** (lines 62–117): Uses raw `.table`, `.panel`, `.table-wrap` CSS classes instead of `DataTable`/`RotasTableRow`. The `.table th` in globals.css uses `color: var(--muted-color)` and `font-weight: 700` — not `text-xs uppercase tracking-wide` as per DESIGN.md spec. The Viagens page is a high-traffic page and its table is off-spec.

2. **`motoristas/page.tsx`** (same pattern): Raw `.table` class used throughout.

3. **`viaturas/page.tsx`** (same pattern): Raw `.table` class. Additionally, the document status pills (`DOC_COLORS`) use `bg-success text-white` and `bg-warning text-white` — filled pill with white text, not the semantic `bg-success-bg text-success` pattern. The table header in `.table th` is `color: var(--muted-color); font-weight: 700` vs. the `DataTable`'s `font-semibold uppercase tracking-wide text-muted` — the global CSS table is slightly off the spec (missing uppercase/tracking).

4. **Table header background missing in raw `.table`**: The `DataTable` wrapper renders headers inside shadcn's `<TableHeader>` which has `bg-surface-2`. The raw `.table th` has no background — visually different from DESIGN.md's "Header row: fundo `--surface-2`".

---

### 10. Form Inputs — FLAG

**Verdict: FLAG**

**DESIGN.md requirement:** `border: 1px solid var(--border-color)`, `background: var(--surface)`. Focus: `border-color: var(--amber)`, `box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.12)`.

**Findings:**

1. **No focus amber ring on most inputs** — the modal form inputs (`.modal-form input`) have no focus styles in globals.css. The only defined focus style is in `ClientsTable.tsx` line 65: `focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500`. PaymentModal inputs use `focus:ring-2 focus:ring-amber-500 focus:border-amber-500` — correct intent but `amber-500` instead of the token-mapped `amber` and the box-shadow is `ring-2` not `0 0 0 3px`.

2. **`PaymentModal.tsx` inputs** (lines 144, 163, 176, 194, 208): `border-gray-200` instead of `border-border`. Labels use `text-gray-500` instead of `text-muted`. The entire modal's input styles are off-system.

3. **`DocumentUploadModal.tsx`** uses `border: "1px solid var(--border-strong)"` (slightly stronger than `--border-color` per spec) and no focus styles in the inline style object.

4. **`login-form input`** in globals.css has no focus styles defined — the login inputs have no visible focus indicator. This is an accessibility issue.

---

### 11. Modal and Dialog Patterns — FLAG

**Verdict: FLAG**

**DESIGN.md requirement:** `border-radius: var(--r-xl)` (12px), `padding: var(--s6)` (24px), backdrop `rgba(15, 23, 42, 0.45)`, header with title 18px + close button, actions footer with `border-top`.

**What's correct:** `globals.css` `.modal` class: `border-radius: 12px`, `padding: 24px`. `.modal-header h2`: `font-size: 18px`. `.modal-actions`: `border-top: 1px solid var(--border-color)`. These are correct and used by `DriverFormModal`, `VehicleFormModal`, `TripFormModal`, `ContractFormModal`, `KnownRouteFormModal`.

**Issues:**

1. **`PaymentModal.tsx`** (lines 113–230): Completely custom modal implementation — does not use `.modal`, `.modal-header`, `.modal-actions`. Uses `bg-white rounded-xl shadow-2xl p-6` — off-system. The close button is an `<X>` icon in a custom button. No `.modal-backdrop` class. The backdrop is `fixed inset-0 z-50 flex items-center justify-center bg-black/60` vs. spec's `rgba(15, 23, 42, 0.45)`. The `bg-black/60` is visually darker than the design system backdrop.

2. **`DocumentUploadModal.tsx`** (lines 118–270): Entirely inline-styled modal with no CSS class reuse. The backdrop is `rgba(0,0,0,0.50)` instead of the DESIGN.md `rgba(15, 23, 42, 0.45)`. Modal padding is 24px (correct), border-radius uses `var(--r-xl, 12px)` (correct), but everything else is inline styles.

3. **`PairingCodeButton.tsx`** (lines 49–78): Uses `.modal`, `.modal-header`, `.modal-actions` CSS classes — correct pattern.

4. **`manutencao/components/WorkOrderFormModal.tsx`**: Uses `style={{}}` objects for the modal shell instead of `.modal` CSS class. Different trigger button pattern (native button with inline styles, not `<Button>`).

**Pattern gap:** There are three distinct modal implementations in the codebase: (a) CSS-class-based via `.modal`/`.modal-header` (correct), (b) inline-style-based (DocumentUploadModal, PaymentModal), (c) Tailwind-based (FuelPurchaseModal). No unified modal shell component exists.

---

### 12. KPI Cards and Metric Tiles — PASS

**Verdict: PASS**

`KpiCard.tsx` is correctly implemented and widely used. It:
- Uses `bg-surface border border-border rounded-lg p-4 shadow-sm`
- Renders value in `font-mono text-[26px] font-medium tabular-nums`
- Supports `semantic` prop for colour
- Supports `loading` state with skeleton
- Supports trend with direction arrows

Used correctly in: `manutencao/page.tsx`, `cobranca/page.tsx`, `ar/page.tsx`.

**Minor gaps:**
- `analytics/page.tsx` (lines 141–159): Uses shadcn `<Card>` with `<KpiCard>` inside — double-wrapping that adds unnecessary border/background. Should just use `<KpiCard>` directly.
- `page.tsx` (home/dashboard): Does not use `<KpiCard>` for the quick-access section cards at the bottom. Those are custom `<a>` elements. Not a metric tile context so this is acceptable.
- `tms-metric` in globals.css defines a parallel metric tile pattern (`.tms-metric` with `font-size: 26px`) that overlaps with `<KpiCard>`. The `TmsExecutiveDashboard.tsx` uses the CSS class pattern instead of `<KpiCard>`. Two inconsistent metric patterns exist simultaneously.

---

### 13. Page-Level Layout — FLAG

**Verdict: FLAG**

**Consistent pages (PASS):** `manutencao/page.tsx`, `cobranca/page.tsx`, `ar/page.tsx` use `<PageHeader>` component — correct.

**Inconsistent pages (FLAG):**

- `viagens/page.tsx` (lines 46–59): Uses raw `.page-header` CSS class with raw `<h1>` and `<p>` — not `<PageHeader>`.
- `motoristas/page.tsx` (lines 27–34): Same — raw `.page-header` CSS class.
- `viaturas/page.tsx` (lines 44–51): Same — raw `.page-header` CSS class.
- `alertas/page.tsx` (not read but `AlertsClient.tsx` shows no `PageHeader` usage — `SectionHeader` is used for sub-sections, but the page header itself is likely missing or a raw div).

**No breadcrumb pattern exists anywhere** — DESIGN.md does not specify breadcrumbs explicitly, but for detail pages (`/viaturas/[id]`, `/motoristas/[id]`, `/clientes/[id]`) there is no back navigation or breadcrumb trail. Users on a vehicle detail page have no visual indicator of where they are in the hierarchy beyond the sidebar.

**Page padding inconsistency:**
- `SidebarLayout.tsx` applies `p-6` (24px) on the content area wrapper
- `TmsExecutiveDashboard.tsx` adds `padding: 0 24px 24px` internally via `.tms-executive` — this doubles the horizontal padding on the home page (48px total sides vs. 24px on other pages)
- `page.tsx` (home) has `px-6` on the shortcuts section at the bottom (line 58), which is inside the `p-6` wrapper — resulting in 48px total

---

### 14. Responsive and Mobile — FLAG

**Verdict: FLAG**

`globals.css` has responsive breakpoints at 1100px and 760px that collapse grids to 1-column layouts. This is functional.

**Issues:**

1. **`@media (max-width: 760px)` sidebar behaviour**: The sidebar becomes `position: sticky; top: 0` and the `.nav` becomes `grid-template-columns: repeat(2, minmax(0, 1fr))` — a horizontal 2-column nav grid. This means section labels (Operações/Frota/Financeiro/Config) are lost at mobile. The section grouping — a DESIGN.md hard requirement — disappears on mobile. The sidebar becomes a flat 2-column icon grid.

2. **`SidebarLayout.tsx` has no mobile behaviour** — it implements collapse but not the 760px responsive CSS. The SidebarLayout uses inline grid styles (`gridTemplateColumns: collapsed ? "56px" : "248px" ...`), which at 760px would conflict with the `.shell` CSS that removes the sidebar column. Since the layout is in a React component rather than the CSS class, the CSS media query may not apply correctly.

3. **`PaymentModal.tsx`**: `max-w-lg` on the modal — good. But the form grid (5+ form fields) has no mobile stack — at 375px width inputs may be clipped.

4. **`cobranca/page.tsx` work-queue section** (line 170): `grid-cols-2 md:grid-cols-3 xl:grid-cols-5` — at mobile (375px) this is 2 columns of work queues, each queue containing a list of truncated trip references. Functional but tight.

5. **Tables in raw `.table` class** have `min-width: 1120px` (globals.css line 1295) and are wrapped in `.table-wrap` with `overflow-x: auto`. This is correct for wide tables but provides no mobile-optimized fallback view.

---

## Prioritized Gap List

### CRITICAL — Breaks Brand / Token Contract

| # | Issue | Files | Impact |
|---|-------|-------|--------|
| C-1 | `PaymentModal.tsx` uses 100% off-system styles: `gray-*`, `bg-white`, `shadow-2xl`, `amber-500`/`amber-600` | `components/PaymentModal.tsx` | Every payment registration action bypasses design system |
| C-2 | Hardcoded hex in buttons: `#f59e0b`, `#d97706`, `#fff`, `#0f1623` directly in JSX/inline styles | `cobranca/IssueDocumentButton.tsx:29-30`, `components/DocumentUploadModal.tsx:79,268`, `components/FuelPurchaseModal.tsx:107,333`, `manutencao/components/WorkOrderFormModal.tsx:112,347` | Token contract violated — hex cannot be themed |
| C-3 | `bg-primary`/`text-primary` used on buttons/tabs instead of `bg-amber`/`text-ink` | `alertas/AlertsClient.tsx:98,108`, `cobranca/page.tsx:127`, `settings/SettingsClient.tsx:256,387,455` | Breaks when shadcn HSL mapping drifts; not semantic |
| C-4 | 28 button instances across 14 files still using `.primary-btn`, `.secondary-btn`, `.icon-btn`, `.login-btn` CSS classes | See component consistency section | `<Button>` component ignored; variant behaviour inconsistent |
| C-5 | Hardcoded hex in conic-gradient for TMS donut chart | `components/TmsExecutiveDashboard.tsx:177` | Four hex values; first thing users see on home page |

### MAJOR — Visible Inconsistency

| # | Issue | Files | Impact |
|---|-------|-------|--------|
| M-1 | Zero design-token spacing classes used anywhere (`p-s4`, `gap-s2`, etc.) — 332 raw Tailwind spacing values | All files | Spacing system exists but is dead; density cannot be adjusted |
| M-2 | `rounded-lg` (6px shadcn radius) used instead of `rounded-r-lg` (8px DESIGN.md card radius) — 115 occurrences | Virtually all pages | Card corners 2px tighter than design spec |
| M-3 | `ar/page.tsx` ageing buckets use `slate-*` Tailwind raw classes instead of semantic tokens | `ar/page.tsx:62-116` | Accounts Receivable page has its own colour palette |
| M-4 | Three distinct modal implementations (CSS-class / inline-style / Tailwind) — no unified modal shell | `PaymentModal`, `DocumentUploadModal`, `FuelPurchaseModal` vs. modal CSS classes | Visual inconsistency between modals; padding, radius, backdrop colour differ |
| M-5 | Viagens/Motoristas/Viaturas tables use raw `.table` CSS class instead of `DataTable`/`RotasTableRow` | `viagens/page.tsx`, `motoristas/page.tsx`, `viaturas/page.tsx` | No bg-surface-2 header, no structured hover, no sticky actions cell |
| M-6 | Login/Register/Forgot-password/Verify-email pages use `.login-shell`/`.login-form`/`.login-btn`/`.secondary-btn` CSS classes; no `<Button>` usage except login submit | `login/page.tsx`, `register/page.tsx`, `forgot-password/page.tsx`, `verify-email/page.tsx` | Auth flow inconsistently styled vs. app body |
| M-7 | `DocumentUploadModal.tsx` entirely built with inline style objects — 80+ inline CSS declarations | `components/DocumentUploadModal.tsx` | Not maintainable; silently breaks on token changes |
| M-8 | Viagens/Motoristas/Viaturas pages use raw `.page-header` CSS class instead of `<PageHeader>` component | `viagens/page.tsx:46`, `motoristas/page.tsx:27`, `viaturas/page.tsx:44` | Three of the most-visited pages lack consistent header component |
| M-9 | `viaturas/page.tsx` document status pills use `bg-success text-white` / `bg-warning text-white` | `viaturas/page.tsx:28-29` | Filled-white pill vs. semantic `bg-success-bg text-success` convention |
| M-10 | `clientes/[id]/page.tsx` action button uses `bg-amber-500 hover:bg-amber-600 text-white` | `clientes/[id]/page.tsx:143` | `text-white` on amber is wrong (spec: `text-ink` on amber); also raw amber-500 not token |

### MINOR — Polish

| # | Issue | Files | Impact |
|---|-------|-------|--------|
| P-1 | Motor/driver license, passport, BI numbers not in `font-mono` | `motoristas/page.tsx:73-80` | Document IDs not tabular/monospace |
| P-2 | Vehicle plates in `viagens/page.tsx` not `font-mono` | `viagens/page.tsx:88` | Plate not tabular |
| P-3 | `.badge` (no colour) used for "insuficiente" driver tier and maintenance trigger label — invisible dot | `DriverScorecardPanel.tsx:21`, `MaintenanceImminentPanel.tsx:73` | Badge dot invisible |
| P-4 | Sidebar uses imperative `element.style.*` in `onMouseEnter`/`onMouseLeave` instead of Tailwind hover classes | `SidebarLayout.tsx:123-130, 179-188` | Works, but not idiomatic; harder to audit |
| P-5 | Modal transitions: no enter/exit animation — modals appear instantly | All modal implementations | Spec says 150ms ease-out open/close |
| P-6 | `analytics/page.tsx` wraps `<KpiCard>` inside shadcn `<Card>` — double border/shadow | `analytics/page.tsx:141-159` | KPI cards have double borders |
| P-7 | Two metric tile patterns: `<KpiCard>` and `.tms-metric` CSS class — parallel implementations | `TmsExecutiveDashboard.tsx` vs. `manutencao/page.tsx` | Executive dashboard metrics look different from other module metrics |
| P-8 | `login-form input` has no focus ring in CSS | `globals.css:1513-1521` | Login inputs have no focus indicator — accessibility gap |
| P-9 | Home page `TmsExecutiveDashboard` has 48px horizontal padding (24px from layout + 24px internal) vs. 24px on other pages | `page.tsx + TmsExecutiveDashboard.tsx` | Home page is visually tighter than all other pages |
| P-10 | Mobile sidebar (760px) loses section grouping — becomes flat 2-column icon grid | `globals.css:2301-2312` | DESIGN.md hard requirement (grouped sections) breaks on mobile |

---

## Files Audited

Primary reads:
- `DESIGN.md`
- `apps/manager/app/globals.css`
- `apps/manager/tailwind.config.ts`
- `apps/manager/app/layout.tsx`
- `apps/manager/app/page.tsx`
- `apps/manager/app/components/ui/Button.tsx`
- `apps/manager/app/components/ui/StatusBadge.tsx`
- `apps/manager/app/components/ui/KpiCard.tsx`
- `apps/manager/app/components/ui/PageHeader.tsx`
- `apps/manager/app/components/ui/SectionHeader.tsx`
- `apps/manager/app/components/ui/DataTable.tsx`
- `apps/manager/app/components/ui/EmptyState.tsx`
- `apps/manager/app/components/SidebarLayout.tsx`
- `apps/manager/app/login/page.tsx`
- `apps/manager/app/register/page.tsx`
- `apps/manager/app/viagens/page.tsx`
- `apps/manager/app/viaturas/page.tsx`
- `apps/manager/app/motoristas/page.tsx`
- `apps/manager/app/manutencao/page.tsx`
- `apps/manager/app/cobranca/page.tsx`
- `apps/manager/app/cobranca/IssueDocumentButton.tsx`
- `apps/manager/app/alertas/AlertsClient.tsx`
- `apps/manager/app/ar/page.tsx` (partial)
- `apps/manager/app/settings/SettingsClient.tsx` (partial)
- `apps/manager/app/analytics/page.tsx` (partial)
- `apps/manager/app/security/page.tsx` (partial)
- `apps/manager/app/components/PaymentModal.tsx` (partial)
- `apps/manager/app/components/DocumentUploadModal.tsx`
- `apps/manager/app/components/FuelPurchaseModal.tsx` (partial)
- `apps/manager/app/components/MaintenanceImminentPanel.tsx`
- `apps/manager/app/components/TmsExecutiveDashboard.tsx` (partial)
- `apps/manager/app/components/BillingTripActions.tsx` (grep)
- `apps/manager/app/components/DriverScorecardPanel.tsx` (partial)

Grep patterns applied to all 75 TSX files for:
- Hardcoded hex (`#[0-9a-fA-F]{3,8}`)
- Legacy CSS classes (`primary-btn`, `secondary-btn`, `icon-btn`, `login-btn`)
- `bg-primary`, `text-primary`, `border-primary`
- Tailwind colour bypasses (`slate-*`, `gray-*`, `amber-500`, `amber-600`, `red-600`, `bg-white`, `text-white`)
- IBM Plex Mono / font-mono usage
- Design-token spacing usage (`p-s*`, `gap-s*`)
- Focus ring implementation
- Badge/StatusBadge usage patterns
- Inline style objects
