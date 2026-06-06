# ROTAS — MVP Roadmap
_Last updated: 2026-06-06_

---

## Overview

**4 phases | 27 requirements | Brownfield — codebase ~70% complete**

Phases are ordered by hard dependency: a security bypass is active (SEC-05), the backend cannot deploy to production safely, and the PWA has no Service Worker despite the sync logic existing end-to-end. The order reflects what must be TRUE before anything downstream can be trusted.

---

## Phases

- [ ] **Phase 1: Security Hardening + Deploy Foundation** — Close the active CVE, harden auth, and deploy the backend to a production environment
- [ ] **Phase 2: PWA Offline-First Completion** — Deliver the core product promise: driver app installs, works offline, syncs reliably
- [ ] **Phase 3: Manager Dashboard + Reporting Layer** — Turn ROTAS from a data-collection tool into an operational management platform
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
- [ ] 03-03-PLAN.md — Wave 1: CT-02 Redis cache-aside + ARQ worker scaffold + ExportJob model + migration (CT-02)
- [x] 03-04-PLAN.md — Wave 1: BILL-03 waiver workflow backend (POST /billing/waivers + approve/reject endpoints + RBAC) (BILL-03)
- [x] 03-05-PLAN.md — Wave 1: RPT-01 analytics KPI endpoint + RPT-02 document expiry endpoint (RPT-01, RPT-02)
- [ ] 03-06-PLAN.md — Wave 2: BILL-01 PDF (fpdf2 + DejaVuSans) + BILL-02 XLSX (openpyxl) + ARQ export jobs (BILL-01, BILL-02)
- [x] 03-07-PLAN.md — Wave 1: Tailwind v3 + shadcn@2.3.0 install in apps/manager + tailwind.config.ts + 10 components (D-01, D-02)
- [x] 03-08-PLAN.md — Wave 2: Migrate SidebarLayout + ControlTowerOverview + CostMarginBoard to Tailwind + /analytics nav entry (D-03, D-05)
- [ ] 03-09-PLAN.md — Wave 2: Migrate FleetComplianceBoard + BillingTripActions + FuelControlBoard + FleetHistoryBoard + Transport/Driver boards (D-03)
- [ ] 03-10-PLAN.md — Wave 3: Waiver modals + export job polling UI in BillingTripActions (BILL-01, BILL-02, BILL-03 frontend)
- [ ] 03-11-PLAN.md — Wave 3: /analytics page with KPI cards + driver summary + document expiry panel (RPT-01, RPT-02 frontend)
- [ ] 03-12-PLAN.md — Wave 4: Phase 3 verification checkpoint (all backend tests + frontend build + full UX verification)

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
| 1. Security Hardening + Deploy Foundation | 0/6 | Not started | - |
| 2. PWA Offline-First Completion | 0/8 | Not started | - |
| 3. Manager Dashboard + Reporting Layer | 0/12 | Not started | - |
| 4. Production Hardening + Scale Preparation | 0/9 | Not started | - |

---

---

# ROTAS — v2.0 Roadmap: Gestão de Clientes e Contas a Receber
_Last updated: 2026-06-06_

---

## Overview (v2.0)

**3 phases | 12 requirements | Milestone: Transform billing into a complete AR system**

Phase 5 is the highest-risk phase of the milestone: it carries a live data migration (client_name → client_id) across two tables and establishes the schema foundation everything downstream depends on. Phase 6 cannot start until Phase 5 has zero NULL client_id rows confirmed. Phase 7 requires both the client entity (Phase 5) and payment records (Phase 6) to produce meaningful AR totals.

The build order is determined by hard FK dependencies: clients must exist before payments can reference them, and payments must exist before aging can compute outstanding balances.

---

## Phases (v2.0)

- [ ] **Phase 5: Client Registry + Migration Foundation** — Clients become first-class entities; all existing contracts and invoices gain a client_id FK with zero data loss
- [ ] **Phase 6: Payment Registration** — Managers can record total and partial payments against invoices, including advance payments
- [ ] **Phase 7: Accounts Receivable + Aging Dashboard** — Client statements, aging buckets, AR KPIs, and PDF export complete the financial management loop

---

## Phase Details (v2.0)

### Phase 5: Client Registry + Migration Foundation

**Goal**: A manager can create, search, and manage clients as first-class entities — and every existing contract and invoice is automatically associated with the correct client, with no data loss and no manual re-entry required.

**Depends on**: Phase 4 (PostgreSQL RLS infrastructure must exist; Decimal type annotations must be clean; production deployment must be stable before a live data migration runs)

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

**Plans**: TBD

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

**Plans**: TBD

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

**Total v2.0 requirements mapped: 12/12**

---

## Progress Table (v2.0)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 5. Client Registry + Migration Foundation | 0/TBD | Not started | - |
| 6. Payment Registration | 0/TBD | Not started | - |
| 7. Accounts Receivable + Aging Dashboard | 0/TBD | Not started | - |
