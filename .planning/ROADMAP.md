# ROTAS — MVP Roadmap
_Last updated: 2026-06-06_

---

## Overview

**4 phases | 27 requirements | Brownfield — codebase ~70% complete**

Phases are ordered by hard dependency: a security bypass is active (SEC-05), the backend cannot deploy to production safely, and the PWA has no Service Worker despite the sync logic existing end-to-end. The order reflects what must be TRUE before anything downstream can be trusted.

---

## Phases

- [x] **Phase 1: Security Hardening + Deploy Foundation** — Close the active CVE, harden auth, and deploy the backend to a production environment
- [ ] **Phase 2: PWA Offline-First Completion** — Deliver the core product promise: driver app installs, works offline, syncs reliably
- [x] **Phase 3: Manager Dashboard + Reporting Layer** — Turn ROTAS from a data-collection tool into an operational management platform
- [ ] **Phase 4: Production Hardening + Scale Preparation** — Production-grade reliability for multi-tenant SaaS at scale

---

## Phase Summary

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 1 | Security Hardening + Deploy Foundation | Backend is secure and deployed to production | SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, AUTH-03, DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04 | Not Started |
| 2 | PWA Offline-First Completion | 5/8 | In Progress|  |
| 3 | Manager Dashboard + Reporting Layer | 6/12 | In Progress|  |
| 4 | Production Hardening + Scale Preparation | 8/9 | In Progress|  |

---

## Phase Details

### Phase 1: Security Hardening + Deploy Foundation

**Goal**: The backend is free of active CVEs, auth cannot be bypassed, and the application is deployed to production with validated configuration.

**Depends on**: Nothing (first phase — must complete before any external users touch the system)

**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, AUTH-03, DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04

**Success Criteria** (what must be TRUE):
  1. A request with an `alg=none` JWT is rejected with HTTP 401 — the CVE-2025-61152 auth bypass is closed
  2. The backend starts and refuses to run if `JWT_SECRET_KEY`, `DATABASE_URL`, or `ENVIRONMENT` are missing — no silent defaults in production
  3. `/auth/login` and `/driver-auth/pair` return HTTP 429 after repeated rapid requests — brute-force is rate-limited
  4. The FastAPI backend is reachable at a production URL (Railway or Render) with Alembic migrations applied automatically on deploy
  5. The manager Next.js frontend is reachable at a Vercel URL and communicates with the production backend — CORS allows only explicit production origins

**Implementation Notes**:

- **SEC-05 first**: Migrate `python-jose` to `PyJWT >= 2.8` before anything else. This is a full auth bypass (CVE-2025-61152 — tokens with `alg=none` accepted without signature verification). All other security work is irrelevant until this is fixed.
- **SEC-01 (JWT_SECRET_KEY)**: Use `pydantic-settings` `SecretStr` field with no default. App must raise `ValidationError` at startup if the env var is absent.
- **DEPLOY-01 (startup validation)**: Validate `JWT_SECRET_KEY`, `DATABASE_URL`, `ENVIRONMENT`, `REDIS_URL`, `R2_*` at import time via `Settings` model. `ENVIRONMENT=production` activates strict mode (CORS, Secure cookies, no test-token bypass).
- **DEPLOY-02 / DEPLOY-04**: `railway.toml` with `preDeployCommand = "alembic upgrade head"`. Alembic migration runs before the new server version accepts traffic — zero schema drift window.
- **DEPLOY-03**: `vercel.json` with rewrite rules, `NEXT_PUBLIC_API_URL` env var, `engines.node = "20.x"` in `package.json`.
- **SEC-02 (CORS)**: `CORS_ORIGINS` env var — list of allowed origins. In production: Vercel manager URL + any mobile web origin. Wildcard `"*"` must be rejected if `ENVIRONMENT=production`.
- **AUTH-03**: The `/api/v1/sync/batch` endpoint currently accepts any authenticated principal. Switch to `get_driver_principal` — only device-paired driver tokens can submit syncs. Manager tokens must be rejected. This prevents privilege escalation via the sync endpoint.
- **SEC-04**: Set `Secure=True` on session cookies when `ENVIRONMENT=production`. Pair with `SameSite=Lax` or `Strict`.
- **Cross-tenant regression tests before phase closes**: Write tests that confirm a query authenticated as tenant A cannot return data belonging to tenant B. These tests guard the CT-01 query rewrite in Phase 3.

**Plans**: 6 plans

Plans:
- [x] 01-01-PLAN.md — Wave 0: Test scaffolds (failing stubs for all security behaviors)
- [x] 01-02-PLAN.md — Wave 1: PyJWT migration (SEC-05) + config hardening (SEC-01, DEPLOY-01) + CORS fix (SEC-02) + sync auth lock (AUTH-03)
- [x] 01-03-PLAN.md — Wave 2: Rate limiting on auth endpoints (SEC-03) + secure cookies Next.js (SEC-04)
- [x] 01-04-PLAN.md — Wave 2: Cross-tenant isolation regression tests (D-21)
- [x] 01-05-PLAN.md — Wave 2: Deploy config — railway.toml, vercel.json, Node.js 20.x, .env.example (DEPLOY-02, DEPLOY-03, DEPLOY-04)
- [x] 01-06-PLAN.md — Wave 3: Checkpoint — deploy to Railway + Vercel, smoke test production URLs (DEPLOY-02, DEPLOY-03)

**UI hint**: no

---

### Phase 2: PWA Offline-First Completion

**Goal**: A driver on a low-cost Android device can install the app, complete a full trip cycle (departure, refueling, stops, delivery proof) without network connectivity, and have all data arrive intact at the manager dashboard when signal returns.

**Depends on**: Phase 1 (production backend must exist for sync to target; auth must be secure before driver tokens are issued at scale)

**Requirements**: PWA-01, PWA-02, PWA-03, AUTH-01, AUTH-02, AUTH-04

**Success Criteria** (what must be TRUE):
  1. A Chrome user on Android can tap "Add to Home Screen" and the app installs as a standalone PWA — no browser chrome visible after launch
  2. With the device in airplane mode, the driver can open the installed app, create a trip entry, add a stop, and record a delivery — all actions complete without error messages
  3. When airplane mode is disabled, all offline-created records appear in the manager dashboard within 60 seconds — no manual sync button required
  4. A driver who has been offline for 4 hours can resume the app and submit a batch without 401 errors — token refresh works silently on reconnect
  5. Sync `update` operations for trips, refueling records, and stops are processed correctly by the backend — not only checklist updates

**Implementation Notes**:

- **PWA-01 (Service Worker)**: Use `vite-plugin-pwa` with `injectManifest` strategy. Write a custom `src/sw.ts` that registers a `workbox-background-sync` queue targeting `POST /api/v1/sync/batch`. Dexie.js handles domain persistence; Workbox handles the network queue. Both layers are required — they solve different problems.
- **Critical SW gotcha**: Serve `sw.js` with `Cache-Control: no-store`. A cached broken SW is unrecoverable on low-cost Android without clearing site data. Add a visible "Check for updates" button in the driver UI.
- **PWA-02 (Web App Manifest)**: `display: standalone`, `start_url`, `theme_color` matching ROTAS branding, 192x192 and 512x512 icons (PNG). Manifest must pass Chrome's installability criteria — test with Lighthouse.
- **PWA-03 (Cache strategy)**: Network-first for all `/api/v1/` calls (stale data is worse than no data in financial context). Cache-first for static assets. Offline fallback page for navigation requests when network is unavailable.
- **AUTH-01 / AUTH-02 (Token refresh)**: Access token 15 min, refresh token in `HttpOnly` cookie. Silent refresh before expiry using an in-memory refresh lock (prevents parallel refresh races). Manager Next.js uses `axios` interceptor or `fetch` wrapper. Driver PWA must handle refresh before the SW flushes the background sync queue — a stale token when the queue flushes causes all queued items to fail with 401.
- **AUTH-04 (Sync update)**: Extend `POST /api/v1/sync/batch` entity_type handlers to process `update` operations for `trip`, `fuel_entry`, `stop`, and `delivery_proof`. Today only `checklist_response` supports updates.
- **Batch sync resilience**: Response must include per-item status (not just top-level HTTP status). `sync.ts` must process item-level results — a partial failure must not mark all items as synced.
- **Field testing requirement**: Phase 2 does not close until the PWA has been tested on a real low-cost Android device (Samsung Galaxy A-series or Tecno equivalent) on a mobile data connection. Background Sync API compatibility must be confirmed on the target hardware.
- **Timestamps**: Add `client_timestamp` and `server_timestamp` to sync items to handle clock skew between offline device and server.

**Plans**: 8 plans

Plans:
- [x] 02-01-PLAN.md — Wave 0: Test stubs (failing tests for AUTH-04, D-08, AUTH-01/02 refresh)
- [x] 02-02-PLAN.md — Wave 1: AUTH-04 backend (sync update handlers for trip, fuel_log, trip_stop, delivery_proof + patch service functions)
- [x] 02-03-PLAN.md — Wave 1: AUTH-01 + AUTH-02 token refresh (manager silent refresh + driver refresh with in-memory lock)
- [x] 02-04-PLAN.md — Wave 1: D-08 driver access revocation (backend driver_access_revoked error code distinction)
- [x] 02-05-PLAN.md — Wave 2: PWA-01 + PWA-03 Service Worker (vite-plugin-pwa injectManifest + sw.ts + main.tsx Workbox registration)
- [x] 02-06-PLAN.md — Wave 2: PWA-02 Web App Manifest + placeholder icons
- [ ] 02-07-PLAN.md — Wave 2: SyncStatusBanner UI (7-state banner, useNetworkStatus, useSyncStatus, D-01 through D-09)
- [ ] 02-08-PLAN.md — Wave 3: Field testing checkpoint (Android device test + full suite verification)

**UI hint**: yes

---

### Phase 3: Manager Dashboard + Reporting Layer

**Goal**: A fleet manager can open the dashboard, see real-time KPIs for their fleet, export invoices for completed trips, and receive proactive alerts before documents expire — without writing a single query or spreadsheet.

**Depends on**: Phase 2 (sync must be reliable before reporting is meaningful; billing requires delivery proof which requires sync)

**Requirements**: CT-01, CT-02, CT-03, BILL-01, BILL-02, BILL-03, RPT-01, RPT-02

**Success Criteria** (what must be TRUE):
  1. The Control Tower dashboard loads in under 3 seconds for a tenant with 20 vehicles — N+1 queries are eliminated
  2. A manager can export a completed trip invoice as a PDF that renders Mozambican names with accented characters correctly (UTF-8)
  3. A manager can export invoice data as a formatted XLSX file with value columns, dates, descriptions, and totals
  4. A trip with a negative margin cannot enter the billing queue without a supervisor waiver — the waiver workflow is functional end-to-end
  5. The dashboard shows vehicles and drivers with documents expiring in the next 30 days before they trigger a departure block
  6. KPI data (cost-per-km, fleet utilization, fuel consumption trends) is visible per vehicle and per driver

**Implementation Notes**:

- **CT-01 (N+1 fix)**: Replace ~38 sequential queries with `joinedload` for many-to-one (trip → vehicle/driver), `selectinload` for one-to-many (trip → stops), `func.count()` SQL-level aggregations for KPI scalars. Target: 4-6 queries for the full Control Tower payload. Set `lazy="raise"` on SQLAlchemy relationships in the development config to catch accidental lazy loads during development.
- **Cross-tenant safety during CT-01**: Every rewritten query must include `.where(Model.tenant_id == tenant_id)`. Run the cross-tenant regression tests written in Phase 1 after every batch of query rewrites. This is the highest-risk window for data leaks.
- **CT-02 (Redis caching)**: `redis[asyncio]` is already provisioned but not installed. Add to `pyproject.toml`. Implement cache-aside: `ct:kpis:{tenant_id}` with TTL 60s, alert keys with TTL 30s. Use `NX + EX` for the write lock to prevent cache stampede. Deploy ARQ worker as a separate process on Railway for async KPI refresh jobs.
- **CT-03 (Pagination)**: All Control Tower queue endpoints must accept `page` and `page_size` query params with a default cap (e.g., 50). Remove any unbounded queries.
- **BILL-01 (PDF)**: Use `fpdf2 >= 2.8.7` with `DejaVuSans.ttf` embedded. This font covers the full Unicode Latin Extended range including Portuguese diacritics. Bundle the font file in the backend repo. Run PDF generation as an ARQ background task — do not block the HTTP response for large invoices.
- **BILL-02 (XLSX)**: Use `openpyxl`. Format: header row bold, currency columns right-aligned with `"#,##0.00"` number format, date columns as ISO 8601. Export as ARQ background task.
- **BILL-03 (Negative margin waiver)**: The billing queue endpoint must reject trips with `margin < 0` unless a `waiver_id` is attached. The waiver model requires supervisor role authorization. Test with a trip that has margin < 0 and confirm it cannot be invoiced without supervisor approval.
- **RPT-01 (KPI dashboard)**: Cost-per-km per vehicle (fuel cost + stop costs / total km), fleet utilization % (active trips / total vehicles), fuel consumption trend (L/100km rolling 30 days), trip summary per driver. All metrics filtered by `tenant_id` — mandatory.
- **RPT-02 (Document expiry alerts)**: Query vehicles and drivers where any compliance document expires within 30 days. Proactive alert panel shows before the reactive departure block fires. This is display-only in Phase 3; notification delivery (email/WhatsApp) is v2.
- **Pre-Phase prerequisite**: Confirm `tailwind.config.*` exists in `apps/manager/` before writing dashboard UI — shadcn/ui requires Tailwind config. Fix Node.js to `"engines": { "node": "20.x"` in all `package.json` files.

**Plans**: 12 plans

Plans:

- [x] 03-01-PLAN.md — Wave 0: Test stubs for all Phase 3 behaviors (CT-01, CT-02, CT-03, BILL-01/02/03, RPT-01/02) + conftest fixtures
- [x] 03-02-PLAN.md — Wave 1: CT-01 N+1 query rewrite + CT-03 pagination + redis[asyncio] dependency (CT-01, CT-02, CT-03)
- [x] 03-03-PLAN.md — Wave 1: CT-02 Redis cache-aside + ARQ worker scaffold + ExportJob model + migration (CT-02)
- [x] 03-04-PLAN.md — Wave 1: BILL-03 waiver workflow backend (POST /billing/waivers + approve/reject endpoints + RBAC) (BILL-03)
- [x] 03-05-PLAN.md — Wave 1: RPT-01 analytics KPI endpoint + RPT-02 document expiry endpoint (RPT-01, RPT-02)
- [x] 03-06-PLAN.md — Wave 2: BILL-01 PDF (fpdf2 + DejaVuSans) + BILL-02 XLSX (openpyxl) + ARQ export jobs (BILL-01, BILL-02)
- [x] 03-07-PLAN.md — Wave 1: Tailwind v3 + shadcn@2.3.0 install in apps/manager + tailwind.config.ts + 10 components (D-01, D-02)
- [x] 03-08-PLAN.md — Wave 2: Migrate SidebarLayout + ControlTowerOverview + CostMarginBoard to Tailwind + /analytics nav entry (D-03, D-05)
- [x] 03-09-PLAN.md — Wave 2: Migrate FleetComplianceBoard + BillingTripActions + FuelControlBoard + FleetHistoryBoard + Transport/Driver boards (D-03)
- [x] 03-10-PLAN.md — Wave 3: Waiver modals + export job polling UI in BillingTripActions (BILL-01, BILL-02, BILL-03 frontend)
- [x] 03-11-PLAN.md — Wave 3: /analytics page with KPI cards + driver summary + document expiry panel (RPT-01, RPT-02 frontend)
- [x] 03-12-PLAN.md — Wave 4: Phase 3 verification checkpoint (all backend tests + frontend build + full UX verification)

**UI hint**: yes

---

### Phase 4: Production Hardening + Scale Preparation

**Goal**: ROTAS runs reliably under multi-tenant production load — financial data is stored with correct precision, the database scales with composite indexes, and the preventive maintenance module closes the gap between reactive workshop management and scheduled fleet maintenance.

**Depends on**: Phase 3 (all product features complete; this phase is operational hardening, not new features)

**Requirements**: MAINT-01 (promoted from v2 to Phase 4 MVP)

**Additional hardening items** (not tracked as individual v1 requirements but required for production readiness):
- Preventive maintenance scheduler (odometer/calendar triggers → automatic work order generation)
- Driver scorecard (composite score from GPS, km, stop duration from existing sync data)
- `float` → `Numeric(10,2)` migration for all monetary columns with faseado backfill
- Gunicorn multi-worker configuration for FastAPI (Railway production deployment)
- Composite index audit with `tenant_id` as leading column on all high-traffic tables

**Success Criteria** (what must be TRUE):
  1. A vehicle reaches its configured service interval (e.g., 10,000 km) and a work order is automatically created and visible in the workshop queue — no manual trigger required
  2. A fleet manager can view a driver's scorecard with a composite performance score derived from trip data already in the system
  3. All monetary values in the database are stored as `Numeric(10,2)` — no `float` columns remain in financial tables; existing data has been migrated without loss
  4. The backend handles concurrent requests from multiple tenants without worker contention — Gunicorn is configured with ≥2 workers in production
  5. All queries on high-traffic tables use indexes where `tenant_id` is the leading column — no sequential scans on tenant-filtered queries at 1,000+ row tables

**Implementation Notes**:

- **MAINT-01 (Preventive maintenance scheduler)**: Add `MaintenanceSchedule` model with fields: `vehicle_id`, `trigger_type` (odometer | calendar), `interval_km`, `interval_days`, `last_triggered_at`, `next_due_at`. ARQ worker (already deployed for CT-02) runs daily check: if `current_odometer >= next_due_at` or `today >= next_due_at`, create a `ServiceOrder` and update `last_triggered_at`. Reuse existing `ServiceOrder` model from the workshop module.
- **Driver scorecard**: Derive score from data already collected: km per trip, stop duration relative to trip distance, number of sync batches per trip (proxy for connectivity discipline), delivery proof submission rate. No new data collection required — aggregate from existing sync records.
- **`Numeric(10,2)` migration**: Identify all `Float` columns in financial tables (`fuel_entry.cost`, `stop.cost`, `trip.total_cost`, etc.). Write Alembic migration with `ALTER COLUMN ... TYPE NUMERIC(10,2) USING ROUND(value::numeric, 2)`. Test backfill on a copy of production data before running on live. Phase the migration: add new column, backfill, rename, drop old.
- **Composite indexes**: Run `EXPLAIN ANALYZE` on the 10 most-executed queries in production. Add `CREATE INDEX CONCURRENTLY` for any missing `(tenant_id, ...)` composite indexes. Priority tables: `trip`, `fuel_entry`, `vehicle`, `driver`, `stop`.
- **Gunicorn**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker` in `railway.toml` start command. Set `--timeout 30` for long-running sync batch processing. Tune worker count to Railway instance memory (2 workers per GB RAM as baseline).
- **RLS consideration**: PostgreSQL Row Level Security as a second isolation layer (defense-in-depth) was deferred from Phase 1. Evaluate adding it in Phase 4 once the query rewrite (CT-01) and index audit are complete. This is a low-risk window — all queries already filter by `tenant_id`.

**Plans**: 9 plans

Plans:
- [x] 04-01-PLAN.md — Wave 1: Deps install (arq, gunicorn, redis[asyncio]) + test stubs for all Phase 4 behaviors
- [x] 04-02-PLAN.md — Wave 2: MAINT-01 scheduler (WorkOrder creation + next-cycle + imminent alerts) (MAINT-01)
- [x] 04-03-PLAN.md — Wave 3: MAINT-01 ARQ worker + odometer event trigger (MAINT-01)
- [x] 04-04-PLAN.md — Wave 2: Driver scorecard API (get_driver_scorecard + endpoint) (MAINT-01 adjacent)
- [x] 04-05-PLAN.md — Wave 2: Decimal type annotation cleanup (Mapped[float] → Mapped[Decimal] on Numeric columns)
- [x] 04-06-PLAN.md — Wave 3: Composite indexes Alembic migration (10 indexes, CONCURRENTLY, D-14)
- [x] 04-07-PLAN.md — Wave 3: Gunicorn railway.toml + pool tuning + checkpoint (D-12, D-13)
- [ ] 04-08-PLAN.md — Wave 4: PostgreSQL RLS (event listener + Alembic migration + ALEMBIC_DATABASE_URL) (D-16–D-19)
- [x] 04-09-PLAN.md — Wave 4: UI — DriverScorecardPanel + MaintenanceImminentPanel + page integration + checkpoint

**UI hint**: yes

---

## Coverage Check

| Requirement | Phase | Category |
|-------------|-------|----------|
| SEC-01 | Phase 1 | Security |
| SEC-02 | Phase 1 | Security |
| SEC-03 | Phase 1 | Security |
| SEC-04 | Phase 1 | Security |
| SEC-05 | Phase 1 | Security |
| AUTH-03 | Phase 1 | Authentication |
| DEPLOY-01 | Phase 1 | Deploy |
| DEPLOY-02 | Phase 1 | Deploy |
| DEPLOY-03 | Phase 1 | Deploy |
| DEPLOY-04 | Phase 1 | Deploy |
| PWA-01 | Phase 2 | PWA |
| PWA-02 | Phase 2 | PWA |
| PWA-03 | Phase 2 | PWA |
| AUTH-01 | Phase 2 | Authentication |
| AUTH-02 | Phase 2 | Authentication |
| AUTH-04 | Phase 2 | Authentication |
| CT-01 | Phase 3 | Control Tower |
| CT-02 | Phase 3 | Control Tower |
| CT-03 | Phase 3 | Control Tower |
| BILL-01 | Phase 3 | Billing |
| BILL-02 | Phase 3 | Billing |
| BILL-03 | Phase 3 | Billing |
| RPT-01 | Phase 3 | Reporting |
| RPT-02 | Phase 3 | Reporting |
| MAINT-01 | Phase 4 | Maintenance |

**Total v1 requirements mapped: 25/25**

**Note on Phase 4 hardening items**: The additional items in Phase 4 (preventive maintenance scheduler behavior, driver scorecard, `Numeric(10,2)` migration, Gunicorn config, composite index audit) are not tracked as individual REQUIREMENTS.md entries — they are operational hardening tasks derived from the research findings. MAINT-01 is the only formally tracked requirement in Phase 4.

---

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Hardening + Deploy Foundation | 6/6 | Complete | 2026-06-06 |
| 2. PWA Offline-First Completion | 7/8 | Field test pending | - |
| 3. Manager Dashboard + Reporting Layer | 12/12 | Complete | 2026-06-06 |
| 4. Production Hardening + Scale Preparation | 8/9 | RLS plan pending | - |

---

---

# ROTAS — v2.0 Roadmap: Plataforma Operacional Completa
_Last updated: 2026-06-06_

---

## Overview (v2.0)

**8 phases | 32 requirements | Milestone: Transform ROTAS into a full operational platform**

This milestone extends ROTAS across five capability areas: financial client management (CLI/PAY/AR), production infrastructure hardening (INFRA), database-level tenant isolation (RLS), proactive communications and public SaaS onboarding (NOTIF/ONBRD), driver financial settlement (DESP), and GPS fleet visibility with customer tracking (GPS/TRK).

**Execution sequencing advisory**: Phase 8 (INFRA) and Phase 9 (RLS) are infrastructure prerequisites that unlock subsequent phases. Although numbered 8-9, they should be executed before Phases 5-7 if Phase 4 plan 04-08 (RLS) has not yet completed. Phase 5 (CLI) explicitly depends on RLS infrastructure existing; Phase 10 (NOTIF+ONBRD) depends on Phase 8 tenant limits; Phase 12 (GPS+TRK) depends on Phase 9 RLS. WhatsApp template approval (4-6 weeks, external) must begin in parallel with Phase 8 execution. GPS device operator survey (2-4 weeks, external) must begin in parallel with Phase 8 execution.

**Hard dependency chain**:
- INFRA (Phase 8) → NOTIF+ONBRD (Phase 10) → DESP (Phase 11)
- RLS (Phase 9) → GPS+TRK (Phase 12)
- RLS (Phase 9) → CLI (Phase 5) → PAY (Phase 6) → AR (Phase 7)

---

## Phases (v2.0)

- [ ] **Phase 5: Client Registry + Migration Foundation** — Clients become first-class entities; all existing contracts and invoices gain a client_id FK with zero data loss
- [ ] **Phase 6: Payment Registration** — Managers can record total and partial payments against invoices, including advance payments
- [ ] **Phase 7: Accounts Receivable + Aging Dashboard** — Client statements, aging buckets, AR KPIs, and PDF export complete the financial management loop
- [ ] **Phase 8: Infrastructure Hardening** — Sentry error tracking, R2/S3 durable file storage, and tenant plan limit enforcement make ROTAS production-grade
- [x] **Phase 9: PostgreSQL RLS Policies** — Database-level tenant isolation across all 47+ tenant-owned tables as a second security layer (completed 2026-06-07)
- [ ] **Phase 10: Notifications + Self-Service Onboarding** — WhatsApp/email notification infrastructure and public registration enable SaaS launch
- [ ] **Phase 11: Driver Financial Settlement (Despacho)** — Complete driver expense lifecycle: advance before departure, settlement after delivery, PDF document
- [ ] **Phase 12: GPS Integration + Customer Tracking Portal** — Fleet map in manager dashboard, GPS webhook ingestion, shareable customer tracking links

---

## Phase Details (v2.0)

### Phase 04.1: UI Design System and Component Library (INSERTED)

**Goal:** Every page in the manager app uses consistent design tokens, shared primitive components, and delivers a premium B2B SaaS experience with IBM Plex Mono on all data values and amber as the sole accent color.

**Requirements**: DS-01, DS-02, DS-03, DS-04, DS-05, DS-07, DS-08, DS-09
**Depends on:** Phase 4
**Plans:** 7/8 plans executed

Plans:
- [x] 04.1-01-PLAN.md — Wave 1: CSS foundation fix (remove oklch override, consolidate @layer base, extend Tailwind config, install shadcn components)
- [x] 04.1-02-PLAN.md — Wave 2: Core primitives A (StatusBadge, KpiCard, PageHeader, SectionHeader, WorkQueue)
- [x] 04.1-03-PLAN.md — Wave 2: Core primitives B (DataTable, MonoCell, MoneyCell, EmptyState, DataSourceBadge)
- [x] 04.1-04-PLAN.md — Wave 3: SidebarLayout redesign (4 grouped sections, amber active indicator)
- [x] 04.1-05-PLAN.md — Wave 4: Migrate ControlTowerOverview + FleetComplianceBoard
- [x] 04.1-06-PLAN.md — Wave 4: Migrate FuelControlBoard + FleetHistoryBoard + TransportCargoBoard + CostMarginBoard
- [x] 04.1-07-PLAN.md — Wave 5: Migrate page.tsx billing section
- [ ] 04.1-08-PLAN.md — Wave 6: Legacy CSS cleanup + visual checkpoint

### Phase 5: Client Registry + Migration Foundation

**Goal**: A manager can create, search, and manage clients as first-class entities — and every existing contract and invoice is automatically associated with the correct client, with no data loss and no manual re-entry required.

**Depends on**: Phase 4 (PostgreSQL RLS infrastructure must exist — specifically plan 04-08 must complete, or Phase 9 must complete, before Phase 5 starts; Decimal type annotations must be clean; production deployment must be stable before a live data migration runs)

**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05

**Success Criteria** (what must be TRUE):
  1. A manager can create a client with NUIT, trading name, address, phone, email, and payment terms — and the client appears in a searchable list scoped to their tenant
  2. When a client's outstanding balance exceeds their configured credit limit, a visual warning is displayed on the client detail page and invoice list — without blocking any action
  3. Every existing contract and billing document that had a `client_name` string now has a populated `client_id` FK pointing to a `clients` record — `SELECT count(*) FROM contracts WHERE client_id IS NULL` returns zero (or a documented and accepted exception count)
  4. A manager creating or editing a contract selects the client from a dropdown backed by the client registry — free-text client_name entry is no longer the primary path
  5. New invoices display a sequential number in `AAAA/NNNN` format (e.g., `2026/0001`) that never repeats or gaps within the same tenant

**Architecture constraints**:
- Four Alembic migrations strictly separated — never DDL + DML in the same file: (a) create `clients` table with RLS policy and `GRANT TO rotas_app` in the same migration, (b) add nullable `client_id` FK to `contracts` and `billing_documents` + add `due_date` column to `billing_documents`, (c) backfill data via `SELECT DISTINCT tenant_id, client_name FROM contracts` → insert clients → UPDATE FKs, (d) create `payments` table (scaffolded here, populated in Phase 6)
- Pre-migration audit query is a required first step before writing migration code: `SELECT tenant_id, lower(trim(client_name)), count(*) FROM contracts GROUP BY 1, 2 HAVING count(*) > 1` — review variant groups before any FK backfill
- `due_date` column MUST be added in migration (b) alongside `client_id` — aging calculation needs it from day one; adding it in Phase 7 would require a second backfill
- RLS must be enabled on `clients` table in the CREATE TABLE migration — not a follow-up patch. Pattern: `ALTER TABLE clients ENABLE ROW LEVEL SECURITY` + `CREATE POLICY` + `GRANT` in the same Alembic file
- `client_name` is kept on `BillingDocument` and `Contract` as a denormalized snapshot — do not drop it; it has independent archival and legal value
- PostgreSQL SEQUENCE for invoice numbering must be tenant-scoped: one sequence per tenant or a composite sequence pattern — never a Python MAX+1 counter

**Plans**: 5 plans

Plans:
- [x] 05-01-PLAN.md � Wave 1: clients backend (model, migration a, service, router) + Wave 0 test stubs (CLI-01, CLI-02)
- [x] 05-02-PLAN.md � Wave 1: FK migrations (b) + pre-audit + backfill (c) + payments scaffold (d) (CLI-03)
- [x] 05-03-PLAN.md � Wave 2: /clientes list page + /clientes/[id] detail page + ClientFormModal + sidebar nav (CLI-01, CLI-02)
- [x] 05-04-PLAN.md � Wave 2: ContractFormModal ClientCombobox + backend contracts schema/service update (CLI-04)
- [x] 05-05-PLAN.md � Wave 3: CLI-05 display (MonoCell in billing table) + test_invoice_number_format stub (CLI-05)

**UI hint**: yes

---

### Phase 6: Payment Registration

**Goal**: A manager can record that a client has paid — in full, partially, or in advance — and the invoice balance and client outstanding balance update immediately, with a full audit trail.

**Depends on**: Phase 5 fully verified (zero NULL `client_id` confirmed before Phase 6 starts — this is a hard gate, not a suggestion)

**Requirements**: PAY-01, PAY-02, PAY-03

**Success Criteria** (what must be TRUE):
  1. A manager can register a payment against an issued invoice specifying amount, value date, and payment method (bank transfer, cheque, cash) — the payment appears in the invoice detail immediately
  2. A manager can register a payment for less than the invoice total — the invoice shows a partial balance due, not a "paid" status
  3. A manager can register an advance payment for a client with no specific invoice — the advance appears as credit on the client record and can be applied to a future invoice
  4. After any payment is registered, `GET /clients/{id}/statement` reflects the updated balance within the same request — no eventual consistency lag

**Architecture constraints**:
- `payment_allocations` junction table MUST be created in this phase (not deferred to Phase 7) — schema: `(payment_id, billing_document_id, amount_applied, created_at)`. Retrofitting this table after payment rows exist is a high-risk schema migration
- `client_payments` table holds the cash receipt; `payment_allocations` holds the link to invoices — do not put `billing_document_id` as a direct NOT NULL FK on `client_payments`
- Advance payments have no allocation rows at creation time — `billing_document_id` is nullable on payments, and allocation rows are inserted separately when the advance is applied to an invoice
- `POST /api/v1/billing/payments` requires `Idempotency-Key` header — same pattern as billing document creation
- Payment registration must verify `billing_document.client_id == payment.client_id` AND both share the same `tenant_id` before writing — cross-client payment mismatches must return HTTP 409
- Payments are never hard-deleted — use `status = "voided"` with `voided_by` and `voided_reason` fields; audit log entry required for every void
- `billing_documents.paid_at` (existing column) is updated as a denormalized cache when `SUM(allocations) >= total_amount` — it is no longer the source of truth, but is kept for backward compatibility with PDF generation

**Plans**: 4 plans

Plans:
- [x] 06-01-PLAN.md � Wave 1: Test stubs (10 failing tests for PAY-01, PAY-02, PAY-03)
- [x] 06-02-PLAN.md � Wave 2: Backend service layer (register_payment, void_payment, apply_advance, _get_outstanding_balance, get_client_statement)
- [x] 06-03-PLAN.md � Wave 3: Router endpoints (POST /billing/payments, void, apply; GET /clients/{id}/statement)
- [x] 06-04-PLAN.md � Wave 4: Frontend PaymentModal + route handlers + /cobranca and /clientes/[id] integration

**UI hint**: yes

---

### Phase 7: Accounts Receivable + Aging Dashboard

**Goal**: A manager can see, at a glance, which clients owe money and for how long — and can generate a formal client statement as a PDF for reconciliation or collections.

**Depends on**: Phase 6 (aging and outstanding balance calculations require payment records; building the dashboard before payments exist would show every invoice as outstanding)

**Requirements**: AR-01, AR-02, AR-03, AR-04

**Success Criteria** (what must be TRUE):
  1. A manager can open a client's statement for any date range and see a list of invoices with issue date, due date, total amount, amount paid, and outstanding balance — all values correct relative to registered payments
  2. A manager can view a client's aging breakdown showing outstanding balance bucketed into current / 1–30 / 31–60 / 61–90 / +90 days overdue — the reference date is always displayed next to the buckets
  3. The AR dashboard shows tenant-wide totals (total issued, total received, total outstanding) and a ranked list of the 5 clients with the largest outstanding balances
  4. A manager can export a client statement as a PDF that includes the tenant's company name as a header and renders Mozambican names with diacritics correctly (UTF-8)

**Architecture constraints**:
- Aging is computed by a service-layer SQL query with an explicit `as_of` date parameter — never use `NOW()` implicitly; the `as_of` parameter makes aging testable without time mocking and allows retrospective reports
- Aging buckets are derived from `billing_documents.due_date` (stored in Phase 5) — not from `issued_at + payment_terms_days` at query time; `due_date` is the authoritative column
- Outstanding per document = `billing_documents.total_amount - SUM(payment_allocations.amount_applied WHERE billing_document_id = X)` — do not use `billing_documents.paid_at` as the balance source
- Only documents with `status = 'issued'` appear in aging — draft documents are not receivables
- AR dashboard endpoint: `GET /api/v1/billing/ar-summary?as_of=YYYY-MM-DD` — tenant-scoped, paginated top-5 by outstanding balance
- Client statement PDF uses `fpdf2 + DejaVuSans.ttf` (same pattern established in Phase 3 for invoice PDF) — no new PDF library introduced
- Composite index `(tenant_id, client_id, due_date)` on `billing_documents` is required for aging query performance — add in the Phase 7 migration if not already present

**Plans**: TBD

**UI hint**: yes

---

### Phase 8: Infrastructure Hardening

**Goal**: Production errors are visible in real time, uploaded files survive server restarts, and tenants that exceed their plan limits are blocked before data integrity is compromised.

**Depends on**: Nothing (infrastructure phase with no hard dependencies on other v2 phases — execute first or in parallel with Phase 9)

**Requirements**: INFRA-01, INFRA-02, INFRA-03

**Success Criteria** (what must be TRUE):
  1. An unhandled exception in FastAPI, the ARQ worker, the Next.js manager, or the driver PWA appears as a Sentry event within 60 seconds — PII fields (driver name, cargo description, phone number) are absent from the Sentry payload
  2. A delivery proof photo or billing PDF uploaded to ROTAS is retrievable after a Railway deploy (ephemeral disk wipe) — zero `storage_provider = local` records exist after the R2 migration completes
  3. When a tenant attempts to create a vehicle beyond their `max_vehicles` limit, the API returns HTTP 403 with an `upgrade_url` field — the manager dashboard displays a usage warning banner when utilization reaches 80% of any plan limit

**Architecture constraints**:
- **Sentry**: `sentry_sdk.init()` in `backend/app/main.py` lifespan handler; `before_send` hook strips fields matching `["driver_name", "cargo_description", "phone", "nuit", "email"]` from all event extras and request data. `traces_sample_rate=0.05` in production. `@sentry/nextjs` wired in `next.config.mjs` for App Router. Driver PWA uses `@sentry/vite-plugin` in `vite.config.mjs`. ARQ worker initializes Sentry before starting the event loop.
- **R2/S3**: Replace `boto3>=1.43` with `aiobotocore[boto3]>=3.7.0` in `pyproject.toml` — do not keep both, they conflict at the botocore layer. Implement dual-provider `storage.py` backend: `StorageProvider` enum with `LOCAL` and `R2` variants; `upload_file()` and `generate_presigned_url()` dispatch on `settings.storage_provider`. Migration script: iterate all `File` records with `storage_provider = "local"`, upload to R2, update record. Run migration before switching `settings.storage_provider` to `R2`. Verify zero local records before enabling the switch.
- **Tenant limits**: Add `_check_vehicle_limit()`, `_check_driver_limit()`, `_check_user_limit()` guard functions called at the top of each `create_*` service function. Guards read `Tenant.max_vehicles` / `max_drivers` / `max_users` and compare against current counts. Return `ApiError("plan_limit_reached", ..., 403)` with `{"upgrade_url": settings.upgrade_url}` in the body. Cache tenant limit counts in Redis with TTL 30s to avoid per-request count queries. Dashboard `layout.tsx` fetches `GET /api/v1/tenant/limits` and renders a `<LimitWarningBanner>` component when any dimension is ≥ 80%.

**Plans**: 8 plans

Plans:
- [ ] 08-01-PLAN.md — Wave 0: Test scaffolds for all three INFRA requirements (failing stubs)
- [ ] 08-02-PLAN.md — Wave 1: Backend Sentry integration (FastAPI + ARQ worker) (INFRA-01)
- [ ] 08-03-PLAN.md — Wave 1: storage.py dual-provider abstraction + files/service.py refactor (INFRA-02)
- [ ] 08-04-PLAN.md — Wave 2: ARQ worker R2 routing + ExportJob.file_id + migration script (INFRA-02)
- [ ] 08-05-PLAN.md — Wave 2: Tenant limit guards + Redis cache + GET /api/v1/tenant/limits (INFRA-03)
- [ ] 08-06-PLAN.md — Wave 3: LimitWarningBanner component + layout.tsx integration (INFRA-03)
- [ ] 08-07-PLAN.md — Wave 1: Frontend Sentry (Next.js manager + Vite driver PWA) (INFRA-01)
- [ ] 08-08-PLAN.md — Wave 4: Human verification checkpoint (INFRA-01, INFRA-02, INFRA-03)

**UI hint**: yes

---

### Phase 9: PostgreSQL RLS Policies

**Goal**: Tenant data is isolated at the database level — even if application-layer `tenant_id` filtering is accidentally removed, a cross-tenant data leak is impossible under the `rotas_app` role.

**Depends on**: Nothing (standalone migration phase — execute before Phase 5 CLI, before Phase 12 GPS, and ideally before any new v2 migrations create new tables)

**Requirements**: RLS-01, RLS-02, RLS-03

**Success Criteria** (what must be TRUE):
  1. All 47+ tables with `tenant_id` have `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and a `CREATE POLICY` using `current_setting('app.tenant_id')` — confirmed by querying `pg_policies`
  2. Alembic migrations and the ARQ worker operate without errors using the `rotas_admin` (BYPASSRLS) role — `ALEMBIC_DATABASE_URL` and `ADMIN_DATABASE_URL` are distinct from `DATABASE_URL` and configured in Railway
  3. The cross-tenant test suite passes under `rotas_app` role — a query for tenant A's vehicles returns zero rows when the session `app.tenant_id` is set to tenant B's ID, with no explicit `WHERE tenant_id` filter in the query

**Architecture constraints**:
- **SET LOCAL vs SET**: The `after_begin` event listener in `database.py` must use `SET LOCAL app.tenant_id = ...` not `SET app.tenant_id = ...`. `SET` persists on pooled asyncpg connections and causes the next request reusing that connection to execute under the wrong tenant with no error raised. Verify this in the existing `database.py` before the migration runs.
- **Role separation**: Three database URLs must exist in Railway config: `DATABASE_URL` (connects as `rotas_app` role — subject to RLS), `ALEMBIC_DATABASE_URL` (connects as `rotas_admin` — BYPASSRLS, for schema migrations), `ADMIN_DATABASE_URL` (connects as `rotas_admin` — BYPASSRLS, for ARQ cross-tenant jobs). All three must be configured before any RLS policy migration runs.
- **Migration structure**: Single Alembic migration file. For each of the 47+ tenant-owned tables: `ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY; CREATE POLICY rls_{table} ON {table} USING (tenant_id::text = current_setting('app.tenant_id', true));`. Tables without `tenant_id` (e.g., `tenants`, `idempotency_keys`) are explicitly excluded with a comment.
- **New tables created in v2.0**: Every new table with `tenant_id` created in Phases 5-12 must include its RLS policy in the CREATE TABLE migration — not as a follow-up patch. This is mandatory for `clients`, `client_payments`, `payment_allocations`, `driver_advances`, `trip_settlements`, `gps_positions`, `gps_devices`, `vehicle_last_position`, `tracking_tokens`.
- **Confirmation gate**: After migration runs, execute `SELECT tablename FROM pg_policies WHERE policyname LIKE 'rls_%'` and compare count against expected 47+ tables. Any gap is a blocker before Phase 5 starts.
- **WhatsApp template parallel activity**: Draft and submit all 7 WhatsApp message templates to Meta for approval during Phase 9 execution. Templates needed: `trip_dispatched`, `delivery_completed`, `eta_update`, `document_expiring`, `settlement_approved`, `settlement_disputed`, `driver_blocked`. Meta approval takes 1-3 days per template; business verification takes 5-14 days. Submitting during Phase 9 ensures approval before Phase 10 (NOTIF) begins.

**Plans**: TBD

**UI hint**: no

---

### Phase 10: Notifications + Self-Service Onboarding

**Goal**: Any Mozambican transportadora can register for ROTAS without contacting anyone — and once registered, the system proactively notifies managers about document expirations and drivers about settlement decisions via WhatsApp, with email as fallback.

**Depends on**: Phase 8 (tenant limits must be enforced before public registration opens — PITFALL-19: new tenants created before limits are enforced can exceed plan constraints with no guard); WhatsApp templates must be approved by Meta before this phase closes (submitted during Phase 9)

**Requirements**: NOTIF-01, NOTIF-02, NOTIF-03, ONBRD-01

**Success Criteria** (what must be TRUE):
  1. A fleet manager at a Mozambican transportadora not yet in ROTAS can complete the public registration form with company name, NUIT, and email — and receive an email verification link that activates their tenant account
  2. A manager whose vehicle document expires in 30 days receives a WhatsApp message from the ROTAS business number — without any manual export or spreadsheet check
  3. A manager contact without confirmed WhatsApp opt-in receives the same alert via email — the system never sends WhatsApp to unconfirmed numbers
  4. All notification dispatch is non-blocking — the HTTP handler enqueues an ARQ task and returns immediately; delivery happens asynchronously with 3-attempt exponential backoff

**Architecture constraints**:
- **New modules**: `backend/app/modules/notifications/` (template management, notification log, ARQ dispatch tasks) and `backend/app/modules/onboarding/` (public registration flow, atomic tenant+owner creation)
- **Onboarding**: `POST /api/v1/onboarding/register` uses `get_session_raw` (no JWT — public endpoint). Creates `Tenant` + `User` (role=owner) in a single atomic transaction. Sets `tenant.is_active = False` until email verification completes. Uses `itsdangerous.URLSafeTimedSerializer` to generate the verification token (stateless — no token DB table). Token embedded in `GET /api/v1/onboarding/verify?token=...` link sent by email. `IntegrityError` on duplicate NUIT must be caught and re-raised as `ApiError("slug_already_taken", ..., 409)`.
- **Notifications**: `notification_templates` table stores approved Meta template names and parameter schemas. `notification_log` table records every dispatch attempt with status (queued/sent/failed/skipped). ARQ task `task_send_whatsapp(notification_id)` calls WhatsApp Business Cloud API v22.0 with retry policy: attempt 1 after 30s, attempt 2 after 5min, attempt 3 after 30min. `task_send_email(notification_id)` uses `aiosmtplib` for async SMTP — does not block the FastAPI event loop.
- **Opt-in guard**: `dispatch_notification()` service function checks `contact.whatsapp_opt_in_confirmed` before enqueuing WhatsApp task. If false: enqueue email task instead. Never send WhatsApp to unconfirmed number — Meta suspends accounts for this (PITFALL-10). Add `whatsapp_opt_in_confirmed: bool = False` field to `Driver` model and customer contact model in this phase.
- **Phone normalization**: All phone number fields validated and normalized to E.164 format (`+258...`) using `phonenumbers` library at input — in `Pydantic` validators on schemas. Prevents silent WhatsApp API failures from malformed numbers.
- **BSP selection**: Resolve 360dialog vs direct Meta Cloud API before planning this phase. 360dialog recommended for launch (handles message routing + WABA provisioning); direct Meta Cloud API requires separate WABA setup.
- **Next.js public pages**: `/register` and `/register/verify` routes excluded from `apps/manager/middleware.ts` auth redirect matcher. Server components only — no client-side auth state.
- **Stripe**: Wire Stripe subscription webhook handler (`POST /api/v1/stripe/webhook`) in this phase even if checkout is disabled for v2.0. Subscription lifecycle events (`customer.subscription.updated`, `customer.subscription.deleted`) update `tenant.plan` field. Enables v2.1 to activate checkout without backend changes.

**Plans**: TBD

**UI hint**: yes

---

### Phase 11: Driver Financial Settlement (Despacho)

**Goal**: A manager can issue a cash advance to a driver before departure, and after the trip closes, compute, approve, and generate a PDF document for the financial settlement — with full audit trail and multi-currency support for cross-border routes.

**Depends on**: Phase 10 (WhatsApp notification infrastructure must exist — settlement approval triggers WhatsApp notification to driver; DESP-03 explicitly requires notification dispatch)

**Requirements**: DESP-01, DESP-02, DESP-03, DESP-04, DESP-05

**Success Criteria** (what must be TRUE):
  1. A manager can issue a cash advance to a driver for a specific trip, specifying amount, payment method, and disbursement date — the advance appears on the trip record with status `pending` until the manager marks it `disbursed`
  2. After a trip closes, the system computes the settlement automatically: advance minus approved driver-paid expenses equals the balance, with sign indicating who owes whom
  3. A manager can approve or dispute a settlement with a written justification — the driver receives a WhatsApp notification within 5 minutes of the decision; the settlement state is recorded in the audit log
  4. A PDF settlement document is generated by the ARQ worker listing all expenses, the advance amount, the final balance, and the settlement date — the manager can download it from the trip detail page
  5. A cross-border trip with ZAR-denominated expenses can be reconciled — the manager enters the MZN/ZAR exchange rate at reconciliation time and all amounts are converted to MZN in the settlement document

**Architecture constraints**:
- **New tables**: `driver_advances` and `trip_settlements` created within the existing `trips` module. `driver_advances` schema: `(id, trip_id, driver_id, tenant_id, amount Numeric(10,2), currency char(3), method varchar, status enum[pending/disbursed/cancelled], disbursed_at, created_by, created_at)`. `trip_settlements` schema: `(id, trip_id, driver_id, tenant_id, advance_total Numeric(10,2), expense_total Numeric(10,2), balance Numeric(10,2), currency char(3), status enum[draft/pending_approval/approved/disputed], approved_by, approved_at, dispute_reason, costs_reconciled_at, created_at)`. Both tables require RLS policies in their CREATE TABLE migration.
- **Settlement computation**: `compute_settlement()` in `trips/despacho.py` queries `trip_costs WHERE paid_by = 'driver' AND approved = true` — never creates a parallel expense ledger (PITFALL-03). Sum of approved driver-paid costs = `expense_total`. `balance = advance_total - expense_total`. Positive balance means company owes driver; negative means driver owes company.
- **State machine**: `driver_advances` follows `pending → disbursed → cancelled` (no backward transitions). `trip_settlements` follows `draft → pending_approval → approved | disputed`. Settlement creation sets `costs_reconciled_at` timestamp. Finalization re-reads `trip_costs` at approval time to catch any cost changes since draft — optimistic lock check: if `trip_costs` modified after `costs_reconciled_at`, reject with `409 settlement_costs_changed` (PITFALL-04).
- **Multi-currency**: `DESP-05` — `trip_settlements` stores `fx_rate Numeric(10,6)` and `base_currency char(3)`. When trip has ZAR expenses, manager POSTs `{"fx_rate_mzn_zar": 1.23}` to the settlement endpoint. `compute_settlement()` converts each ZAR cost: `mzn_amount = zar_amount * fx_rate`. Settlement PDF always rendered in MZN. No automatic FX rate fetching — manual entry only.
- **ARQ task**: `task_generate_settlement_pdf(settlement_id)` generates PDF using `fpdf2 + DejaVuSans.ttf` (same pattern as billing PDF). Stores result as a `File` record via the files module (R2 storage — Phase 8 must be complete). Manager downloads via `GET /api/v1/trips/{trip_id}/settlement/pdf`.
- **Dexie schema**: If any settlement entity needs to be in the driver PWA sync queue (e.g., advance acknowledgment), `db.version()` must be incremented in `apps/driver/src/db.ts` — schema version bump is required or Dexie throws a schema version error (PITFALL-17). Assess scope before implementation.

**Plans**: TBD

**UI hint**: yes

---

### Phase 12: GPS Integration + Customer Tracking Portal

**Goal**: A fleet manager can see every vehicle's current position on a live map, and a client can follow their shipment via a shareable link — without installing any app or logging into ROTAS.

**Depends on**: Phase 9 (RLS policies must exist before `gps_positions` table is created — GPS data is tenant-scoped and must be covered by policy at creation time); GPS device operator survey must be completed before implementation begins (external dependency — start survey during Phase 8 execution)

**Requirements**: GPS-01, GPS-02, GPS-03, TRK-01, TRK-02

**Success Criteria** (what must be TRUE):
  1. A Teltonika or Coban GPS device configured to HTTP POST mode sends a position event to `POST /api/v1/gps/webhook/{imei}` and the position appears on the fleet map within 15 seconds — the webhook rejects requests with invalid HMAC signatures
  2. A manager opens the fleet map in the dashboard and sees every vehicle's last known position as a pin — pins older than 5 minutes display a staleness indicator; the map refreshes every 10 seconds without a full page reload
  3. A manager generates a tracking link for an active trip and shares it with the client — the client opens the link without logging in, sees the delivery status, last position in text form, and any delivery proof photo
  4. The tracking page auto-refreshes every 5 minutes and shows a visual indicator when position data is more than 5 minutes old
  5. The GPS webhook endpoint rejects more than 60 events per minute per IMEI — burst from misconfigured devices cannot degrade the database

**Architecture constraints**:
- **New modules**: `backend/app/modules/gps/` (webhook ingestion, device registration, HMAC auth, position storage) and `backend/app/modules/tracking/` (token generation, public payload assembly)
- **GPS tables**: `gps_positions` (append-only, monthly PostgreSQL declarative partitions — `PARTITION BY RANGE (recorded_at)`, one partition per month, 90-day retention ARQ cron). `gps_devices` (IMEI registry: `imei`, `tenant_id`, `vehicle_id`, `device_secret` for HMAC, `is_active`). `vehicle_last_position` (upsert table for fast fleet map reads: `vehicle_id PK`, `lat`, `lon`, `speed`, `heading`, `recorded_at`, `updated_at`). All three tables require RLS policies in their CREATE TABLE migration.
- **Webhook auth**: `POST /api/v1/gps/webhook/{imei}` uses `get_session_raw` (no JWT). HMAC-SHA256 validation: `expected = hmac.new(device_secret, request_body, sha256).hexdigest()`. Compare against `X-Device-Signature` header using `hmac.compare_digest()`. Resolve `tenant_id` and `vehicle_id` from `gps_devices` table after HMAC passes — never before. An attacker who knows an IMEI cannot inject positions without the device secret (PITFALL-08).
- **Position normalization**: GPS devices (Teltonika FMB, Coban GT06) emit different JSON schemas. Normalization layer maps device-specific fields to internal schema: `{lat, lon, speed_kmh, heading_deg, accuracy_m, recorded_at}`. Obtain actual JSON payload samples from operators before implementing — device firmware version affects field names (MEDIUM confidence in research).
- **Fleet map**: `GET /api/v1/gps/vehicles/latest` returns one row per vehicle from `vehicle_last_position` — never queries `gps_positions` directly for live display. Manager dashboard uses React Query `refetchInterval: 10000`. SSE upgrade (`sse-starlette`) is a Phase 12 enhancement if polling proves insufficient.
- **Tracking tokens**: `tracking_tokens` table: `(id, trip_id, tenant_id, token varchar(64), expires_at, created_by, created_at)`. Token is 256 bits of `secrets.token_urlsafe(32)`. `POST /api/v1/tracking-tokens` (manager auth) creates token. `GET /api/v1/public/track/{token}` (no auth, `get_session_raw`) returns public payload: delivery status, last known position text, delivery proof photo URL if available. Rate limited to 30 req/min per IP via `slowapi` (PITFALL-05).
- **Next.js tracking page**: `/track/[token]` is a Server Component. Excluded from `middleware.ts` auth matcher. Fetches from `/api/v1/public/track/{token}`. Staleness indicator: if `position.recorded_at < now - 5min`, show amber badge "Posição desactualizada". Page must be under 50KB total (low-end Android browsers on shared mobile data — no heavy map library on the tracking page; text-format position only unless interactive map is explicitly requested).
- **ETA calculation**: GPS-03 — `GET /api/v1/trips/{id}/eta` computes estimated arrival using Haversine distance from `vehicle_last_position` to trip destination in `known_routes`, divided by `vehicle_last_position.speed_kmh`. Returns `null` when speed is 0 or position is stale. No PostGIS required — Haversine in Python is sufficient for < 200 vehicles.
- **Storage bloat prevention**: 50 vehicles at 30s intervals = 120,000 rows/day. Monthly partitions are mandatory from day one (PITFALL-07). ARQ cron `task_expire_gps_partitions()` drops partitions older than 90 days.

**Plans**: TBD

**UI hint**: yes

---

## Coverage Check (v2.0)

| Requirement | Phase | Category |
|-------------|-------|----------|
| CLI-01 | Phase 5 | Clients |
| CLI-02 | Phase 5 | Clients |
| CLI-03 | Phase 5 | Clients |
| CLI-04 | Phase 5 | Clients |
| CLI-05 | Phase 5 | Clients |
| PAY-01 | Phase 6 | Payments |
| PAY-02 | Phase 6 | Payments |
| PAY-03 | Phase 6 | Payments |
| AR-01 | Phase 7 | Accounts Receivable |
| AR-02 | Phase 7 | Accounts Receivable |
| AR-03 | Phase 7 | Accounts Receivable |
| AR-04 | Phase 7 | Accounts Receivable |
| INFRA-01 | Phase 8 | Infrastructure |
| INFRA-02 | Phase 8 | Infrastructure |
| INFRA-03 | Phase 8 | Infrastructure |
| RLS-01 | Phase 9 | Security |
| RLS-02 | Phase 9 | Security |
| RLS-03 | Phase 9 | Security |
| NOTIF-01 | Phase 10 | Notifications |
| NOTIF-02 | Phase 10 | Notifications |
| NOTIF-03 | Phase 10 | Notifications |
| ONBRD-01 | Phase 10 | Onboarding |
| DESP-01 | Phase 11 | Settlement |
| DESP-02 | Phase 11 | Settlement |
| DESP-03 | Phase 11 | Settlement |
| DESP-04 | Phase 11 | Settlement |
| DESP-05 | Phase 11 | Settlement |
| GPS-01 | Phase 12 | GPS |
| GPS-02 | Phase 12 | GPS |
| GPS-03 | Phase 12 | GPS |
| TRK-01 | Phase 12 | Tracking |
| TRK-02 | Phase 12 | Tracking |

**Total v2.0 requirements mapped: 32/32**

---

## Progress Table (v2.0)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Client Registry + Migration Foundation | 3/5 | In Progress|  |
| 6. Payment Registration | 0/TBD | Not started | - |
| 7. Accounts Receivable + Aging Dashboard | 0/TBD | Not started | - |
| 8. Infrastructure Hardening | 0/8 | Not started | - |
| 9. PostgreSQL RLS Policies | 0/TBD | Complete    | 2026-06-07 |
| 10. Notifications + Self-Service Onboarding | 0/TBD | Not started | - |
| 11. Driver Financial Settlement (Despacho) | 0/TBD | Not started | - |
| 12. GPS Integration + Customer Tracking Portal | 0/TBD | Not started | - |

---

---

# ROTAS — v3.0 Roadmap: TMS Enterprise Completo
_Last updated: 2026-06-18_

---

## Overview (v3.0)

**6 phases | 20 requirements | Milestone: Fechar todos os gaps críticos identificados na auditoria de 2026-06-18**

Esta milestona converte o ROTAS de um MVP técnico avançado numa plataforma TMS Enterprise completa e auditável. As lacunas foram identificadas por análise exaustiva de 43 migrações, 22 routers, 21 módulos e 2 frontends. As fases estão ordenadas por dependência e impacto de produção.

**Hard dependency chain**:
- Phase 14 (State Machines) → Phase 15 (Fiscal — DeliveryProof SM necessário para billing)
- Phase 14 (State Machines) → Phase 16 (HOS + Avail — vehicle availability depende de work order SM)
- Phase 13 + 14 + 15 → Phase 18 (Analytics precisa de dados correctos das SMs)
- Phase 17 (Infra v2) — sem dependências, pode correr em paralelo com Phase 13

**Parallel external actions during Phase 13**:
- Confirmar PostGIS disponível no Railway (necessário para eventual Geofencing v4)
- Verificar requisitos AT Moçambique para numeração de faturas (FISC-01)

---

## Phases (v3.0)

- [x] **Phase 13.5: Workshop Operations Expansion** — Staff de oficina (atribuição + custo mão de obra), ferramentas com histórico de calibrações, peças serializadas e timeline unificada de veículo
 (completed 2026-06-19)
- [ ] **Phase 13: Frontend Completeness** — As 4 páginas do manager referenciadas no sidebar mas sem implementação real: `/manutencao`, `/cobranca`, `/alertas`, `/settings`
- [ ] **Phase 14: Domain State Machines** — Fechar state machines incompletas de `BillingDocument`, `Contract`, `DeliveryProof` e `DispatchClearance` — o núcleo financeiro e documental fica coerente
- [ ] **Phase 15: Fiscal Compliance + Segurança de Carga** — IVA Moçambique, numeração fiscal, validação de peso vs capacidade, suporte hazmat
- [ ] **Phase 15.1: Documentos Fiscais Completos** — Estender billing_documents com document_type (invoice/debit_note/credit_note/invoice_receipt/receipt/proforma) e parent_document_id; criar Nota de Débito, Nota de Crédito, Fatura-Recibo e Recibo; AR básico com due_date e aging
- [ ] **Phase 16: HOS + Availability** — Driver Hours of Service and vehicle/driver availability calendar
- [x] **Phase 17: Enterprise Infrastructure v2** — Distributed rate limiting, structured logging, Prometheus metrics, advanced worker heartbeat (completed 2026-06-18) (completed 2026-06-19)
- [ ] **Phase 18: Analytics + Insurance** — Client profitability, insurance management, deep BI layer
- [ ] **Phase 19: Customs/Border Crossing** — Workflows for cross-border routes, documentation, and border dispatch
- [ ] **Phase 20: Route Optimization** — Distance matrix, waypoint sequencing, integration with routing providers
- [ ] **Phase 21: Frontend E2E Tests** — Playwright E2E testing suite to prevent visual and functional UI regressions
- [x] **Phase 22: RBAC Permission-Based** — Refactor do sistema de roles e permissões: dois planos (platform vs tenant), roles em português com agregados de gestão e operacional, `require_permission()` granular por domínio, `tenant_roles` custom para owner/director, migração dos 174 call sites de `require_roles` (completed 2026-06-20)
- [x] **Phase 23: Third Party Registry** — Fornecedores e prestadores externos como entidades estruturadas; elegibilidade operacional de motoristas calculada em tempo real; atribuição motorista-viatura com histórico temporal; documentos com validade rastreada (completed 2026-06-20)
- [ ] **Phase 24: Third Party Completion** — UI /terceiros no manager, supplier/service-provider pickers em abastecimentos e ordens de trabalho, sub-contactos, conta corrente de fornecedor, pagamentos a fornecedores, avaliação/scoring, idempotency keys, seed de províncias

---

## Phase Details (v3.0)

### Phase 13.5: Workshop Operations Expansion

**Goal**: Um gestor de oficina consegue atribuir tarefas a mecânicos com custo de mão de obra calculado automaticamente, registar calibrações de ferramentas com histórico completo, gerir peças serializadas (pneus, baterias) vinculadas ao veículo, e consultar um histórico cronológico unificado de todas as intervenções num veículo.

**Depends on**: Phase 4 (workshop base sólida — 18 endpoints + models existentes); Phase 04.1 (design system com `DataTable`, `StatusBadge`, `MonoCell` para UI da oficina)

**Requirements**: WSHOP-01, WSHOP-02, WSHOP-03, WSHOP-04, WSHOP-05

**Success Criteria** (what must be TRUE):
  1. Um gestor atribui uma tarefa a um mecânico com estimativa de 90 minutos; ao completar, o campo `labor_cost` do WorkOrder é atualizado automaticamente com base na taxa horária do mecânico — sem cálculo manual
  2. Uma ferramenta crítica com `calibration_due_at` a menos de 30 dias gera um `Alert` automático — a ferramenta não pode ser retirada para uso sem calibração válida
  3. Um pneu com número de série `MZ-TBB-2024-001` é registado, instalado num veículo e aparece em `GET /workshop/vehicles/{id}/installed-parts` com `status=installed` e `vehicle_id` correto
  4. `GET /api/v1/vehicles/{id}/history?types=maintenance,fuel` retorna eventos paginados em ordem cronológica de ambos os tipos com `event_type`, `event_date`, `title`, `reference_id` e `odometer_reading` preenchidos
  5. A página `/manutencao` exibe 4 tabs funcionais; `/viaturas/[id]/historico` renderiza a timeline com filtros por tipo de evento

**Architecture constraints**:
- Todos os novos campos em tabelas existentes adicionados por `ALTER TABLE` (nunca DROP/RECREATE)
- Três novas tabelas: `workshop_staff_rates`, `tool_calibrations`, `spare_part_serial_items` — cada uma com RLS + GRANT na mesma migração (padrão v2.0 obrigatório)
- `labor_cost` em `work_orders` é **acumulado** em cada task completion — nunca recalculado em batch; campo separado de `actual_cost` (que é custo de peças)
- Role `mechanic` adicionado ao enum de roles existente — permissões: escrita em workshop (WOs, tasks, ferramentas, peças); sem acesso a billing/contratos/configurações de tenant
- Vehicle history endpoint usa UNION ALL com query separada por entidade + ORDER BY `event_date DESC` no exterior — nunca JOINs em N entidades (performance)
- Cursor pagination por `event_date + id` (par único) — não por offset (resultados instáveis com inserts concorrentes)
- Peças serializadas (`spare_part_serial_items`) geram `SparePartMovement` direction=`out` quando instaladas — manter rastreabilidade de stock

**Implementation Notes**:
- **WSHOP-01 (Staff)**: `WorkOrderTask` recebe `assigned_to UUID nullable FK → users.id`, `estimated_minutes INT`, `actual_minutes INT`. `WorkOrder` recebe `labor_cost Numeric(14,2) DEFAULT 0`. Nova tabela `workshop_staff_rates`: `id`, `tenant_id`, `user_id UUID FK → users.id`, `hourly_rate Numeric(10,2)`, `effective_from DATE`, `created_at`. Service `assign_task_to_mechanic(task_id, user_id, estimated_minutes, db)` + extensão de `complete_task()` que lê rate ativa e acumula `labor_cost`. Endpoint `PATCH /workshop/work-orders/{wo_id}/tasks/{task_id}` (atribuição + estimativa). Endpoint `GET /workshop/kpis` adiciona `total_labor_hours`, `total_labor_cost`, `work_orders_by_mechanic` ao payload existente.
- **WSHOP-02 (Ferramentas)**: `WorkshopTool` recebe: `category VARCHAR(40)`, `location VARCHAR(120)`, `serial_number VARCHAR(80)`, `purchase_date DATE`, `purchase_cost Numeric(10,2)`, `calibration_interval_days INT`. Nova tabela `tool_calibrations`: `id`, `tenant_id`, `tool_id FK`, `calibrated_by UUID`, `calibrated_at TIMESTAMPTZ`, `next_due_at TIMESTAMPTZ`, `notes TEXT`, `created_at`. Service `record_tool_calibration()` cria registo + atualiza `workshop_tools.calibration_due_at`. Alerta automático via `ensure_exception()` quando `calibration_due_at < NOW() + INTERVAL '30 days'` e `is_critical=true`. Endpoint `PATCH /workshop/tools/{id}` permite atualizar status, location, calibration_interval_days.
- **WSHOP-03 (Peças Serializadas)**: `SparePartInventory` recebe: `category VARCHAR(40)` (enum: `filtro/pneu/bateria/correia/outro`), `shelf_location VARCHAR(80)`, `supplier_name VARCHAR(160)`, `lead_time_days INT`, `reorder_quantity INT`. Nova tabela `spare_part_serial_items`: `id`, `tenant_id`, `part_id FK → spare_parts_inventory.id`, `serial_number VARCHAR(120)`, `status VARCHAR(30)` (enum: `in_stock/installed/scrapped`), `vehicle_id UUID nullable FK`, `installed_at TIMESTAMPTZ`, `scrapped_at TIMESTAMPTZ`, `notes TEXT`, `created_at`. Instalação cria `SparePartMovement` com `direction=out`, `movement_type=serial_install`. `GET /workshop/spare-parts/low-stock`: `WHERE current_quantity <= minimum_quantity AND status='active'`.
- **WSHOP-04 (Vehicle History)**: Endpoint em `vehicles/router.py`: `GET /api/v1/vehicles/{vehicle_id}/history?from=&to=&types=&cursor=&limit=`. Service `get_vehicle_history()` em `vehicles/service.py` executa UNION ALL com 6 sub-queries (uma por entidade), filtra por `tenant_id + vehicle_id + date range`, ordena por `event_date DESC`. Cursor: base64-encode de `{event_date}|{id}`. Resposta: `{events: [...], next_cursor: str|null, total_count: int}`.
- **WSHOP-05 (UI)**: `apps/manager/app/manutencao/page.tsx` — adicionar `<Tabs>` do shadcn/ui com 4 painéis. `PartsInventoryTable.tsx`: colunas SKU / Nome / Stock / Mínimo / Custo Médio / Categoria / Localização + badge amber "stock baixo" (dot `::before`) quando `current_quantity <= minimum_quantity`. `ToolsTable.tsx`: colunas Código / Nome / Status / Calibração + badge vermelho quando `calibration_due_at < NOW() + 30d`. Página `/viaturas/[id]/historico/page.tsx`: timeline vertical com ícone por `event_type`, data ISO, título e link para entidade (`reference_id`).

**Plans**: 5 plans

Plans:
- [x] 13.5-01-PLAN.md — Wave 1: Alembic migration (3 new tables + ALTER TABLE additions + RLS + GRANT)
- [x] 13.5-02-PLAN.md — Wave 2: ORM models extension + Pydantic schemas for all new entities
- [x] 13.5-03-PLAN.md — Wave 3: Service layer (staff rates, calibration, serial parts, vehicle history) + 11 new endpoints
- [x] 13.5-04-PLAN.md — Wave 4: Frontend UI (PartsInventoryTable, ToolsTable, 4-tab /manutencao, /viaturas/[id]/historico)
- [x] 13.5-05-PLAN.md — Wave 5: Automated tests (23 tests across 4 new test files)

**UI hint**: yes

---

### Phase 13: Frontend Completeness

**Goal**: Um gestor que clica em qualquer entrada do sidebar chega a uma página funcional — sem ecrãs em branco ou redirects para a página principal.

**Depends on**: Phases 8 (workshop tem 26 endpoints, mas Infra/Sentry deve estar activo antes de expor novas páginas de produção), 04.1 (design system completo)

**Requirements**: FE-01, FE-02, FE-03, FE-04

**Success Criteria** (what must be TRUE):
  1. Gestor abre `/manutencao` e vê lista de work orders activos e preventivos da sua frota — dados reais do módulo workshop backend
  2. Gestor abre `/cobranca` e pode filtrar faturas por contrato, período e estado, emitir e descarregar PDF — sem aceder à página principal
  3. Gestor abre `/alertas` e vê alertas activos com acção de reconhecimento; alertas resolvidos desaparecem da lista imediatamente
  4. Gestor abre `/settings` e pode actualizar configurações de tenant, gerir utilizadores/roles e ver dispositivos de motoristas emparelhados

**Implementation Notes**:

- **`/manutencao`**: Next.js page Server Component; chama `GET /api/v1/workshop/work-orders` (já existe), `GET /api/v1/workshop/maintenance-plans` e `GET /api/v1/workshop/maintenance-schedule`. Três tabs: Work Orders Activos / Manutenções Preventivas / Inventário de Peças. Usa `WorkQueue` e `DataTable` do design system 04.1.
- **`/cobranca`**: Página dedicada separada do `page.tsx` principal. `BillingDocumentList` com filtros (`contract_id`, `status`, `period_start`, `period_end`). Acções inline: emitir, marcar pago (SM-01), download PDF/XLSX (ARQ export job com polling). Waiver modal reutilizado do Phase 3.
- **`/alertas`**: `AlertList` com `react-query` `refetchInterval: 30000`. Card por alerta com severity badge (amber dot para warning, vermelho para critical). Acção `PATCH /api/v1/alerts/{id}/acknowledge` — apenas owners/admins. Tabs: Activos / Reconhecidos / Resolvidos.
- **`/settings`**: Três secções — Tenant (PATCH `/api/v1/tenants/me`), Utilizadores (GET/POST/PATCH `/api/v1/users`), Dispositivos de Motoristas (`GET /api/v1/drivers` com `driver_devices`). Compliance policy toggle (exige documentos obrigatórios antes de viagem).
- **Sidebar update**: Adicionar entradas `Manutenção`, `Alertas` e `Definições` ao `SidebarLayout` nas secções correctas (Frota / Operações / Config). Verificar que todas as rotas estão excluídas do auth matcher apenas onde necessário.

**Plans**: TBD

**UI hint**: yes

---

### Phase 14: Domain State Machines

**Goal**: Nenhuma entidade financeira ou documental fica num estado inválido — `BillingDocument`, `Contract`, `DeliveryProof` e `DispatchClearance` têm state machines explícitas com transições auditadas e guards no service layer.

**Depends on**: Nothing (backend-only; pode iniciar em paralelo com Phase 13)

**Requirements**: SM-01, SM-02, SM-03, SM-04

**Success Criteria** (what must be TRUE):
  1. Um `BillingDocument` emitido com `due_date` passada é automaticamente marcado `overdue` pelo ARQ cron — sem intervenção manual; um PATCH `/billing/documents/{id}/mark-paid` transiciona para `paid` e regista o evento em audit log
  2. Um `Contract` expirado (`ends_at < today`) não pode receber novas viagens sem renovação explícita; PATCH `/contracts/{id}/renew` reactiva o contrato e regista a transição
  3. Uma `DeliveryProof` rejeitada por um gestor cria automaticamente um `operational_exception` do tipo `delivery_rejected` — a viagem permanece `pending_delivery_proof` e não pode ser faturada
  4. Um `DispatchClearance` recusado regista `rejection_reason` e notifica o criador via ARQ; escalation para owner/admin após SLA configurado sem resposta

**Implementation Notes**:

- **SM-01 (BillingDocument)**: Adicionar estados `paid` e `overdue` ao enum existente. ARQ cron `task_mark_overdue_billing_documents()` diário: `UPDATE billing_documents SET status='overdue', overdue_since_at=NOW() WHERE status='issued' AND due_date < NOW()`. PATCH endpoint `/billing/documents/{id}/mark-paid` requer `owner/admin`, registra `billing.document_paid` em audit log, actualiza `paid_at`. `cancelled` só disponível para `draft` ou `overdue` com justificação.
- **SM-02 (Contract)**: Adicionar campo `status` ao modelo `Contract` com enum `draft/active/paused/expired/terminated`. Migration: `ALTER TABLE contracts ADD COLUMN status VARCHAR DEFAULT 'active'`. PATCH `/contracts/{id}/status` com allowed transitions por role. ARQ cron `task_expire_contracts()`: marca `expired` quando `ends_at < NOW()`. Alerta de expiração criado 30/15/7 dias antes via módulo `alerts`.
- **SM-03 (DeliveryProof)**: Adicionar estado explícito ao modelo `DeliveryProof` — verificar se campo `status` já existe (tem `pending/validated/verified/rejected`). Adicionar `accepted` e `disputed` se necessário. PATCH `/cargo/delivery-proofs/{id}/accept` e `/reject`. Transição `rejected` → cria `operational_exception` automaticamente no mesmo service call. Transição `accepted` → verifica se `trip.contract_id` existe → actualiza `trip.billing_status = 'billable'`.
- **SM-04 (DispatchClearance)**: Adicionar `rejected` e `escalated` ao enum. `rejected` exige campo `rejection_reason` (NOT NULL). `escalated` disparado por ARQ task `task_escalate_pending_clearances()` quando `created_at + tenant.clearance_sla_hours < NOW()`. Notificação ARQ para `owner/admin` na escalação.
- **Todos os transitions**: Registados com `record_audit_log()` dentro da mesma transacção DB — padrão estabelecido no codebase. Transitions inválidas retornam `ApiError("invalid_state_transition", ..., 409)`.

**Plans**: TBD

**UI hint**: no

---

### Phase 15: Fiscal Compliance + Segurança de Carga

**Goal**: Uma fatura emitida pelo ROTAS tem número sequencial sem gaps, IVA discriminado à taxa correcta moçambicana e o peso da carga é validado contra a capacidade do veículo antes de cada viagem.

**Depends on**: Phase 14 (SM-01 BillingDocument completo antes de adicionar campos fiscais às faturas)

**Requirements**: FISC-01, FISC-02, FISC-03, LOAD-01, LOAD-02

**Success Criteria** (what must be TRUE):
  1. Um tenant ao emitir a sua primeira fatura recebe número `2026/0001`; a segunda recebe `2026/0002` — PostgreSQL SEQUENCE garante que não há gaps mesmo sob concorrência
  2. A fatura PDF inclui linha de subtotal, linha de IVA (17% ou 5% ou 0%) e linha de total com IVA — taxas seleccionáveis por billing item
  3. Relatório mensal de compliance exportado em XLSX lista todas as faturas com NUIT do cliente e valor de IVA — adequado para submissão à AT
  4. Tentativa de criar viagem com `cargo_weight > vehicle.max_payload_kg` retorna HTTP 409 com `payload_exceeded` — com detalhe de kg em excesso
  5. Viagem com carga hazmat exige declaração de `hazmat_class` e `un_number` antes de emissão de Load Permit

**Implementation Notes**:

- **FISC-01 (Sequência de faturas)**: PostgreSQL SEQUENCE `invoice_seq_{tenant_id}` criada no onboarding (PATCH `/api/v1/onboarding/register` service). `billing_documents.invoice_number VARCHAR(12)` adicionado por migration. Gerado em `create_billing_document()`: `SELECT nextval('invoice_seq_{tenant_id}')` e formatted como `f"{year}/{seq:04d}"`. UNIQUE constraint `(tenant_id, invoice_number)`. Retry em `IntegrityError` improvável mas necessário por segurança.
- **FISC-02 (IVA)**: Adicionar `iva_rate NUMERIC(5,4)` (e.g. `0.1700`) e `iva_amount NUMERIC(10,2)` a `billing_items` e `billing_documents`. `iva_rate` seleccionável por item: `standard` (0.17), `reduced` (0.05), `zero` (0.00). `billing_documents.tax_amount` (já existe) passa a ser calculado como `SUM(billing_items.iva_amount)`. PDF gerado por `fpdf2` actualizado para mostrar linha de IVA com % e valor.
- **FISC-03 (Compliance report)**: Novo endpoint `GET /api/v1/billing/compliance-report?month=YYYY-MM` — retorna job ID de ARQ export. ARQ task `task_export_compliance_report(month, tenant_id)` gera XLSX com colunas: `invoice_number`, `client_nuit`, `client_name`, `issued_at`, `subtotal`, `iva_rate`, `iva_amount`, `total_amount`, `status`. Usa padrão ARQ/ExportJob já estabelecido na Phase 3.
- **LOAD-01 (Peso vs capacidade)**: Adicionar `max_payload_kg NUMERIC(10,2)` ao modelo `Vehicle` (migration nullable). Service `create_trip()` e `start_trip()` verificam: `if trip.cargo_weight and vehicle.max_payload_kg and trip.cargo_weight > vehicle.max_payload_kg: raise ApiError("payload_exceeded", ...)`. Override por `admin/owner` com campo `payload_override_reason` (registado em audit log). UI: campo no formulário de veículo + warning visual no Control Tower quando viagem near-limit.
- **LOAD-02 (Hazmat)**: Adicionar `is_hazmat BOOLEAN DEFAULT FALSE`, `hazmat_class VARCHAR(10)`, `un_number VARCHAR(10)`, `hazmat_label VARCHAR(50)` a `trips` e `cargo_manifests`. Se `trip.is_hazmat = True`, `create_load_permit()` exige `hazmat_class IS NOT NULL` — senão `ApiError("hazmat_declaration_required", ..., 422)`. Alert criado automaticamente no `control_tower` quando viagem hazmat fica `in_progress`.

**Plans**: 6 plans

Plans:
- [ ] 15-00-PLAN.md — Wave 0: Test stubs (17 functions in test_fiscal_compliance.py + 2 in test_billing_export.py)
- [ ] 15-01-PLAN.md — Wave 1: Alembic DDL migration (all ADD COLUMN + per-tenant sequences) + ORM model updates
- [ ] 15-02-PLAN.md — Wave 2: LOAD-01 payload guard (create_trip, start_trip) + LOAD-02 hazmat guard + hazmat alert
- [ ] 15-03-PLAN.md — Wave 2: FISC-01 invoice sequence — _assign_invoice_number() + issue_document() integration
- [ ] 15-04-PLAN.md — Wave 2: FISC-02 IVA calculation + exporters.py PDF/XLSX IVA section update
- [ ] 15-05-PLAN.md — Wave 3: FISC-03 compliance report ARQ task + GET /billing/compliance-report endpoint

**UI hint**: yes (campos no formulário de viagem e veículo)

---

### Phase 15.1: Documentos Fiscais e Operacionais

**Goal**: Completar o ciclo documental do ROTAS — documentos fiscais (Nota de Débito, Nota de Crédito, Fatura-Recibo, Recibo, AR básico) e documentos operacionais do transporte moçambicano (Guia de Remessa, Carta de Porte Internacional, DAV/INATTER, checklist por tipo de viagem).

**Depends on**: Phase 15 (IVA e numeração fiscal já implementados)

**Requirements**: FDOC-01, FDOC-02, FDOC-03, FDOC-04, FDOC-05, OPDOC-01, OPDOC-02, OPDOC-03, OPDOC-04, OPDOC-05

**Success Criteria** (what must be TRUE):

  1. `POST /billing/documents/{id}/debit-note` cria Nota de Débito com `invoice_number` sequencial e `parent_document_id` definido
  2. `POST /billing/documents/{id}/credit-note` cria Nota de Crédito; documento pai inalterado
  3. `POST /billing/documents/{id}/invoice-receipt` transita pai para `paid` e cria Fatura-Recibo
  4. `GET /billing/ar?aging_bucket=31_60` retorna apenas documentos com `days_overdue` entre 31 e 60 dias
  5. `POST /cargo/trips/{id}/guia-remessa` cria `transport_document` e retorna URL de PDF
  6. `POST /cargo/trips/{id}/carta-porte` cria CPI com `border_post` e `country_destination` em `extra_fields`
  7. `GET /cargo/trips/{id}/document-checklist` retorna documentos obrigatórios correctos: 4 para viagem nacional, 5+ para internacional
  8. Todos os endpoints filtram por `tenant_id` — testes de isolamento cross-tenant passam

**Implementation Notes**:

- **FDOC-01**: `ALTER TABLE billing_documents ADD COLUMN document_type VARCHAR(30) NOT NULL DEFAULT 'invoice'`, `ADD COLUMN parent_document_id UUID REFERENCES billing_documents(id)`, `ADD COLUMN due_date DATE`, `ADD COLUMN client_nuit VARCHAR(20)`. Tabela já tem RLS.
- **FDOC-02/03**: `create_debit_note()` e `create_credit_note()` chamam `_assign_invoice_number()` do FISC-01 — Notas de Débito e Crédito também recebem número sequencial fiscal. Parent deve ter `status IN ('issued', 'paid')`.
- **FDOC-04**: `create_invoice_receipt()` faz `UPDATE billing_documents SET status='paid', paid_at=now()` no parent E cria novo documento `invoice_receipt` ligado por `parent_document_id`. `create_receipt()` cria `receipt` sem alterar o parent (pagamento parcial).
- **FDOC-05**: `days_overdue` e `aging_bucket` são **campos calculados em runtime** (não colunas na BD) — adicionados ao `serialize_billing_document()`. `GET /billing/ar` filtra por `status='issued' AND due_date IS NOT NULL` ordenado por `due_date ASC`.
- **OPDOC-01**: `ALTER TABLE transport_documents ADD COLUMN extra_fields JSONB`, `ADD COLUMN recipient_nuit VARCHAR(20)`. Tabela já tem RLS — sem nova migração RLS necessária.
- **OPDOC-02 (Guia de Remessa)**: PDF via `fpdf2` (mesmo padrão que faturas). Campos obrigatórios: `client_name` (remetente), `recipient_name`, `origin`, `destination`, `document_number`. `extra_fields = {cargo_description, package_count, gross_weight}`.
- **OPDOC-03 (CPI)**: `extra_fields = {border_post, country_destination, sadc_cpi_number, consignee_name, consignee_nuit}`. PDF bilingue PT/EN.
- **OPDOC-04 (DAV)**: Registo digital da guia física emitida pelo INATTER. `extra_fields = {authorization_code, inatter_office, valid_routes}`. Sem geração de PDF (documento físico externo).
- **OPDOC-05 (Checklist)**: Endpoint calculado — sem nova tabela. Lógica: `trip.destination` internacional (fronteira) → exige CPI. `cargo_manifests.is_hazmat=true` → exige `declaracao_carga_perigosa`.

**Plans**: 9 plans

Plans:
- [ ] 15.1-01-PLAN.md — Wave 0: Test stubs for all FDOC/OPDOC requirements
- [ ] 15.1-02-PLAN.md — Wave 1A: DDL — billing_documents extension (FDOC-01)
- [ ] 15.1-03-PLAN.md — Wave 1B: DDL — transport_documents extension (OPDOC-01)
- [ ] 15.1-04-PLAN.md — Wave 2A: Nota de Débito + Nota de Crédito (FDOC-02, FDOC-03)
- [ ] 15.1-05-PLAN.md — Wave 2B: Fatura-Recibo, Recibo + AR endpoint (FDOC-04, FDOC-05)
- [ ] 15.1-06-PLAN.md — Wave 3A: Guia de Remessa (OPDOC-02)
- [ ] 15.1-07-PLAN.md — Wave 3B: Carta de Porte Internacional + DAV/INATTER (OPDOC-03, OPDOC-04)
- [ ] 15.1-08-PLAN.md — Wave 3C: Document Checklist per Trip (OPDOC-05)
- [ ] 15.1-09-PLAN.md — Wave 4: Implement tests + full suite validation

**UI hint**: no (backend + endpoints only; UI na fase seguinte de design)

---

### Phase 16: Hours of Service + Availability Router

**Goal**: Um gestor sabe em tempo real quantas horas um motorista conduziu hoje e esta semana — e o módulo `availability` finalmente tem endpoints que o dashboard pode consumir.

**Depends on**: Phase 14 (work order state machine necessária para `availability` de veículos ser precisa)

**Requirements**: HOS-01, HOS-02, AVAIL-01, AVAIL-02

**Success Criteria** (what must be TRUE):
  1. `GET /api/v1/availability/drivers` retorna lista de motoristas com status actual (`driving`, `resting`, `available`, `hos_violation`) e horas acumuladas hoje e esta semana
  2. `GET /api/v1/availability/vehicles` retorna lista de viaturas com status (`in_trip`, `in_maintenance`, `available`) e `available_at` estimado quando em manutenção
  3. Um motorista com 9h+ de condução no dia actual não pode ser atribuído a nova viagem sem override de `admin` com justificação em audit log
  4. Um veículo com `work_order` activo em estado `in_progress` é marcado `in_maintenance` — não pode receber nova atribuição de viagem

**Implementation Notes**:

- **HOS-01 (Cálculo de horas)**: Novo serviço `hos_service.py` em `backend/app/modules/drivers/`. Função `calculate_driving_hours(driver_id, date, db)`: query `trips WHERE driver_id=X AND actual_departure::date = date AND status IN ('in_progress','completed')`, soma `(actual_arrival - actual_departure) - SUM(trip_stops.duration WHERE stop_type='pernoite')`. Arredondamento para baixo em segundos convertidos para horas. Exposto no scorecard do motorista (campo adicional).
- **HOS-02 (Alertas e bloqueio)**: ARQ cron `task_check_hos_violations()` diário às 06:00 Africa/Maputo: para cada driver activo calcula horas dia e semana; se `> 9h day OR > 48h week`, cria `Alert` tipo `hos_violation`. `create_trip()` service verifica HOS antes de atribuição — se violação activa, retorna `ApiError("hos_violation_active", ..., 409)` com `{override_required: true}`. Override via campo `hos_override_reason` (requer `admin/owner`).
- **AVAIL-01 (Router de availability)**: Registar `availability` router em `main.py` e `database.py` MODEL_MODULES (actualmente o módulo existe mas não está registado — gap crítico identificado na auditoria). Implementar `GET /api/v1/availability/drivers?status=&limit=&offset=` e `GET /api/v1/availability/vehicles?status=&limit=&offset=`. Dados agregados de `trips`, `work_orders` e `driver_devices`. Cache Redis TTL 30s (mesmo padrão do Control Tower).
- **AVAIL-02 (Workshop integration)**: `create_trip_order()` e `assign_driver_vehicle()` verificam: `active_work_order = db.query(WorkOrder).filter(vehicle_id=X, status='in_progress').first()`. Se existe: `ApiError("vehicle_in_maintenance", ..., 409)` com `{work_order_id, expected_completion: work_order.estimated_completion_at}`. `GET /api/v1/vehicles/{id}` adiciona campo `availability` com `status` e `work_order_summary`.

**Plans**: TBD

**UI hint**: yes (availability panel no Control Tower sidebar)

---

### Phase 17: Infrastructure Enterprise v2

**Goal**: O ROTAS funciona correctamente em Railway multi-worker, os logs são estruturados e pesquisáveis, métricas de latência são visíveis e health checks distinguem dependências saudáveis de falhas.

**Depends on**: Nothing (infra phase — pode correr em paralelo com Phases 13-16)

**Requirements**: INFRA2-01, INFRA2-02, INFRA2-03, INFRA2-04

**Success Criteria** (what must be TRUE):
  1. Um deploy Railway com 4 workers Gunicorn (já configurado Phase 4) tem rate limiting correctamente partilhado — um cliente que esgota o limite em Worker 1 é recusado em Worker 2 sem reinício de contador
  2. Cada request ao FastAPI produz uma linha de log JSON com `request_id`, `tenant_id`, `method`, `path`, `status_code`, `duration_ms` — visível no Railway Logs
  3. `GET /api/v1/health/deep` retorna `{"status": "ok", "db": "ok", "redis": "ok", "arq_worker": "ok"}` quando tudo está saudável — retorna HTTP 503 se qualquer componente falhar
  4. `/metrics` Prometheus expõe `http_requests_total`, `http_request_duration_seconds` (histogram com p50/p95/p99) e `active_tenants` — Grafana Cloud conectado ao endpoint

**Implementation Notes**:

- **INFRA2-01 (Redis rate limiting)**: Substituir `slowapi` `InMemoryRateLimiter` por `slowapi` com `RedisRateLimiter(redis_url=settings.redis_url)`. Instalar `redis[asyncio]>=5.0` (já em `pyproject.toml` potencialmente — verificar). Limites: `/auth/login` 10/min, `/driver-auth/pair` 10/min, `/api/v1/sync/batch` 60/min, `/api/v1/gps/webhook` 60/min por IMEI. Configurar `REDIS_URL` no Railway — usar a mesma instância Redis do ARQ worker.
- **INFRA2-02 (Structured logging)**: Adicionar `structlog>=24.0` a `pyproject.toml`. Configurar em `app/main.py` lifespan: `structlog.configure(processors=[...structlog.stdlib.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()])`. Middleware FastAPI adiciona `request_id` e `tenant_id` ao contexto `structlog` via `structlog.contextvars.bind_contextvars()`. Replace `print()` e `logging.info()` statements por `logger = structlog.get_logger()`. ARQ worker configura o mesmo `structlog` antes de iniciar event loop.
- **INFRA2-03 (Prometheus)**: Instalar `prometheus-fastapi-instrumentator>=7.0`. Em `main.py` lifespan: `Instrumentator().instrument(app).expose(app, endpoint="/metrics")`. Adicionar gauge custom `active_tenants` (count query com Redis cache TTL 300s). Railway: configurar scrape do Prometheus se Grafana Cloud disponível; senão, Railway Metrics é suficiente para MVP de monitoring.
- **INFRA2-04 (Health check profundo)**: Substituir `GET /health` existente por endpoint com checks reais: `db`: `await db.execute(text("SELECT 1"))` com timeout 2s; `redis`: `await redis.ping()` com timeout 1s; `arq_worker`: query `redis.get("arq:health:{worker_id}")` — ARQ worker actualiza esta chave cada 30s via heartbeat task. Retorna HTTP 200 se todos OK, HTTP 503 com detalhes dos componentes falhados. Registado em Railway como health check path.

**Plans**: TBD

**UI hint**: no

---

### Phase 18: Analytics Avançado + Gestão de Seguros

**Goal**: Um director de operações abre o dashboard e vê — numa única vista — as rotas mais rentáveis, os motoristas com melhor performance, os veículos com anomalias de consumo e as apólices a renovar.

**Depends on**: Phases 13, 14, 15 (dados correctos de state machines e compliance fiscal necessários para analytics serem fiáveis)

**Requirements**: ANA-01, ANA-02, ANA-03, INS-01, INS-02

**Success Criteria** (what must be TRUE):
  1. `/analytics` mostra custo por rota (top-10), margem bruta por contrato, NPS de entrega (% carga intacta vs danificada), top-5 motoristas por km e score — todos filtráveis por período
  2. Relatório de combustível XLSX exportável mostra consumo real vs target por veículo com desvio %  e evolução mensal de custo/litro
  3. Relatório de compliance documental PDF lista todos os documentos vencidos e a vencer em 30 dias — adequado para reunião de gestão quinzenal
  4. Um gestor regista apólice de seguro para um veículo — recebe alerta 30 dias antes da renovação sem qualquer acção manual
  5. Um sinistro é associado a um `trip_incident` existente — o registo inclui número de processo do seguro e estado de resolução

**Implementation Notes**:

- **ANA-01 (KPIs completos)**: Estender `GET /api/v1/analytics/kpis` existente com novos campos. Custo por rota: `GROUP BY (trips.origin, trips.destination)` com `SUM(total_transport_cost)/COUNT(*)`. Margem bruta: `(contract.unit_price * billing_items.quantity) - trip.total_transport_cost`. NPS entrega: `COUNT(delivery_proofs WHERE cargo_condition='intact') / COUNT(delivery_proofs) * 100`. Top-5 motoristas: já calculado no scorecard Phase 4 — agregar por período. Cache Redis TTL 300s (KPIs pesados, actualização menos frequente).
- **ANA-02 (Relatório combustível)**: Novo endpoint `GET /api/v1/analytics/fuel-report?month=YYYY-MM` → ARQ job `task_export_fuel_report`. Query: `SELECT vehicle_id, SUM(liters), SUM(total_cost), AVG(consumption_l_per_100km), vehicle.avg_consumption_target FROM fuel_logs JOIN vehicles GROUP BY vehicle_id`. Calcula `deviation_pct = (actual - target) / target * 100`. XLSX: linha por veículo, coluna por semana (evolução). Anomalia: `deviation_pct > 20%` destacado a vermelho via `openpyxl` cell fill.
- **ANA-03 (Compliance report)**: Novo endpoint `GET /api/v1/analytics/compliance-report` → ARQ job `task_export_compliance_pdf`. PDF com duas secções: (1) Documentos vencidos (hoje ou antes) por veículo/motorista; (2) A vencer nos próximos 30 dias. Usa `fpdf2 + DejaVuSans` (padrão estabelecido). Logo do tenant no cabeçalho. Paginação automática.
- **INS-01 (Apólices)**: Novo modelo `VehicleInsurance` em `backend/app/modules/vehicles/models.py` (ou sub-módulo `insurance`). Campos: `id`, `tenant_id`, `vehicle_id`, `policy_number`, `insurer`, `coverage_type` (enum: `civil_liability/comprehensive/cargo`), `premium_amount Numeric(10,2)`, `valid_from DATE`, `valid_until DATE`, `notes TEXT`, `created_at`. Migration com RLS policy + GRANT no mesmo ficheiro. Endpoints: CRUD em `/api/v1/vehicles/{id}/insurance`. ARQ cron de renovação: cria `Alert` 60/30/7 dias antes de `valid_until`.
- **INS-02 (Sinistros)**: Modelo `InsuranceClaim` com campos: `id`, `tenant_id`, `vehicle_id`, `insurance_id` (FK), `incident_id` (FK para `trip_incidents` nullable), `claim_number`, `claim_date DATE`, `estimated_damage Numeric(10,2)`, `status` (enum: `open/under_review/paid/rejected`), `resolved_at`, `notes`. Endpoints: CRUD em `/api/v1/vehicles/{id}/insurance/{insurance_id}/claims`. Status transitions auditadas. UI: tab "Sinistros" na página de detalhe de veículo.

**Plans**: TBD

**UI hint**: yes

---

## Coverage Check (v3.0)

| Requirement | Phase | Category |
|-------------|-------|----------|
| FE-01 | Phase 13 | Frontend |
| FE-02 | Phase 13 | Frontend |
| FE-03 | Phase 13 | Frontend |
| FE-04 | Phase 13 | Frontend |
| SM-01 | Phase 14 | State Machines |
| SM-02 | Phase 14 | State Machines |
| SM-03 | Phase 14 | State Machines |
| SM-04 | Phase 14 | State Machines |
| FISC-01 | Phase 15 | Fiscal |
| FISC-02 | Phase 15 | Fiscal |
| FISC-03 | Phase 15 | Fiscal |
| LOAD-01 | Phase 15 | Load Safety |
| LOAD-02 | Phase 15 | Load Safety |
| HOS-01 | Phase 16 | HOS |
| HOS-02 | Phase 16 | HOS |
| AVAIL-01 | Phase 16 | Availability |
| AVAIL-02 | Phase 16 | Availability |
| INFRA2-01 | Phase 17 | Infrastructure |
| INFRA2-02 | Phase 17 | Infrastructure |
| INFRA2-03 | Phase 17 | Infrastructure |
| INFRA2-04 | Phase 17 | Infrastructure |
| ANA-01 | Phase 18 | Analytics |
| ANA-02 | Phase 18 | Analytics |
| ANA-03 | Phase 18 | Analytics |
| INS-01 | Phase 18 | Insurance |
| INS-02 | Phase 18 | Insurance |

**Total v3.0 requirements mapped: 26/26**

### Phase 22: RBAC Permission-Based

**Goal:** Qualquer endpoint do backend verifica uma permissão granular (`trips.write`, `billing.read`, `fleet.admin`) em vez de um role string hardcoded. O owner ou director de um tenant pode criar roles custom com as permissões exactas que pretende. O plano de plataforma (operadores ROTAS) está completamente separado do plano de tenant.

**Requirements**: SEC-RBAC-01 a SEC-RBAC-05
**Depends on:** Phase 9 (RLS — os dois planos partilham infra de isolamento), Phase 13 (Frontend usa roles nos componentes de UI)
**Plans:** 3/3 plans complete

Plans:
- [ ] TBD (run /gsd:plan-phase 22 to break down)

---

### Phase 23: Third Party Registry

**Goal**: Suppliers and service providers are first-class tenant-managed entities in ROTAS; fuel purchases and workshop work orders can reference structured third parties via nullable FK; driver operational eligibility is computed in real time from existing Driver model fields; driver-vehicle assignments have a formal temporal history; documents have a structured model with expiry tracking.

**Depends on**: Phase 5 (clients module must exist — supplier/service_provider entities are distinct from clients and drivers which remain canonical), Phase 9 (RLS — new tables must follow RLS + GRANT pattern)

**Requirements**: TP-01, TP-02, TP-03, TP-04, TP-05, TP-06, TP-07, TP-08, TP-09, TP-10, TP-11

**Success Criteria** (what must be TRUE):
  1. A manager can register a fuel supplier as a third party with `role_type=supplier`, and that supplier can be selected when creating a `fuel_purchase` — `fuel_purchases.supplier_third_party_id` is populated; `supplier_name` still accepted as legacy fallback
  2. A manager can register an external workshop (oficina) as a third party with `role_type=service_provider`, and that provider can be referenced on a `work_order`
  3. `POST /api/v1/third-party-roles/{role_id}/eligibility/check` with a `driver` role returns `{"eligible": false, "reasons": [{"code": "driver_license_expired", "blocking": true}]}` when `Driver.license_valid_until` is in the past
  4. `POST /api/v1/trips` rejects with HTTP 409 when the assigned driver has a blocking eligibility reason — override requires `admin` role and `eligibility_override_reason` field
  5. `POST /api/v1/driver-vehicle-assignments` creates a temporal assignment record; a driver cannot have two active assignments simultaneously (unique partial index on `status=active`)
  6. A document with `expiry_date` uploaded to `operational_documents` for a driver or vehicle generates an alert 30 days before expiry — `alerts` table receives the entry
  7. `GET /api/v1/party-directory` returns a unified list of drivers, clients, and third_parties with `subject_type` discrimination, filterable by role and status, scoped to tenant
  8. All new tables (`third_parties`, `third_party_roles`, `supplier_profiles`, `service_provider_profiles`, `provinces`, `driver_vehicle_assignments`, `operational_documents`) have RLS policy and `GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app` in the same CREATE TABLE migration
  9. `clients` and `Driver` models are not modified — no third_party_id added to either; they remain canonical entities

**Architecture constraints**:
- `third_parties` stores identity (display_name, legal_name, primary_phone, tax_id optional, province_code, tags, record_status, tenant_id). `primary_phone` is unique per tenant for non-archived records.
- `third_party_roles` stores operational role per third party (role_type: supplier | service_provider, role_status: pending | active | suspended | blacklisted | archived, metadata JSONB with schema version).
- `supplier_profiles` and `service_provider_profiles` are separate profile tables linked to `third_party_roles.id` — not embedded in `third_party_roles`.
- `fuel_purchases.supplier_third_party_id` and `spare_parts_inventory.supplier_third_party_id` are nullable FKs — `supplier_name` (existing free-text) is retained as snapshot/fallback.
- `work_orders.service_provider_third_party_id` is a nullable FK — no existing column is removed.
- `OperationalEligibilityService` reads `Driver.license_valid_until`, `Driver.passport_valid_until`, `Driver.bi_valid_until`, `Driver.status` — no new Driver columns required.
- `operational_documents.file_id` → `files.id` — storage delegated to existing files module; no duplicate storage columns.
- `operational_documents.subject_type` enum: `driver | vehicle | third_party | client | contract`.
- `driver_vehicle_assignments` references `drivers.id` and `vehicles.id` — `trips.driver_id` is NOT changed.
- `PartyDirectoryService` uses UNION ALL query across `drivers`, `clients`, `third_parties` — not sequential API calls.
- All migrations are additive and backward-compatible — no existing FK is removed or renamed.
- Phase 22 (RBAC) not required as a hard dependency — this phase uses existing `require_roles(*DASHBOARD_ROLES)` pattern; RBAC masking of sensitive fields deferred.

**Plans**: TBD

**UI hint**: yes (party directory list, third party detail, eligibility badge on driver pages, assignment history)

---

---

### Phase 24: Third Party Completion — UI, Conta Corrente & Avaliação

**Goal**: O módulo de terceiros do ROTAS atinge paridade funcional com ERPs como PHC CS: qualquer gestor pode criar e gerir fornecedores e prestadores através do manager dashboard, os formulários de abastecimento e ordens de trabalho têm pickers estruturados, e existe conta corrente por fornecedor com registo de pagamentos e scoring de qualidade.

**Depends on**: Phase 23 (Third Party Registry — backend e tabelas já existem)

**Requirements**: TP2-01 a TP2-13

| ID | Descrição |
|----|-----------|
| TP2-01 | Sub-contactos por terceiro — tabela `third_party_contacts` com nome, função, telefone, email; múltiplos por terceiro |
| TP2-02 | Código de actividade/sector — campo `activity_code` + `sector` na ficha de terceiro |
| TP2-03 | Conta corrente de fornecedor — tabela `supplier_ledger_entries` com débitos (compras) e créditos (pagamentos); saldo calculado em tempo real |
| TP2-04 | Pagamentos a fornecedores — `POST /api/v1/third-party/{id}/payments`; ligação a `fuel_purchases` e `work_orders` como documentos de origem |
| TP2-05 | Avaliação de fornecedores — `supplier_evaluations` com critérios configuráveis (prazo, qualidade, preço); score médio exposto na ficha |
| TP2-06 | Idempotency keys nas mutações de terceiros — `Idempotency-Key` header em todos os POST/PUT do router de terceiros |
| TP2-07 | UI manager `/terceiros` — página de lista com filtros (tipo, estado, sector), detalhe com tabs (Info / Contactos / Documentos / Conta Corrente / Avaliações) |
| TP2-08 | Supplier picker no formulário de abastecimento (`/abastecimentos`) — combobox que substitui o campo de texto livre `supplier_name` quando existe terceiro |
| TP2-09 | Service provider picker nas ordens de trabalho — combobox no formulário de criação/edição de work order |
| TP2-10 | UI para documentos operacionais — upload e lista de documentos na tab Documentos do detalhe de terceiro e do perfil de motorista |
| TP2-11 | UI para driver-vehicle assignments — tabela de atribuições na página de detalhe de veículo e de motorista |
| TP2-12 | Migrations aplicadas + seed de províncias — `alembic upgrade head` documentado como step de deploy; seed script executado e verificado |
| TP2-13 | Múltiplos telefones/emails por terceiro — `third_party_contacts` também serve como modelo de contacto adicional (tipo: comercial, técnico, financeiro, emergência) |

**Success Criteria**:
1. `GET /terceiros` mostra lista paginada de terceiros com filtro por `role_type` e `status`
2. Criar um fornecedor via UI, abrir formulário de abastecimento — o campo supplier mostra o fornecedor criado no dropdown
3. `GET /api/v1/third-party/{id}/account` retorna saldo em aberto calculado como `sum(débitos) - sum(créditos)`
4. Registar pagamento a fornecedor via `POST /api/v1/third-party/{id}/payments` actualiza saldo da conta corrente
5. Submeter avaliação de fornecedor com 3 critérios — score médio aparece na ficha
6. Todos os POST do router de terceiros aceitam `Idempotency-Key`; duplo-submit com mesma key retorna 200 com resposta em cache
7. Upload de documento para terceiro via UI — documento aparece na tab Documentos com estado `pending`

**Architecture constraints**:
- `third_party_contacts` tem `tenant_id` + RLS + GRANT na mesma migration (v2.0 rule)
- `supplier_ledger_entries` tem `tenant_id` + RLS; `entry_type: debit|credit`; `source_type: fuel_purchase|work_order|manual`; `source_id UUID nullable`
- `supplier_evaluations` tem `tenant_id` + RLS; `criteria JSONB`; `score NUMERIC(4,2)`; `evaluated_by → users.id`
- Supplier picker no abastecimento é additive — `supplier_name` continua aceite como texto livre quando nenhum terceiro está seleccionado
- UI usa Manrope + IBM Plex Mono (valores monetários) + amber-500 (acções primárias) conforme DESIGN.md
- Saldo de conta corrente é calculado via query (não desnormalizado) — sem coluna de saldo que possa desincronizar

**Plans**: TBD — run `/gsd:plan-phase 24`

---

## Progress Table (v3.0)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 13. Frontend Completeness | 0/TBD | Not started | - |
| 14. Domain State Machines | 0/TBD | Not started | - |
| 15. Fiscal Compliance + Segurança de Carga | 0/TBD | Not started | - |
| 16. Hours of Service + Availability Router | 0/TBD | Not started | - |
| 17. Infrastructure Enterprise v2 | 2/2 | Complete    | 2026-06-19 |
| 18. Analytics Avançado + Gestão de Seguros | 0/TBD | Not started | - |
| 22. RBAC Permission-Based | 3/3 | Complete   | 2026-06-20 |
| 23. Third Party Registry | 8/8 | Complete | 2026-06-20 |
| 24. Third Party Completion — UI, Conta Corrente & Avaliação | 2/7 | In Progress|  |
