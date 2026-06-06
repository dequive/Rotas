---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: executing
stopped_at: Completed 04.1-07-PLAN.md
last_updated: "2026-06-06T20:16:05.127Z"
last_activity: 2026-06-06
progress:
  total_phases: 13
  completed_phases: 3
  total_plans: 43
  completed_plans: 41
---

# ROTAS — Project State

_Last updated: 2026-06-06_

---

## Current Phase

Phase: 4.1 — UI Design System and Component Library
Plan: 06 COMPLETE — plans 01-06 complete
Status: In Progress — Plans 01-06 complete (CSS foundation, 5 core primitives, table primitives + MonoCell, grouped sidebar navigation, ControlTowerOverview migration, 4 domain board migrations)
Last activity: 2026-06-06
Stopped at: Completed 04.1-07-PLAN.md

---

## Execution Order Advisory

Phase 5 (CLI) depends on RLS infrastructure. Execute in this order:

```
Phase 8 (INFRA) — no dependencies, start immediately
Phase 9 (RLS)   — no dependencies, start immediately (parallel with 8)
  [During Phase 9: submit 7 WhatsApp templates to Meta for approval]
  [During Phase 8: run GPS device operator survey with fleet clients]
Phase 5 (CLI)   — requires Phase 9 RLS complete
Phase 6 (PAY)   — requires Phase 5 complete + zero NULL client_id gate
Phase 7 (AR)    — requires Phase 6 complete
Phase 10 (NOTIF+ONBRD) — requires Phase 8 complete + WhatsApp templates approved
Phase 11 (DESP) — requires Phase 10 complete
Phase 12 (GPS+TRK) — requires Phase 9 complete + GPS device survey complete
```

---

## Accumulated Context (v2.0)

### Roadmap Evolution

- Phase 4.1 inserted after Phase 4: UI Design System and Component Library (URGENT — foundational for all v2.0 UI work)

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

### Blockers

_None — roadmap expanded, planning not yet started for new phases._

### Todos

- [ ] Start WhatsApp Business API Meta approval process immediately (parallel to Phase 8)
- [ ] Start GPS device operator survey immediately (parallel to Phase 8)
- [ ] Configure ALEMBIC_DATABASE_URL and ADMIN_DATABASE_URL in Railway before Phase 9 planning
- [ ] Decide 360dialog vs direct Meta Cloud API before Phase 10 planning
- [ ] Verify Flutterwave Mozambique live availability before Phase 10 planning
- [ ] Run GPS device field survey and obtain Teltonika/Coban JSON payload samples before Phase 12 planning
- [ ] Run pre-migration audit query before writing Phase 5 migration code: `SELECT tenant_id, lower(trim(client_name)), count(*) FROM contracts GROUP BY 1, 2 HAVING count(*) > 1`
- [ ] Confirm PostGIS availability on Railway PostgreSQL before any geofencing design (Phase 12+)

---

## Session Continuity

_Last session: 2026-06-06 — v2.0 roadmap expanded from 3 phases (CLI/PAY/AR, 12 reqs) to 8 phases (5-12, 32 reqs); added INFRA (Phase 8), RLS (Phase 9), NOTIF+ONBRD (Phase 10), DESP (Phase 11), GPS+TRK (Phase 12); all 32 v2.0 requirements mapped; REQUIREMENTS.md traceability updated; STATE.md milestone_name updated to plataforma-operacional-completa_

---

## Project Reference

**Core value**: A Mozambican driver can complete an entire trip — departure, refueling, stops, and delivery proof — without connectivity, and all data arrives intact at the manager when signal returns.

**Current milestone**: v2.0 — Plataforma Operacional Completa

**Stack**: FastAPI 0.115 + Python 3.12 + SQLAlchemy 2.0 async + PostgreSQL 16 / Next.js 14 App Router + React 18 + Tailwind / Vite + Dexie.js 4

**Deploy target**: Vercel (manager) + Railway or Render (backend FastAPI)

**Roadmap**: `.planning/ROADMAP.md`

**Requirements**: `.planning/REQUIREMENTS.md`

**Codebase analysis**: `.planning/codebase/` (7 documents, generated 2026-06-04)

**Research**: `.planning/research/SUMMARY.md` (generated 2026-06-06)
