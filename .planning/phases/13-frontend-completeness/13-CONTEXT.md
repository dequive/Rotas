# Phase 13 — Frontend Completeness

## Phase Goal

A manager who clicks any sidebar entry reaches a functional page — no blank screens,
placeholder "Em breve" sections, or unwired action buttons. Four areas require real
implementation: `/alertas`, `/settings`, `/cobranca` (action wiring), and a TypeScript
clean-pass verification.

## Current State (read before planning)

### Sidebar (`SidebarLayout.tsx`)
All sidebar entries already exist: Alertas, Definições, Manutenção, Cobrança, Terceiros,
etc. No missing entries. No sidebar changes needed.

### `/manutencao`
COMPLETE. Full 4-tab page: Work Orders, Peças, Ferramentas, Planos Preventivos.
KPIs, DataTable, WorkOrderFormModal. No action required.

### `/alertas` — PARTIAL (has gaps)
- `page.tsx` + `AlertsClient.tsx` exist with two tabs: "Documentos a Expirar" / "Alertas de
  Sistema".
- The alert backend has `status` field: `pending | read | dismissed | resolved`.
- The backend endpoint is `PATCH /alerts/{id}/status` (not `/acknowledge`).
- `actions.ts` only has `resolveAlert` (sets status=resolved). Missing: acknowledge action
  (sets status=read).
- Tab structure is "documentos/sistema" — needs to add a "reconhecidos" filter view within
  the sistema tab showing read/dismissed alerts separately from active (pending) ones.
- No react-query polling — page uses SSR Server Component data only. Re-fetch on action
  uses `router.refresh()`. This is acceptable; full polling would require full client
  component data fetching which requires a proxy route.

### `/settings` — PARTIAL (has stubs)
- `page.tsx` + `SettingsClient.tsx` exist with tabs: Perfil, Gestão de Acessos,
  Preferências.
- "Perfil" tab: works — user profile update (name, email, phone).
- "Acessos" tab: stub ("Em breve" placeholder). Must implement: user list, invite form
  (POST /api/v1/users), role change (PATCH /api/v1/users/{id}).
- "Preferências" tab: stub ("Em breve" placeholder). Must implement: tenant PATCH form
  (timezone, currency, whatsapp_number from TenantPatch schema) + driver devices list.
- Note: `TenantPatch` backend schema supports `timezone | currency | whatsapp_number |
  compliance_policy` — NOT name/nuit (those fields don't exist on the model). Implement
  what the backend supports.

### `/cobranca` — PARTIAL (action buttons unwired)
- Full page exists: billing trips work queue, billing documents list, KPIs, status badges.
- "Gerar Fatura" button is rendered but has no onClick handler.
- PDF export button (FileText icon) is rendered but has no onClick handler.
- Backend: `POST /api/v1/billing/documents/{id}/issue` accepts `{ issued_at?: datetime }`.
- The "issue" action applies to a billing document (from the documents list at the bottom),
  not the trips table. The button at the top creates a new document — different from issue.
- `IssueBillingDocumentRequest`: `{ issued_at: datetime | None }` — all optional.

## Backend API Contracts

### Alerts
- `GET /api/v1/alerts?status=pending|read|dismissed|resolved` — list alerts
- `PATCH /api/v1/alerts/{id}/status` body: `{ "status": "read" | "resolved" | "dismissed" }`
- Requires FLEET_WRITE for PATCH, FLEET_READ for GET

### Users (ADMIN_USERS permission required)
- `GET /api/v1/users?limit=50` — list users: `[{ id, email, full_name, phone, role }]`
- `POST /api/v1/users` body: `{ email, full_name, role, phone? }` — invite user
- `PATCH /api/v1/users/{id}` body: `{ full_name?, email?, phone?, role? }`

### Tenants
- `PATCH /api/v1/tenants/me` body: `{ timezone?, currency?, whatsapp_number?,
  compliance_policy? }`
- `GET /api/v1/tenants/me` — returns `{ id, name, slug, plan, is_active, timezone,
  currency, created_at }`

### Drivers (for device list)
- `GET /api/v1/drivers?limit=50` — list drivers: `[{ id, full_name, phone, status, ... }]`
- No `/driver_devices` endpoint exists. Driver list shows paired status via `status` field.
  The devices tab will show drivers with their status and pairing code generation button.

### Billing Document Issue
- `POST /api/v1/billing/documents/{id}/issue` body: `{}` (issued_at is optional, omit for
  now = server uses current timestamp)

## Design Constraints

From DESIGN.md (enforced throughout):
- Fonts: Manrope (UI/body) + IBM Plex Mono (data/IDs)
- Accent: amber-500 (`--amber: #f59e0b`)
- Badges: always with colored dot `::before` circle — use StatusBadge component
- Sidebar: already grouped correctly — do not change
- No decorative gradients, blobs, or illustrations
- Error states use `bg-error-bg border-error/30 text-error`
- Success states use `bg-success-bg text-success`

## Existing Components Available

- `SidebarLayout` — wraps every page
- `PageHeader`, `SectionHeader` — page/section headers
- `KpiCard` — metric cards
- `DataTable`, `RotasTableHeader`, `RotasTableRow`, `RotasTableCell` — table system
- `StatusBadge` — colored dot badge
- `MonoCell`, `MoneyCell` — IBM Plex Mono cells
- `EmptyState` — empty list state
- `WorkQueue` — Kanban-style work queue card
- `apiFetch` (lib/api.ts) — authenticated fetch for Server Components
- `requireSession` (lib/auth.ts) — session guard

## Wave Structure

| Wave | Plans | Dependency |
|------|-------|------------|
| 1 | 13-01 (/alertas gaps), 13-02 (/settings stubs) | Independent |
| 2 | 13-03 (/cobranca action wiring) | Independent of wave 1 |
| 3 | 13-04 (tsc check + smoke verification) | After all code changes |

Wave 1 plans can run in parallel (different files, no overlap).
Wave 2 is independent of wave 1 but runs after for sequencing simplicity.
