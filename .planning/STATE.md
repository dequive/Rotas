---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: TMS Enterprise Completo
status: in_progress
stopped_at: Completed 16-02-SUMMARY.md
last_updated: "2026-06-21T00:00:00.000Z"
last_activity: 2026-06-21
progress:
  total_phases: 13
  completed_phases: 9
  total_plans: 69
  completed_plans: 69
---

# ROTAS — Project State

_Last updated: 2026-06-21 — Phase 16 (HOS + Availability) complete: 16-01 router registration, 16-02 HOS service + trip gate (8 tests GREEN, 434 total passing), 16-03/04/05 availability endpoints. All 5 plans have SUMMARYs._

---

## Current Phase

Phase: 16
Plan: 16-05 complete — ALL PLANS DONE
Status: Phase 16 complete — all 5 plans done (16-01 router; 16-02 HOS service; 16-03 availability endpoints + Redis; 16-04 status filter; 16-05 HOS integration test)
Last activity: 2026-06-22 — Phase 26 planned: 3 plans (gt01 DDL, gt02 backfill, gt03 find-or-create), plan checker passed (1 warning fixed)
Stopped at: Completed 16-02-SUMMARY.md

### Completed v2.0 Phases

- [x] **Phase 5** — Client Registry + Migration Foundation (6 plans, VERIFICATION.md present)
- [x] **Phase 6** — Payment Registration (4 plans, all SUMMARYs present)
- [x] **Phase 7** — Accounts Receivable + Aging Dashboard (5 plans, 6 AR tests GREEN, /ar UI live)
- [x] **Phase 8** — Infrastructure Hardening (8 plans + VERIFICATION.md; Sentry, R2, tenant limits)
- [x] **Phase 9** — PostgreSQL RLS Policies (completed 2026-06-07)

### Completed v3.0 Phases

- [x] **Phase 23** — Third Party Registry (TP-01..TP-11: third_parties, roles, profiles, mz_provinces, nullable FKs, eligibility service, assignments, operational_documents, expiry alerts, party directory UNION ALL) — 29 tests passed, 11/11 PASS
- [x] **Phase 14** — Domain State Machines (SM-01 BillingDocument, SM-02 Contract, SM-03 DeliveryProof, SM-04 DispatchClearance)
- [x] **Phase 15.1** — Documentos Fiscais Completos (FDOC-01..05: Nota de Débito, Nota de Crédito, Fatura-Recibo, Recibo, AR aging; OPDOC-01..05: extra_fields DDL, Guia de Remessa PDF, CPI bilingual PDF, DAV digital record, checklist por tipo de viagem) — 238 passed, 3 skipped
- [x] **Phase 17** — Infrastructure Enterprise v2 (INFRA2-01 distributed rate limiting, INFRA2-02 structured logging, INFRA2-03 Prometheus metrics, INFRA2-04 deep health check + worker heartbeat)
- [x] **Phase 24** — Third Party Completion (24-01 tp07/08/09 migrations; 24-02 contacts/ledger/payments/evaluations API; 24-03 /terceiros UI; 24-04 ThirdPartyCombobox/ServiceProviderCombobox pickers; 24-05 OperationalDocuments + assignments UI; 24-06 alembic head + seed + 348 tests green + tsc clean) — completed 2026-06-20
- [x] **Phase 18** — Analytics + Insurance (18-01..04: all plans complete, SUMMARYs present) — completed
- [x] **Phase 21** — Frontend E2E Tests (21-01 Playwright scaffold; 21-02 5 spec files + CI e2e job; 10 tests passing) — completed 2026-06-21
- [x] **Phase 16** — HOS + Availability (16-01 router registration; 16-02 HOS service + trip gate 8h/9h/48h thresholds + hos_override_reason bypass; 16-03 availability endpoints + Redis cache; 16-04 status filter; 16-05 integration; 434 tests GREEN) — completed 2026-06-21

---

## Execution Order Advisory

### v2.0 (em curso) — Concluir primeiro

```
Phase 8 (INFRA)         — start immediately (Sentry, R2, tenant limits)
Phase 5 (CLI)           — requires Phase 9 RLS ✅ complete
Phase 6 (PAY)           — requires Phase 5 + zero NULL client_id gate
Phase 7 (AR)            — requires Phase 6
Phase 10 (NOTIF+ONBRD)  — requires Phase 8 + WhatsApp templates approved
Phase 11 (DESP)         — requires Phase 10
Phase 12 (GPS+TRK)      — requires Phase 9 ✅ + GPS device survey
Phase 04.1 (UI)         — ✅ complete (04.1-08 done: .topbar, .toolbar, .queue-list, .queue-item removed; build clean)
Phase 2 (PWA)           — 02-07 ✅ done; 02-08 field test pending
Phase 4 (RLS plan)      — 1 plan remaining (04-08 RLS)
```

### v3.0 — Execution Order

```
Phase 17 (INFRA2)       — no dependencies; run in parallel with Phase 13
Phase 13 (Frontend)     — requires Phase 8 + 04.1 complete
Phase 14 (State Machines) — no new dependencies; can run in parallel with Phase 13
Phase 15 (Fiscal+Load)  — requires Phase 14 (SM-01 DeliveryProof)
Phase 16 (HOS+Avail)    — requires Phase 14 (work order SM)
Phase 18 (Analytics+Ins) — requires Phases 13 + 14 + 15
Phase 19 (Customs/Border) — new; requires Phase 14
Phase 20 (Route Optim)   — new; requires GPS/Maps integration
Phase 21 (Frontend E2E)  — new; E2E tests for stability
Phase 24 (Third Party Completion) — plans written 2026-06-20; ready to execute
```

---

## Accumulated Context (v2.0)

### Roadmap Evolution

- Phase 4.1 inserted after Phase 4: UI Design System and Component Library (URGENT — foundational for all v2.0 UI work)
- Phase 22 added (2026-06-18): RBAC Permission-Based — refactor dos dois planos (platform vs tenant), roles em português com agregados gestao/operacional/finance, `require_permission()` granular, `tenant_roles` custom, migração dos 174 call sites de `require_roles`

### Key Decisions

| Decision | Phase | Rationale |
|----------|-------|-----------|
| SidebarLayout hover via inline style handlers not Tailwind hover: — CSS variable values cannot be Tailwind class arguments | 4.1 | Tailwind hover: works for static values only; var(--sidebar-hover) requires onMouseEnter/onMouseLeave |
| border-l-2 border-transparent on inactive sidebar items prevents layout shift when active item changes | 4.1 | Without the transparent border, active item's border-l-2 pushes content 2px — visible shift |
| muted Tailwind token → var(--muted-color) not var(--muted) | 4.1 | Prevents HSL token (#213 27% 96% background surface) from being used as text color |
| TransportCargoBoard: table KPI rows replaced with KpiCard grid | 4.1-06 | Cards are more scannable; consistent with other board sections; removes shadcn Table dependency from this component |
| CostMarginBoard margin KPI: semantic=error for negative, semantic=success for positive | 4.1-06 | IBM Plex Mono in red/green makes financial health instantly visible without reading the number |
| DataSourceBadge in PageHeader actions slot (not below header) | 4.1-06 | Reduces vertical whitespace; keeps data freshness indicator close to section title |
| Legacy CSS classes stay outside @layer base | 4.1 | .shell, .sidebar etc. are regular CSS rules; wrapping in layer would break cascade order |
| Colored dot is a span element not ::before — React JSX cannot express pseudo-elements | 4.1 | DESIGN.md says "dot colorido" but ::before is not valid in React JSX; inline span achieves same visual |
| WorkQueue toneConfig static lookup prevents Tailwind class purging in production builds | 4.1 | Dynamic `border-l-${tone}` would be purged by Tailwind scanner; all classes must appear as full strings |
| SEC-05 (python-jose → PyJWT) first in Phase 1 | 1 | Active CVE — auth bypass active before any external user |
| Cross-tenant regression tests before CT-01 | 1 → 3 | CT-01 query rewrite is highest-risk window for cross-tenant data leaks |
| ARQ for background jobs (PDF, XLSX, KPI refresh) | 3 | Uses Redis already provisioned; asyncio-native; avoids blocking HTTP responses |
| SW served with Cache-Control: no-store | 2 | Broken cached SW is unrecoverable on low-cost Android — cannot be fixed server-side |
| Field testing on real Android hardware required to close Phase 2 | 2 | Background Sync API compatibility must be confirmed on target hardware |
| DeliveryProof patchable fields use actual model names (notes, receiver_name, receiver_contact) | 2 | Plan spec listed wrong field names; real model checked and corrected |
| _dispatch_update wraps patch calls in try/except for per-item error isolation | 2 | Batch HTTP stays 200; ApiError converts to failed result per item |
| registerType: prompt not autoUpdate in VitePWA config | 2 | autoUpdate calls skipWaiting unconditionally — would reload app mid-trip while driver records delivery proof |
| BackgroundSyncPlugin handles fetch exceptions only; Dexie handles HTTP errors | 2 | BackgroundSync only retries on network failure; 4xx/5xx need Dexie-level retry |
| Icons generated with Pillow + Windows Arial Bold (proper 192x192/512x512) | 2 | Proper dimensions required — Chrome installability checker rejects icons smaller than declared size |
| manifest.webmanifest in public/ is static fallback; live manifest from vite.config.mjs manifest block | 2 | VitePWA injectManifest strategy generates injected manifest from config, not public/ file |
| require_roles(*DASHBOARD_ROLES) for scorecard endpoint — driver tokens rejected at dependency level | 4 | Consistent with all other protected endpoints; no manual scope check needed |
| fpdf2+DejaVuSans for billing PDF — full Latin Extended Unicode, font path via Path(__file__) | 3 | latin-1 hand-rolled builder silently corrupted Mozambican diacritics; fpdf2 TTF font path is CWD-independent |
| openpyxl for XLSX — native bold/number_format, no hand-rolled XML/ZIP | 3 | openpyxl is the standard Python XLSX library; proper cell formatting without raw XML |
| Idempotent export job creation — returns existing queued/processing job on duplicate request | 3 | Prevents duplicate ARQ jobs for same document+format; safe for retry from frontend |
| Four Alembic migrations for client migration — DDL and DML never in same file | 5 | Established pattern in this codebase (28 existing migrations); DDL+DML mixing causes transaction issues on some PG versions |
| clients migration uses revision a2b3c4d5e6f7 (not plan-specified a1b2c3d4e5f6 which was already taken) | 5-01 | a1b2c3d4e5f6 assigned to add_waiver_status_pending_approval; merge migration 22fbf8416463 resolves dual-head conflict with a8f3b2c1d4e5 workshop expansion |
| _get_outstanding_balance returns Decimal('0.00') in Plan 01 — client_id FK on billing_documents not yet added | 5-01 | Plan 02 migration (b) adds FK; outstanding_balance_estimate flag signals interim state to API consumers |
| Plan 02 migration revision IDs: e5f6a7b8c9d0 (b), f6a7b8c9d0e1 (c), a7b8c9d0e1f2 (d) | 5-02 | Plan-specified b2c3d4e5f6a7 and d4e5f6a7b8c9 were taken by existing migrations; down_revision = 22fbf8416463 (merge head, not plan-specified a1b2c3d4e5f6) |
| outstanding_balance_estimate flag removed in Plan 02 — _get_outstanding_balance now queries BillingDocument.client_id | 5-02 | FK live after migration e5f6a7b8c9d0; real sum(total_amount WHERE status='issued') query active |
| Radix Popover + native input for ClientCombobox — cmdk not installed in manager app | 5-04 | cmdk/Command not in package.json; native implementation satisfies all UI-SPEC combobox behavior requirements |
| GET /api/clients proxy route added to Next.js app — client components cannot read httpOnly cookies | 5-04 | httpOnly cookies require server-side access; Next.js route handler reads cookies and forwards auth headers to backend |
| RLS policy created in the CREATE TABLE migration — not a follow-up patch | 5, 8-12 | PITFALL-06: new tables not covered by existing RLS migration; must be explicit per table |
| due_date added in Phase 5 migration (b) alongside client_id — not in Phase 7 | 5 | PITFALL-04: aging needs stored due_date from day one; adding later requires second backfill of all issued documents |
| payment_allocations junction table created in Phase 6 — not deferred to Phase 7 | 6 | PITFALL-05: retrofitting allocation table after payment rows exist is high-risk schema migration |
| client_payments.billing_document_id is nullable — allocations live in junction table | 6 | Supports advance payments and multi-invoice allocation; direct FK would permanently block these flows |
| Payments voided via status field — never hard-deleted | 6 | Financial records must have immutable audit trail; hard delete corrupts AR history |
| Aging uses billing_documents.due_date (stored) not issued_at + payment_terms_days (derived) | 7 | due_date is authoritative; derived calculation drifts when payment_terms change post-issue |
| AR aging endpoint requires explicit as_of date parameter | 7 | Makes aging testable without time mocking; allows retrospective report generation |
| aiobotocore[boto3] replaces boto3 — never keep both | 8 | Conflict at botocore layer; aiobotocore is async-safe for upload/download operations |
| R2 migration script runs before enabling storage_provider=R2 switch | 8 | PITFALL-14: Railway ephemeral disk wipes on deploy; existing files lost permanently if switch enabled before migration |
| Tenant limit guards added to all create_* service functions | 8 | PITFALL-19: limits must be enforced before onboarding opens public registration |
| SET LOCAL app.tenant_id not SET — verified in after_begin event listener | 9 | PITFALL-01: SET persists on pooled connections; next request executes under wrong tenant silently |
| Three separate DB URLs: DATABASE_URL / ALEMBIC_DATABASE_URL / ADMIN_DATABASE_URL | 9 | PITFALL-02: Alembic blocked by RLS if it uses rotas_app role; ARQ worker needs BYPASSRLS for cross-tenant jobs |
| WhatsApp templates submitted to Meta during Phase 9 execution | 9 → 10 | Meta approval 1-3 days per template + 5-14 day business verification; templates must be approved before Phase 10 closes |
| dispatch_notification() checks whatsapp_opt_in_confirmed before enqueuing WhatsApp task | 10 | PITFALL-10: Meta suspends accounts for sending to unconfirmed numbers; recovery takes weeks |
| Onboarding uses atomic tenant+owner transaction; IntegrityError → slug_already_taken 409 | 10 | PITFALL-11: partial registration leaves orphaned inactive tenant |
| compute_settlement() reads trip_costs WHERE paid_by=driver — never a parallel expense ledger | 11 | PITFALL-03: parallel ledger double-counts same expenses |
| Settlement draft re-reads costs at finalization — optimistic lock on costs_reconciled_at | 11 | PITFALL-04: costs changed after draft creation would produce incorrect balance |
| GPS HMAC validation before tenant_id resolution | 12 | PITFALL-08: attacker who knows IMEI cannot inject positions without device_secret |
| vehicle_last_position upsert table as fast read path — never query gps_positions for live display | 12 | PITFALL-07: 120,000 rows/day at 50 vehicles; raw event table must never be queried for live fleet map |
| Tracking page target under 50KB — text-format position, no heavy map library | 12 | Low-end Android browsers on shared mobile data in Mozambique outside Maputo/Beira/Nampula |
| supplier_ledger balance = sum(credits) - sum(debits) — never denormalised | 24 | Denormalised balance drifts on concurrent writes; calculated at query time is always correct |
| ThirdPartyCombobox uses native fetch via Next.js /api/third-party proxy — not direct backend URL | 24 | Client Components cannot read httpOnly session cookies; proxy pattern established in Phase 5 for /api/clients |
| tp07 down_revision=b1c2d3e4f5a6 not tp06 — tp06 already merged via tp_merge_wave2 | 24-01 | Using tp06 as down_revision would create a parallel branch head; b1c2d3e4f5a6 is the actual current head, keeping linear chain |

### Architecture: v2.0 Phase Sequence

```
Phase 8 (INFRA): Sentry + R2/S3 dual-provider + tenant limit guards
  New packages: sentry-sdk[fastapi], aiobotocore[boto3] (replaces boto3), @sentry/nextjs, @sentry/vite-plugin
  New backend: storage.py dual-provider, _check_*_limit() guards, /api/v1/tenant/limits endpoint
  New frontend: LimitWarningBanner in layout.tsx

Phase 9 (RLS): 47-table policy migration + role separation + cross-tenant test suite
  ALEMBIC_DATABASE_URL / ADMIN_DATABASE_URL must be configured in Railway before migration runs
  Single Alembic migration: ENABLE RLS + FORCE RLS + CREATE POLICY rls_{table} for all tenant tables
  [Parallel: submit 7 WhatsApp templates to Meta for approval]

Phase 5 (CLI): Client entity + 4-migration sequence + CLI frontend
  Migration (a): CREATE clients + RLS + GRANT
  Migration (b): ADD client_id FK (nullable) to contracts + billing_documents; ADD due_date to billing_documents
  Migration (c): Backfill — SELECT DISTINCT client_name → INSERT clients → UPDATE FKs
  Migration (d): CREATE payments + payment_allocations tables + RLS + GRANT
  Gate: SELECT count(*) FROM contracts WHERE client_id IS NULL = 0
        SELECT count(*) FROM billing_documents WHERE client_id IS NULL = 0

Phase 6 (PAY): Payments (only starts after Phase 5 gate passes)
  POST /api/v1/billing/payments (idempotency-key required)
  payment_allocations for invoice linking
  Advance payment support (no billing_document_id at creation)

Phase 7 (AR): AR dashboard + aging (requires both clients + payments)
  GET /clients/{id}/statement
  GET /clients/{id}/aging?as_of=YYYY-MM-DD
  GET /billing/ar-summary?as_of=YYYY-MM-DD
  Client statement PDF (fpdf2 + DejaVuSans — same as billing PDF)

Phase 10 (NOTIF+ONBRD): Notifications + public registration
  New modules: notifications/, onboarding/
  New packages: aiosmtplib, phonenumbers, itsdangerous, stripe
  POST /api/v1/onboarding/register (atomic, get_session_raw)
  ARQ tasks: task_send_whatsapp, task_send_email with 30s/5min/30min backoff
  Next.js: /register, /register/verify (excluded from auth middleware)

Phase 11 (DESP): Driver financial settlement
  New tables: driver_advances, trip_settlements (in trips module)
  trips/despacho.py: advance state machine + compute_settlement() + approval workflow
  ARQ task: task_generate_settlement_pdf (stores via files module → R2)
  Multi-currency: fx_rate Numeric(10,6) + ZAR conversion at reconciliation time

Phase 12 (GPS+TRK): GPS ingestion + fleet map + customer tracking
  New modules: gps/, tracking/
  New packages: sse-starlette (fleet map SSE upgrade path)
  New tables: gps_positions (monthly partitions), gps_devices, vehicle_last_position, tracking_tokens
  POST /api/v1/gps/webhook/{imei} (HMAC auth, get_session_raw)
  GET /api/v1/gps/vehicles/latest (RLS-scoped manager auth)
  GET /api/v1/public/track/{token} (no auth, 30 req/min rate limit)
  Next.js: /track/[token] Server Component (excluded from auth middleware matcher)
```

### External Blockers — Start Immediately

- **WhatsApp Business API Meta Approval (4-6 weeks)**: Register ROTAS on Meta for Developers, submit business verification, draft 7 templates in Portuguese. Start during Phase 8; submit templates during Phase 9. Blocks Phase 10.
- **GPS Device Operator Survey (2-4 weeks)**: Survey each operator for device model, firmware, who has Teltonika Configurator access. Get IMEI list, coordinate reconfiguration window. Start during Phase 8. Blocks Phase 12.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260607-o5b | Document expiry compliance fix and proactive alerts | 2026-06-07 | f4c04b5 | [260607-o5b](./quick/260607-o5b-document-expiry-compliance-fix-and-proac/) |
| 260618-po2 | Fix Phase 13.5 production issues in manager (8 bugs: auth headers, NEXT_PUBLIC misuse, silent errors, KPI dedup, hardcoded email, stub tabs) | 2026-06-18 | 8b5c000 | [260618-po2](./quick/260618-po2-fix-phase-13-5-production-issues-in-mana/) |
| 260620-cme | Billing module production hardening (IVA 16%, invoice_number no PDF, issuer snapshot, state machine, N+1 fix, 4 novos endpoints, invariantes) | 2026-06-20 | e8467c9 | [260620-cme](./quick/260620-cme-billing-module-production-hardening/) |
| 260620-r9k | Design system overhaul: fix token layer + create reusable components | 2026-06-20 | 07df112 | [260620-r9k](./quick/260620-r9k-design-system-overhaul-fix-token-layer-c/) |
| 260620-sik | tenant_document_profiles + redesenho exporters PDF fatura modelo PHC | 2026-06-21 | 2351845 | [260620-sik](./quick/260620-sik-tenant-document-profiles-redesenho-expor/) |
| 260621-a7e | UI empresa: perfil documento tenant (dados empresa, bancários, numeração) | 2026-06-21 | 502783c | [260621-a7e](./quick/260621-a7e-ui-manager-configura-o-perfil-documento-/) |
| 260620-vlw | Design system wave 1: Input + IconButton + sweep secondary-btn/badge/icon-btn + PaymentModal + PageHeader | 2026-06-21 | e33adc6 | [260620-vlw](./quick/260620-vlw-design-system-migration-wave-1-quick-win/) |
| 260621-ei3 | P0.3 numeração fiscal gap-free: FiscalCounter + SELECT FOR UPDATE, migração fisc01 RLS, reescrita _assign_invoice_number, 5 testes concorrência | 2026-06-21 | 4c20890 | [260621-ei3](./quick/260621-ei3-p0-3-numeracao-fiscal-gap-free-substitui/) |
| 260621-b3f | Redesenho 5 documentos operacionais PHC: Guia Remessa + CPI + Relatório Viagem + Ordem Serviço + Inspecção Viatura | 2026-06-21 | 96b70ed | [260621-b3f](./quick/260621-b3f-documentos-operacionais-redesenho-phc/) |
| 260621-f5i | P0.6 audit log em mutações financeiras + P0.1 pipeline billable BILLABLE_PROOF_STATUSES | 2026-06-21 | 4c521ee | [260621-f5i](.planning/quick/260621-f5i-p0-6-audit-log-em-mutacoes-financeiras-a/) |
| 260621-nuj | P0.5 IVA seam: resolve_iva fail-closed para internacionais + iva_basis audit columns | 2026-06-21 | 2db084a | [260621-nuj](.planning/quick/260621-nuj-p0-5-seam-iva-internacional-extrair-reso/) |
| 260621-p0i | Design system wave 2: ModalDialog + FormField + migração de 7 form modals + eliminação de inline styles em detail pages | 2026-06-21 | ffabe83 | [260621-p0i](./quick/260621-p0i-design-system-wave-2-modal-wrapper-formf/) |
| 260621-pbc | Fix silent photo sync bug (delivery_proof/load_permit dropped), consolidate dual ARQ workers into app.worker, remove duplicate root railway.toml | 2026-06-21 | dd28089 | [260621-pbc](./quick/260621-pbc-fix-photo-sync-and-consolidate-arq-worke/) |
| 260621-ext | Extrato conta corrente fornecedores: filtro período + opening_balance + PDF PHC landscape | 2026-06-21 | 233c7d8 | inline |
| 260621-p2c | Notifications module: router (3 endpoints), 3 ARQ tasks (outbox flush, dispatch rejected, vehicle doc expiry), 6 tests | 2026-06-21 | 31a6c32 | [260621-p2c](./quick/260621-p2c-notifications-module-router-py-registo-e/) |
| 260621-pvf | HOS violation alerts (30-min cron) + driver document expiry alerts (daily cron) + 5 tests | 2026-06-21 | 232355b | [260621-pvf](./quick/260621-pvf-task-check-hos-violations-cron-cada-30-m/) |
| 260621-uvf | Fase 0 auditoria dados clients→third_parties (4 queries BD: volume, NUIT quality, duplicados, sobreposição) | 2026-06-21 | — | [260621-uvf](./quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/) |

### Blockers

_None — v3.0 roadmap criado; nenhum bloqueio activo._

### Todos

**v2.0 — Pendentes antes de iniciar v3.0:**

- [ ] Start WhatsApp Business API Meta approval process immediately (parallel to Phase 8)
- [ ] Start GPS device operator survey immediately (parallel to Phase 8)
- [ ] Configure ALEMBIC_DATABASE_URL and ADMIN_DATABASE_URL in Railway
- [ ] Decide 360dialog vs direct Meta Cloud API before Phase 10 planning
- [ ] Verify Flutterwave Mozambique live availability before Phase 10 planning
- [ ] Run GPS device field survey and obtain Teltonika/Coban JSON payload samples before Phase 12 planning
- [ ] Run pre-migration audit query before writing Phase 5 migration code: `SELECT tenant_id, lower(trim(client_name)), count(*) FROM contracts GROUP BY 1, 2 HAVING count(*) > 1`
- [ ] Confirm PostGIS availability on Railway PostgreSQL before any geofencing design (Phase 12+)
- [x] Confirmed Phase 8 (Sentry/R2/limits) is COMPLETE (08-01 through 08-08 executed)
- [x] Corrigir 278 ruff warnings — FIXED: `ruff check --fix` and `ruff format` executed
- [x] Complete Phase 04.1-08 (legacy CSS cleanup)
- [x] Complete Phase 02-07 (SyncStatusBanner) + [ ] 02-08 (field test)
- [x] Complete Phase 04-08 (RLS plan) — DONE: implemented during Phase 9
- [ ] Verificar requisitos da AT Moçambique para numeração sequencial de faturas (FISC-01)
- [ ] Confirmar se `alerts.acknowledge` endpoint existe no backend ou precisa ser criado (FE-03)
- [ ] Auditar sidebar actual (`SidebarLayout.tsx`) para confirmar quais entradas já existem vs. faltam
- [ ] Verificar se `availability` module tem `router.py` ou apenas `service.py` (AVAIL-01 research)
- [ ] Confirmar versão de `slowapi` instalada e compatibilidade com Redis backend (INFRA2-01)

---

## Session Continuity

_Last session: 2026-06-20 — Phase 24 plans 01-05 complete. 24-05: OperationalDocumentsList + DocumentUploadModal components; Documentos tab live in /terceiros/[id]; new /viaturas/[id] page with Motoristas Atribuidos + Documentos sections; new /motoristas/[id] page with Viaturas Atribuidas + Documentos sections. tsc clean (0 errors). Next: 24-06._

---

## Project Reference

**Core value**: A Mozambican driver can complete an entire trip — departure, refueling, stops, and delivery proof — without connectivity, and all data arrives intact at the manager when signal returns.

**Current milestone**: v3.0 — TMS Enterprise Completo

**Previous milestone**: v2.0 — Plataforma Operacional Completa (in progress, Phases 5-12)

**Stack**: FastAPI 0.115 + Python 3.12 + SQLAlchemy 2.0 async + PostgreSQL 16 / Next.js 14 App Router + React 18 + Tailwind / Vite + Dexie.js 4

**Deploy target**: Vercel (manager) + Railway (backend FastAPI)

**Roadmap**: `.planning/ROADMAP.md`

**Requirements**: `.planning/REQUIREMENTS.md`

**Codebase analysis**: `.planning/codebase/` (7 documents, generated 2026-06-04)

**Research**: `.planning/research/SUMMARY.md` (generated 2026-06-06)

**Audit source**: Auditoria exaustiva realizada em 2026-06-18 (43 migrações, 22 routers, 21 módulos, 2 frontends)
