---
phase: quick
plan: 260620-vlw
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/manager/app/cobranca/IssueDocumentButton.tsx
  - apps/manager/app/viagens/page.tsx
  - apps/manager/app/components/MaintenanceImminentPanel.tsx
  - apps/manager/app/rotas-config/page.tsx
  - apps/manager/app/components/ClientFormModal.tsx
  - apps/manager/app/components/ContractFormModal.tsx
  - apps/manager/app/components/DriverFormModal.tsx
  - apps/manager/app/components/KnownRouteFormModal.tsx
  - apps/manager/app/components/TripFormModal.tsx
  - apps/manager/app/components/PairingCodeButton.tsx
  - apps/manager/app/security/page.tsx
  - apps/manager/app/forgot-password/page.tsx
  - apps/manager/app/verify-email/page.tsx
  - apps/manager/app/components/ui/Input.tsx
  - apps/manager/app/components/ui/IconButton.tsx
  - apps/manager/app/components/PaymentModal.tsx
  - apps/manager/app/components/FleetComplianceBoard.tsx
  - apps/manager/app/ar/page.tsx
  - apps/manager/app/viagens/page.tsx
  - apps/manager/app/motoristas/page.tsx
  - apps/manager/app/contratos/page.tsx
  - apps/manager/app/viaturas/page.tsx
  - apps/manager/app/terceiros/page.tsx
  - apps/manager/app/analytics/page.tsx
autonomous: true
requirements: []

must_haves:
  truths:
    - "Zero hardcoded hex or rgb values in any TSX file (inline styles or Tailwind arbitrary)"
    - "No .secondary-btn CSS class used in any TSX file"
    - "No raw .badge CSS class used in any TSX file — all use <StatusBadge>"
    - "No .icon-btn CSS class used in any TSX file"
    - "Input component exists at apps/manager/app/components/ui/Input.tsx"
    - "IconButton component exists at apps/manager/app/components/ui/IconButton.tsx"
    - "PaymentModal uses only token-based classes (no border-gray-*, bg-white, text-gray-*)"
    - "viagens, motoristas, contratos, viaturas, terceiros, analytics, rotas-config pages use <PageHeader>"
---

<objective>
Enterprise design system migration wave 1: eliminate all remaining token violations and create missing reusable components (Input, IconButton) following the token-first cascade defined in DESIGN.md.

Execution order (user-approved):
1. Quick-win sweep: hex inline fix + .secondary-btn → Button + .badge → StatusBadge
2. Create Input/FormField component + migrate off-token inputs
3. Create IconButton component + migrate all .icon-btn usages
4. PaymentModal full token migration
5. PageHeader in missing pages
6. Mop-up: font-mono on monetary values, cleanup
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260620-vlw-design-system-migration-wave-1-quick-win/260620-vlw-PLAN.md

<design_system>
Key tokens from globals.css :root:
- Colors: --amber, --amber-dark, --ink, --ink-2, --muted-color, --surface, --surface-2, --border, --border-strong, --error, --error-bg, --success, --success-bg, --warning, --warning-bg, --info, --info-bg, --placeholder
- Tailwind mappings: bg-amber, bg-surface, bg-surface-2, border-border, text-ink, text-ink-2, text-muted (→ var(--muted-color)), text-placeholder, focus:border-amber, focus:ring-amber/20

Button component API (apps/manager/app/components/ui/Button.tsx):
- variants: 'primary' | 'secondary' | 'ghost' | 'danger'
- sizes: 'sm' | 'md' (default)
- import: import { Button } from '@/app/components/ui/Button'

StatusBadge component API (apps/manager/app/components/ui/StatusBadge.tsx):
- prop: status: StatusKey | string (falls back to neutral style for unknown keys)
- prop: label?: string (override display text)
- prop: className?: string
- import: import { StatusBadge } from '@/app/components/ui/StatusBadge'
- Known StatusKeys: 'em-rota', 'paragem', 'descarga', 'alerta', 'aguarda', 'concluida', 'cancelada', 'planeada', 'billed', 'billable', 'not_billable', 'waiver_required', 'draft', 'issued', 'valid', 'expiring_soon', 'expired', 'open', 'in_progress', 'completed', 'pending', 'approved', 'blocked', 'activo', 'inactivo'

PageHeader API (apps/manager/app/components/ui/PageHeader.tsx):
- props: eyebrow?, title, description?, actions?, meta?, className?
- import: import { PageHeader } from '@/app/components/ui/PageHeader'
</design_system>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Quick-win sweep — hex inline + .secondary-btn + raw .badge</name>
  <files>
    apps/manager/app/cobranca/IssueDocumentButton.tsx
    apps/manager/app/components/ClientFormModal.tsx
    apps/manager/app/components/ContractFormModal.tsx
    apps/manager/app/components/DriverFormModal.tsx
    apps/manager/app/components/KnownRouteFormModal.tsx
    apps/manager/app/components/TripFormModal.tsx
    apps/manager/app/components/PairingCodeButton.tsx
    apps/manager/app/security/page.tsx
    apps/manager/app/forgot-password/page.tsx
    apps/manager/app/verify-email/page.tsx
    apps/manager/app/viagens/page.tsx
    apps/manager/app/components/MaintenanceImminentPanel.tsx
    apps/manager/app/rotas-config/page.tsx
  </files>
  <action>
**1a — IssueDocumentButton.tsx (CRITICAL: only hex hardcode left)**

Replace the button's `style` + `className` with token-only approach using Button component:
- Add import: `import { Button } from '@/app/components/ui/Button'`
- Replace the `<button>` element with `<Button size="sm" disabled={loading} onClick={handleIssue}>{loading ? "A emitir..." : "Emitir"}</Button>`
- Remove the `style={{ backgroundColor: ... }}` entirely — Button primary variant already uses amber tokens

**1b — .secondary-btn → Button variant="secondary"** in each file:

Files and what to change:
- `ClientFormModal.tsx:322` — `<button className="secondary-btn" ...>` → `<Button variant="secondary" ...>`; add Button import
- `ContractFormModal.tsx:175` — `<button type="button" className="secondary-btn" ...>` → `<Button variant="secondary" type="button" ...>`
- `DriverFormModal.tsx:100` — same pattern
- `KnownRouteFormModal.tsx:89` — same pattern
- `TripFormModal.tsx:282` — same pattern
- `PairingCodeButton.tsx:78` — `<button className="secondary-btn" onClick={() => void generate()}>Novo código</button>` → `<Button variant="secondary" onClick={() => void generate()}>Novo código</Button>`
- `security/page.tsx:162` — `<button className="secondary-btn" onClick={loadSessions} disabled={loading}>` → `<Button variant="secondary" onClick={loadSessions} disabled={loading}>`
- `security/page.tsx:183` — same pattern for the MFA button
- `forgot-password/page.tsx:83` — this is a `<Link className="secondary-btn" href={resetUrl}>` — keep as Link but change className: `className="inline-flex items-center justify-center font-bold rounded-lg h-[38px] px-[14px] text-sm bg-surface text-ink border border-border hover:bg-surface-2 transition-colors duration-100 whitespace-nowrap"` (secondary button styles without component since Link can't use Button directly — or use Button with asChild pattern if available, otherwise inline classes)
  Actually: check if Button has asChild prop. If not, use a wrapper approach: `<Button variant="secondary" asChild><Link href={resetUrl}>Continuar</Link></Button>` — but Button doesn't have asChild. Best approach: just apply the className string.
- `verify-email/page.tsx:53` — `<Link className="login-btn" href="/">` → apply primary button classes inline: `className="inline-flex items-center justify-center font-bold rounded-lg h-[38px] px-[14px] text-sm bg-amber text-ink border border-amber hover:bg-amber-dark hover:border-amber-dark transition-colors duration-100 whitespace-nowrap"`
- `verify-email/page.tsx:61` — `<Link className="secondary-btn" href="/login">` → apply secondary classes inline

Each file that uses Button needs: `import { Button } from '@/app/components/ui/Button'` at top (add only if not already imported).

**1c — Raw .badge → StatusBadge**

`viagens/page.tsx:102,105`:
- Read the file to understand what statusMeta and billingMeta are (likely objects with .tone and .label from a local mapping).
- The trip table has: `<span className={`badge ${statusMeta.tone}`}>{statusMeta.label}</span>`
- Since these are mapped from trip.status to display info, use: `<StatusBadge status={t.status} />` for the trip status badge (trip.status IS a StatusKey like 'em-rota', 'concluida', etc.)
- For the billing status badge: `<StatusBadge status={t.billing_status ?? 'not_billable'} />` (billing_status is 'billed', 'billable', etc.)
- Add import: `import { StatusBadge } from '@/app/components/ui/StatusBadge'`
- Remove the statusMeta/billingMeta helper objects if they were only used for badge rendering

`MaintenanceImminentPanel.tsx:42,67,73`:
- Line 42: `<span className="badge red" style={{ marginLeft: "auto" }}>{alerts.length}</span>` → `<StatusBadge status="error" label={String(alerts.length)} className="ml-auto" />`
- Line 67: `<span className="badge red">Vencida</span>` → `<StatusBadge status="expired" />`
- Line 73: `<span className="badge" style={{ fontSize: 11 }}>{TRIGGER_LABEL[alert.trigger_type]}</span>` → `<StatusBadge status="pending" label={TRIGGER_LABEL[alert.trigger_type]} />` (use pending for neutral/info style, or check if there's a better match)
- Add import: `import { StatusBadge } from '@/app/components/ui/StatusBadge'`

`rotas-config/page.tsx:75,79,84,88`:
- `<span className="badge cyan">{money(r.despacho_vazio)}</span>` → `<StatusBadge status="info" label={money(r.despacho_vazio)} />`
- `<span className="badge red">Fora das faixas</span>` → `<StatusBadge status="error" label="Fora das faixas" />`
- Same pattern for lines 84, 88
- Add import: `import { StatusBadge } from '@/app/components/ui/StatusBadge'`
  </action>
  <verify>
    <automated>grep -rn "\.secondary-btn\|\.badge " apps/manager/app --include="*.tsx" | grep -v "globals.css" | grep -v "StatusBadge" | wc -l</automated>
    <automated>grep -n "style.*#d97706\|style.*#f59e0b" apps/manager/app/cobranca/IssueDocumentButton.tsx | wc -l</automated>
  </verify>
  <done>Zero .secondary-btn in TSX; zero raw .badge class; IssueDocumentButton has no hex inline style</done>
</task>

<task type="auto">
  <name>Task 2: Create Input component + migrate off-token inputs</name>
  <files>
    apps/manager/app/components/ui/Input.tsx
    apps/manager/app/components/PaymentModal.tsx
    apps/manager/app/components/FleetComplianceBoard.tsx
    apps/manager/app/ar/page.tsx
  </files>
  <action>
**2a — Create apps/manager/app/components/ui/Input.tsx**

```tsx
'use client'

import { cn } from '@/lib/utils'
import { forwardRef, type InputHTMLAttributes } from 'react'

export type InputVariant = 'default' | 'mono'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  variant?: InputVariant
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ variant = 'default', className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          'w-full h-10 px-3 bg-surface border border-border rounded-md text-sm text-ink',
          'placeholder:text-placeholder',
          'focus:outline-none focus:ring-2 focus:ring-amber/20 focus:border-amber',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'transition-colors duration-100',
          variant === 'mono' && 'font-mono tabular-nums',
          className,
        )}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'

export default Input
```

**2b — Migrate PaymentModal.tsx inputs**

In PaymentModal.tsx, add `import { Input } from '@/app/components/ui/Input'` and replace ALL `<input>` elements that have `border-gray-200` / `bg-white` in their className with `<Input>` (keeping the same name/type/value/onChange/placeholder props).

For the amount input (has `font-mono`): use `<Input variant="mono" ...>`
For other inputs: use `<Input ...>`

Also fix:
- Modal wrapper: `<div className="bg-white rounded-xl shadow-2xl p-6 ...">` → `<div className="bg-surface rounded-xl shadow-design-md p-6 ...">`
- Modal title: `text-gray-900` → `text-ink`
- All `<label>` with `text-gray-500` → `text-ink-2`
- All `<span className="font-normal normal-case text-gray-400">` → `text-placeholder`
- Cancel button: `border-gray-200 text-gray-700 hover:bg-gray-50` → use `<Button variant="secondary">Cancelar</Button>` (add Button import)
- Confirm/submit button if it has hardcoded styles: check and fix

**2c — FleetComplianceBoard.tsx filter inputs**

Find inputs with `bg-white` and replace className to use `bg-surface border-border text-ink` pattern, or wrap with `<Input>` if they're simple text/date inputs.

**2d — ar/page.tsx filter input**

Line 178: `className="px-3 py-1.5 text-sm border border-[var(--border)] rounded-md bg-white text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--amber)]"` → use `<Input className="py-1.5 text-sm h-auto" ...>` or just replace className with token classes: `className="px-3 py-1.5 text-sm border border-border rounded-md bg-surface text-ink focus:outline-none focus:ring-2 focus:ring-amber/20 focus:border-amber"`
  </action>
  <verify>
    <automated>grep -n "border-gray\|bg-white\|text-gray" apps/manager/app/components/PaymentModal.tsx | wc -l</automated>
  </verify>
  <done>Input.tsx exists; PaymentModal has zero gray/white Tailwind classes; FleetComplianceBoard and ar/page inputs use token classes</done>
</task>

<task type="auto">
  <name>Task 3: Create IconButton component + migrate all .icon-btn usages</name>
  <files>
    apps/manager/app/components/ui/IconButton.tsx
    apps/manager/app/components/ClientFormModal.tsx
    apps/manager/app/components/ContractFormModal.tsx
    apps/manager/app/components/DriverFormModal.tsx
    apps/manager/app/components/KnownRouteFormModal.tsx
    apps/manager/app/components/KnownRouteDeleteButton.tsx
    apps/manager/app/components/TripFormModal.tsx
    apps/manager/app/components/PairingCodeButton.tsx
    apps/manager/app/clientes/ClientsTable.tsx
    apps/manager/app/viaturas/page.tsx
  </files>
  <action>
**3a — Create apps/manager/app/components/ui/IconButton.tsx**

```tsx
'use client'

import { cn } from '@/lib/utils'
import type { ButtonHTMLAttributes } from 'react'

export type IconButtonVariant = 'default' | 'danger'
export type IconButtonSize = 'sm' | 'md'

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: IconButtonVariant
  size?: IconButtonSize
  label?: string  // accessible aria-label
}

const variantClasses: Record<IconButtonVariant, string> = {
  default: 'bg-surface text-ink-2 border border-border hover:bg-surface-2 hover:text-ink',
  danger:  'bg-surface text-error border border-error-border hover:bg-error-bg',
}

const sizeClasses: Record<IconButtonSize, string> = {
  sm: 'h-7 w-7',
  md: 'h-8 w-8',
}

export function IconButton({
  variant = 'default',
  size = 'md',
  label,
  className,
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      {...props}
      aria-label={label}
      className={cn(
        'inline-flex items-center justify-center rounded-md flex-shrink-0',
        'transition-colors duration-100 cursor-pointer',
        'disabled:opacity-60 disabled:cursor-not-allowed',
        variantClasses[variant],
        sizeClasses[size],
        className,
      )}
    >
      {children}
    </button>
  )
}
```

Note: `error-border` needs to exist in tailwind config. Check tailwind.config.ts — if `error: { border: 'var(--error-border)' }` is defined, use `border-error-border`. Otherwise use `border-error`.

**3b — Migrate .icon-btn usages**

For each file, replace `<button className="icon-btn" ...>` with `<IconButton ...>` and add import `import { IconButton } from '@/app/components/ui/IconButton'`.

For `.icon-btn.danger`: use `<IconButton variant="danger" ...>`.

**The isEdit ternary pattern** in ContractFormModal, DriverFormModal, VehicleFormModal, KnownRouteFormModal:
```tsx
// Before:
<button className={isEdit ? "icon-btn" : "primary-btn"} onClick={handleOpen}>
// After:
{isEdit
  ? <IconButton onClick={handleOpen} label="Editar"><PencilIcon size={16} /></IconButton>
  : <Button onClick={handleOpen}>...</Button>
}
```
Read each file to understand the trigger button's icon and label before converting.

Files to migrate:
- `ClientFormModal.tsx:165` — close dialog icon-btn → IconButton
- `ContractFormModal.tsx:84` — isEdit ternary trigger; line 93 — close icon-btn
- `DriverFormModal.tsx:54` — isEdit ternary trigger; line 63 — close icon-btn
- `KnownRouteFormModal.tsx:48` — isEdit ternary trigger; line 56 — close icon-btn
- `KnownRouteDeleteButton.tsx:24` — `<button className="icon-btn danger" ...>` → `<IconButton variant="danger" ...>`
- `TripFormModal.tsx:146` — close icon-btn
- `PairingCodeButton.tsx:49` — open icon-btn; line 60 — close icon-btn; line 70 — copy icon-btn
- `ClientsTable.tsx:133` — edit icon-btn in table row
- `viaturas/page.tsx:118` — icon-btn in viaturas table
- Check VehicleFormModal.tsx:54,63 — isEdit ternary + close
  </action>
  <verify>
    <automated>grep -rn "icon-btn" apps/manager/app --include="*.tsx" | grep -v "globals.css" | wc -l</automated>
  </verify>
  <done>Zero .icon-btn in TSX files; IconButton.tsx component exists and is importable</done>
</task>

<task type="auto">
  <name>Task 4: PaymentModal full token migration</name>
  <files>
    apps/manager/app/components/PaymentModal.tsx
  </files>
  <action>
Read PaymentModal.tsx fully. Migrate any remaining non-token classes after Task 2 migration:

Systematic replacements:
- `bg-white` → `bg-surface`
- `border-gray-200` → `border-border`
- `text-gray-900` → `text-ink`
- `text-gray-700` → `text-ink`
- `text-gray-500` → `text-ink-2`
- `text-gray-400` → `text-placeholder`
- `hover:bg-gray-50` → `hover:bg-surface-2`
- `shadow-2xl` → `shadow-design-md` (or `shadow-lg` if design-md not available — check tailwind.config.ts)
- `rounded-xl` → `rounded-lg` (matches --r-md token via tailwind config)

Any `focus:ring-amber-500` → `focus:ring-amber` (token-based)
Any `focus:border-amber-500` → `focus:border-amber`

If Task 2 already handled all of PaymentModal, verify and skip (task is idempotent — re-reading the file confirms zero gray/white classes).
  </action>
  <verify>
    <automated>grep -c "gray\|bg-white" apps/manager/app/components/PaymentModal.tsx || echo "0"</automated>
  </verify>
  <done>PaymentModal has zero Tailwind gray-* or bg-white classes — all on design tokens</done>
</task>

<task type="auto">
  <name>Task 5: PageHeader in missing app pages</name>
  <files>
    apps/manager/app/viagens/page.tsx
    apps/manager/app/motoristas/page.tsx
    apps/manager/app/motoristas/[id]/page.tsx
    apps/manager/app/contratos/page.tsx
    apps/manager/app/viaturas/page.tsx
    apps/manager/app/viaturas/[id]/page.tsx
    apps/manager/app/terceiros/page.tsx
    apps/manager/app/terceiros/[id]/page.tsx
    apps/manager/app/analytics/page.tsx
    apps/manager/app/rotas-config/page.tsx
    apps/manager/app/settings/SettingsClient.tsx
  </files>
  <action>
For each page:
1. Read the file to understand its current header structure (usually a `<h1>` or `<div>` with a title)
2. Add `import { PageHeader } from '@/app/components/ui/PageHeader'`
3. Replace the ad-hoc header section with `<PageHeader title="..." description="..." eyebrow="..." actions={...} />`

Page titles to use (infer from context if different):
- `viagens/page.tsx` → title="Viagens" eyebrow="Operações"
- `motoristas/page.tsx` → title="Motoristas" eyebrow="Frota"
- `motoristas/[id]/page.tsx` → title={driver.name} eyebrow="Motoristas" (use dynamic title)
- `contratos/page.tsx` → title="Contratos" eyebrow="Financeiro"
- `viaturas/page.tsx` → title="Viaturas" eyebrow="Frota"
- `viaturas/[id]/page.tsx` → title={vehicle.plate} eyebrow="Viaturas"
- `terceiros/page.tsx` → title="Terceiros" eyebrow="Frota"
- `terceiros/[id]/page.tsx` → dynamic title from data
- `analytics/page.tsx` → title="Analytics" eyebrow="Financeiro"
- `rotas-config/page.tsx` → title="Configuração de Rotas" eyebrow="Config"

For action buttons: if the page has a "Novo X" button or filter controls at the header level, pass them as `actions` prop to PageHeader.

Auth pages (login, register, forgot-password, reset-password, verify-email) — DO NOT add PageHeader, they have their own card layout.

`settings/SettingsClient.tsx` — read it; if it has its own h1/header, wrap with PageHeader pattern.
  </action>
  <verify>
    <automated>grep -rL "PageHeader" apps/manager/app/viagens/page.tsx apps/manager/app/motoristas/page.tsx apps/manager/app/contratos/page.tsx apps/manager/app/viaturas/page.tsx apps/manager/app/terceiros/page.tsx apps/manager/app/analytics/page.tsx apps/manager/app/rotas-config/page.tsx 2>/dev/null | wc -l</automated>
  </verify>
  <done>All 7 app pages now import and use PageHeader; zero custom h1 header patterns in those files</done>
</task>

<task type="auto">
  <name>Task 6: Mop-up — font-mono on monetary values + focus ring normalization</name>
  <files>
    apps/manager/app/rotas-config/page.tsx
    apps/manager/app/contratos/page.tsx
    apps/manager/app/ar/page.tsx
  </files>
  <action>
**6a — rotas-config/page.tsx font-mono**

Lines 77 and 86 have `<span className="muted-line">{money(tier.amount)} (faixa)</span>`.
The monetary value is rendered without font-mono. Wrap the money value in a `<span className="font-mono tabular-nums">`:
```tsx
<span className="muted-line">
  <span className="font-mono tabular-nums">{money(tier.amount)}</span> (faixa)
</span>
```

**6b — contratos/page.tsx monetary value**

Line 73: `<td>{formatMoney(c.default_unit_price, c.currency)}</td>` — wrap value in `<span className="font-mono tabular-nums">`.

**6c — Focus ring normalization**

Search any remaining `focus:ring-1` in TSX files (should be `focus:ring-2`). Fix any found.
Search for `focus:ring-amber-500` → `focus:ring-amber` (uses token).

Run: `grep -rn "focus:ring-1\|focus:ring-amber-500\|focus:border-amber-500" apps/manager/app --include="*.tsx"` and fix each.
  </action>
  <verify>
    <automated>grep -rn "focus:ring-1\|focus:ring-amber-500" apps/manager/app --include="*.tsx" | wc -l</automated>
    <automated>grep -rn "font-mono" apps/manager/app/rotas-config/page.tsx | wc -l</automated>
  </verify>
  <done>Zero focus:ring-1 or focus:ring-amber-500 in TSX; rotas-config monetary values have font-mono</done>
</task>

</tasks>

<verification>
After all 6 tasks:
1. `grep -rn "icon-btn\|secondary-btn\|\.badge " apps/manager/app --include="*.tsx" | grep -v StatusBadge | wc -l` → 0
2. `grep -rn "style.*#[0-9a-fA-F]" apps/manager/app --include="*.tsx" | wc -l` → 0
3. `grep -rn "border-gray\|bg-white\|text-gray-[0-9]" apps/manager/app --include="*.tsx" | wc -l` → 0
4. Input.tsx and IconButton.tsx exist in apps/manager/app/components/ui/
5. `cd apps/manager && npx tsc --noEmit 2>&1 | grep -c "error TS"` → 0
</verification>

<success_criteria>
- IssueDocumentButton: no hex inline style
- All .secondary-btn replaced with Button variant="secondary"
- All raw .badge replaced with StatusBadge
- All .icon-btn replaced with IconButton
- Input component created, used in PaymentModal + FleetComplianceBoard + ar/page
- IconButton component created with default + danger variants
- PaymentModal 100% on design tokens
- PageHeader used in viagens, motoristas, contratos, viaturas, terceiros, analytics, rotas-config
- font-mono on monetary values in rotas-config + contratos
- Zero focus:ring-1 remaining
- TypeScript: zero new errors
</success_criteria>

<output>
After completion, create `.planning/quick/260620-vlw-design-system-migration-wave-1-quick-win/260620-vlw-SUMMARY.md` with what was implemented, components created, files migrated, and any deviations.
</output>
