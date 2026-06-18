# Project Research Summary

**Project:** ROTAS v2.0 -- Plataforma Operacional Completa
**Domain:** Multi-tenant fleet management SaaS -- Mozambique logistics market
**Researched:** 2026-06-06
**Confidence:** HIGH (all findings grounded in direct codebase inspection + established patterns)

---

## Executive Summary

ROTAS enters v2.0 as a working data-collection platform that must evolve into a full operational platform with GPS fleet visibility, driver financial settlement, customer shipment tracking, and proactive notifications. Research confirms the existing FastAPI modular monolith is the correct foundation, and all v2.0 additions are strictly additive. Seven new library additions (sse-starlette >=3.4.4, itsdangerous >=2.2.0, aiosmtplib >=5.1.1, phonenumbers >=9.0.0, stripe >=15.2.0, sentry-sdk[fastapi] >=2.61.1, aiobotocore[boto3] >=3.7.0) are surgical and well-justified. The most significant structural work is RLS policy deployment, already 80% implemented in the codebase, requiring careful phasing to avoid breaking Alembic and the ARQ worker.

The recommended build order is dependency-driven. Infrastructure hardening (Sentry, R2/S3, tenant limits, RLS) must come before revenue-enabling features (onboarding, notifications), which must come before GPS-dependent features (customer portal). Four CRITICAL pitfalls identified: RLS SET vs SET LOCAL cross-tenant leak, Alembic blocked by RLS, settlement double-counting, and GPS webhook without tenant isolation. Each causes silent data corruption or financial errors if missed; each has a simple prevention.

The two longest external lead-time items -- WhatsApp Business API Meta approval and GPS device reconfiguration coordination with operators -- must begin immediately in parallel with the first implementation phases. Meta business verification takes 5-14 days; template approval adds 1-3 days per template. Teltonika/Coban devices may require physical reconfiguration that operators cannot do without installer credentials. Both block entire feature areas if not started now.

---

## Key Findings

### Stack Additions Confirmed for v2.0

The existing stack (FastAPI, SQLAlchemy 2, asyncpg, Dexie.js 4, Next.js 14, ARQ, Redis, fpdf2, openpyxl, PyJWT, slowapi) requires seven new backend packages and one required frontend package. All versions confirmed from PyPI as of 2026-06-06.

**New backend packages (add to pyproject.toml):**

| Package | Version | Purpose | Rationale |
|---------|---------|---------|-----------|
| sse-starlette | >=3.4.4 | SSE endpoint for real-time GPS push to manager dashboard | Simpler than WebSocket for read-only push; works through Vercel proxy |
| itsdangerous | >=2.2.0 | Signed tokens for customer portal URLs + email verification | Stateless; avoids a token DB table; Pallets project (high trust) |
| aiosmtplib | >=5.1.1 | Async SMTP for email fallback notifications | Does not block FastAPI event loop; smtplib would |
| phonenumbers | >=9.0.0 | Validate and normalize MZ phone numbers (+258) | Prevents silent WhatsApp API failures from malformed numbers |
| stripe | >=15.2.0 | Subscription plan management for self-service onboarding | Supports MZN, metered billing, hosted checkout; lowest-friction moment to wire |
| sentry-sdk[fastapi] | >=2.61.1 | Error tracking + SQLAlchemy slow query breadcrumbs | Auto-instruments FastAPI + SQLAlchemy; useful for Control Tower diagnosis |
| aiobotocore[boto3] | >=3.7.0 | Async R2/S3 file operations; replaces standalone boto3 | Async-safe; boto3 alone blocks event loop on upload/download operations |
| httpx | >=0.28.1 | WhatsApp API HTTP client (promote from dev to main deps) | Already installed; used for WhatsApp Business Cloud API calls from ARQ tasks |

**One replacement:** boto3>=1.43 in pyproject.toml must be replaced with aiobotocore[boto3]>=3.7.0. Do not keep both -- they conflict at the botocore layer.

**New frontend packages (apps/manager/):**

| Package | Purpose | Status |
|---------|---------|--------|
| @sentry/nextjs | App Router error tracking (server + client) | Required |
| leaflet + react-leaflet + @types/leaflet | Interactive map on customer portal | Optional -- only if interactive map required |

**Explicitly rejected:** GeoAlchemy2/PostGIS (Haversine in Python sufficient for < 200 vehicles), WebSocket (SSE sufficient for read-only GPS push), TCP socket listener for Teltonika Codec 8 (HTTP webhook mode eliminates the need), whatsapp-python SDK wrappers (httpx directly is more maintainable), Celery (ARQ already configured), Mapbox/Google Maps (Leaflet + OSM is free, avoids API key exposure).

---

### Features: Table Stakes vs Differentiators

**Must have -- table stakes for v2.0 launch:**

| Feature Area | Table Stakes |
|---|---|
| GPS Integration | Fleet map with last-known position per vehicle, refresh every 60s via polling |
| Driver Settlement (Despacho) | Advance issuance before departure, expense recording per trip, reconciliation calculation (advance minus approved expenses), settlement document PDF |
| Customer Portal | Token-based shareable link, delivery status page in Portuguese, text-only location, no login required |
| WhatsApp Notifications | Delivery confirmation to customer, document expiry alert to manager, settlement approved/disputed to driver |
| Self-Service Onboarding | Registration form with NUIT, email verification, 14-day trial, company setup wizard |
| Sync Conflict Resolution | Sync status badge in driver PWA (green/orange/red dot), manager conflict resolution queue |
| Tenant Limits | Hard limit enforcement at API level (403 with upgrade CTA), max_vehicles/max_drivers/max_users enforced in service layer |

**Should have -- differentiators for v2.0 quality:**

- GPS: Historical track replay, ETA calculation from known_routes + current speed
- Despacho: Per-expense approval/dispute workflow, multi-currency (MZN + ZAR), auto-import fuel costs from fuel_logs
- Customer portal: Live map on tracking page (requires GPS), WhatsApp link sharing from trip detail
- Notifications: ETA push updates, driver settlement notifications, driver compliance block alerts
- Onboarding: Soft limit warnings at 80% of plan, grace period on plan downgrade
- Conflict resolution: Auto-resolution rules for append-only entities (trip stops, checklist answers)

**Defer to v2.1+:**

- Geofencing (PostGIS decision needed; bounding-box SQL is the fallback if PostGIS unavailable on Railway)
- Automated billing via Flutterwave/Paystack (Mozambique gateway availability needs live verification)
- In-app driver to manager chat (WhatsApp deep-link is sufficient)
- Driver payroll integration (out of scope; this is trip expense settlement, not HR)
- Automatic FX rate fetching (no reliable free MZ-specific FX API; manager enters rate manually)
- TCP socket server for Teltonika Codec 8 (not feasible on Railway without dedicated infra)

**Mozambique-specific constraints shaping features:**

- OSM coverage outside Maputo/Beira/Nampula is sparse -- do not attempt route-based ETA outside major corridors
- Customer tracking page must be under 50KB total (low-end Android browsers on shared mobile data)
- Email fallback is required, not optional (WhatsApp penetration varies in rural areas)
- NUIT (9-digit tax ID) required on company registration for invoice issuance compliance
- Normalize all phone numbers to E.164 at input with phonenumbers library

---

### Architecture Approach

All nine v2.0 features integrate with the existing modular FastAPI monolith without structural changes. New features become new modules (gps/, tracking/, notifications/, onboarding/) or sub-modules within existing ones (trips/despacho.py). Session type discipline is the critical cross-cutting concern: get_session for authenticated endpoints (sets RLS tenant context), get_session_raw for unauthenticated endpoints (GPS webhook, public tracking, onboarding registration), admin engine via ADMIN_DATABASE_URL for ARQ cross-tenant jobs.

**New modules and responsibilities:**

| Module | Location | Responsibility |
|--------|----------|---------------|
| gps | backend/app/modules/gps/ | Webhook ingestion, position storage, device registration, HMAC auth, vehicle_last_position upsert table |
| tracking | backend/app/modules/tracking/ | Token generation/validation, public payload assembly for customers |
| notifications | backend/app/modules/notifications/ | Template management, notification log, ARQ task dispatch for WhatsApp + email |
| onboarding | backend/app/modules/onboarding/ | Public registration flow, tenant + owner creation in single atomic transaction |
| trips/despacho | backend/app/modules/trips/despacho.py | Advance lifecycle, settlement computation, approval workflow, PDF generation |

**Key architectural decisions confirmed by research:**

- GPS positions: dedicated append-only table with monthly PostgreSQL partitions + vehicle_last_position upsert table as the fast read path -- never query raw events table for live display
- Customer portal: public route /track/[token] in existing manager Next.js app, not a separate deployment -- excluded from auth middleware matcher
- Notifications: fire-and-enqueue pattern -- HTTP handler enqueues ARQ job and returns; delivery is async with 3-attempt exponential backoff (30s/5min/30min)
- ARQ worker: must use ADMIN_DATABASE_URL (BYPASSRLS role) for all cross-tenant scheduled tasks
- GPS fleet map: 10-second polling (React Query refetchInterval) for Phase 1; SSE upgrade in Phase 2

---

### Critical Pitfalls

Five most dangerous pitfalls -- causing silent data corruption, financial errors, or account suspension:

1. **RLS SET vs SET LOCAL causes cross-tenant data leak (PITFALL-01)** -- Using SET app.tenant_id instead of SET LOCAL persists the value on pooled asyncpg connections. The next request reusing that connection executes under the wrong tenant with no error raised. Prevention: verify database.py after_begin event uses SET LOCAL; write concurrent cross-tenant test as gate.

2. **R2 migration -- Railway ephemeral filesystem orphans existing files (PITFALL-14)** -- Delivery proofs and billing PDFs live on Railway ephemeral disk. Any deploy after enabling R2 loses them permanently. Prevention: run local-to-R2 migration script before enabling R2; keep dual-provider read logic active; verify zero storage_provider = local records before switching.

3. **Settlement double-counts TripCost expenses (PITFALL-03)** -- If the settlement module creates a parallel expense ledger instead of reading from trip_costs, the same fuel and toll entries appear twice. Prevention: settlement module sums trip_costs WHERE paid_by = driver -- never creates a second expense table.

4. **GPS webhook without tenant isolation (PITFALL-08)** -- GPS devices have no JWT. Without a gps_devices table with HMAC validation per IMEI, an attacker who knows a vehicle IMEI can inject fake positions. Prevention: every GPS event authenticated against device_secret before tenant_id and vehicle_id are resolved.

5. **WhatsApp Business account suspended from unconfirmed opt-ins (PITFALL-10)** -- Meta suspends accounts that send outbound messages to numbers without explicit opt-in. Recovery takes weeks. Prevention: add whatsapp_opt_in_confirmed: bool to Driver model and customer contact model; dispatch guard rejects sends to unconfirmed numbers.

Additional HIGH-priority pitfalls:
- PITFALL-02: Alembic blocked by RLS -- ALEMBIC_DATABASE_URL must use rotas_admin (BYPASSRLS); configure before any post-RLS migration
- PITFALL-04: Settlement race condition -- draft must re-read costs at finalization; optimistic lock on costs_reconciled_at
- PITFALL-07: GPS storage bloat -- 50 vehicles at 30s intervals = 120,000 rows/day; monthly partitions + vehicle_last_position required from day one
- PITFALL-09: WhatsApp template approval delays -- templates must be submitted 2 weeks before Phase 5-C begins
- PITFALL-11: Orphaned tenant from partial registration -- tenant + owner user must be created in single atomic transaction
- PITFALL-17: Dexie.js schema version not bumped -- any new sync entity stores require incrementing db.version()

---

## Implications for Roadmap

### Phase 5-A: Infrastructure Hardening

**Rationale:** Three internal, user-invisible items with no dependencies on each other. Build in parallel. They unblock everything that follows.

**Delivers:** Error visibility (Sentry), durable file storage (R2), plan limit enforcement (service guards).

**Features implemented:**
- Sentry SDK init in FastAPI, ARQ worker, Next.js manager app, and driver PWA -- with before_send PII scrubber and 5% traces_sample_rate in production
- R2/S3 file storage: implement storage.py dual-provider backend, run local-to-R2 migration script, verify zero local records before switching
- Tenant limits: _check_vehicle_limit() / _check_driver_limit() / _check_user_limit() guards in service create handlers; GET /api/v1/tenant/limits endpoint cached in Redis; limit banner in manager dashboard layout

**Pitfalls to prevent:** PITFALL-13 (Sentry PII scrubber on init), PITFALL-14 (R2 migration before deploy), PITFALL-19 (limits enforced before onboarding enabled)

**Research flags:** Standard patterns -- no phase research needed.

---

### Phase 5-B: PostgreSQL RLS Policies

**Rationale:** Standalone schema migration phase -- must not be combined with feature development. Failed RLS migration on 47+ tables can break all endpoints simultaneously. Must come before GPS because gps_positions needs a policy at creation time.

**Delivers:** Second isolation layer for all tenant data. Cross-tenant data leak becomes impossible at the database level.

**Features implemented:**
- Verify ALEMBIC_DATABASE_URL uses rotas_admin (BYPASSRLS) role before any migration runs
- Alembic migration: ENABLE ROW LEVEL SECURITY + FORCE ROW LEVEL SECURITY + CREATE POLICY rls_{table} for all 47 tenant-owned tables
- rotas_app and rotas_admin role creation in infra/docker-compose.yml and Railway DB init
- ARQ worker startup verified to use admin engine
- Cross-tenant isolation test suite passing under rotas_app role
- [During 5-B: draft and submit all 7 WhatsApp templates to Meta for approval]

**Pitfalls to prevent:** PITFALL-01 (SET vs SET LOCAL), PITFALL-02 (Alembic URL separation), PITFALL-15 (after_begin event instead of before_cursor_execute), PITFALL-16 (ARQ worker admin URL), PITFALL-20 (skip RLS on tables without tenant_id)

**Research flags:** RLS already 80% implemented in this codebase. No phase research needed. Confirm Railway PostgreSQL allows CREATE ROLE WITH BYPASSRLS in staging before the migration.

---

### Phase 5-C: Self-Service Onboarding + Notifications Infrastructure

**Rationale:** Co-dependent at launch -- welcome email is the first notification sent. Tenant limits (5-A) must be enforced before public registration enables. This phase enables public SaaS launch.

**Delivers:** Any Mozambican transportadora can self-register, get a 14-day trial, and receive a welcome email. Notification dispatch infrastructure ready for all subsequent features.

**Features implemented:**
- onboarding module: POST /api/v1/onboarding/register (atomic tenant + owner creation), email verification via itsdangerous, 14-day trial setup
- notifications module: notification_templates + notification_log tables, task_send_whatsapp and task_send_email ARQ tasks, retry policy (3 attempts, 30s/5min/30min backoff)
- phonenumbers library: E.164 normalization at input for all phone number fields
- stripe integration: webhook handler for subscription events (wire lifecycle now even if payment deferred to v2.1)
- Next.js public pages: /register, /register/verify, middleware exclusions
- whatsapp_opt_in_confirmed field on Driver model and customer contact model

**Pitfalls to prevent:** PITFALL-09 (templates submitted 2 weeks before this phase), PITFALL-10 (opt-in dispatch guard), PITFALL-11 (atomic registration transaction), PITFALL-12 (IntegrityError to ApiError slug_already_taken), PITFALL-22 (E.164 normalization at input)

**Research flags:** WhatsApp template approval is the critical path -- 7 templates must be submitted during Phase 5-B. Resolve 360dialog vs direct Meta Cloud API before planning. Verify Flutterwave Mozambique availability before committing to automated billing.

---

### Phase 5-D: Driver Financial Settlement (Despacho)

**Rationale:** Highest business-value feature independent of GPS. No external device coordination, no third-party API approval required. Depends only on notifications (5-C) for settlement alerts.

**Delivers:** Complete driver expense lifecycle -- advance before departure, expenses recorded offline, settlement computed and approved, PDF document generated.

**Features implemented:**
- driver_advances and trip_settlements tables (new, in trips module)
- trips/despacho.py: advance state machine (pending to disbursed to cancelled), compute_settlement() reading from trip_costs WHERE paid_by = driver, approval workflow
- trips/costs.py: extend reconcile_trip_costs() to include advance deduction in margin calculation
- ARQ tasks: task_generate_settlement_pdf, WhatsApp notification on advance issuance and settlement approval
- Dexie schema version bump for any new sync entity types (advance acknowledgment)
- Multi-currency (MZN + ZAR) with manager-entered exchange rate at reconciliation time

**Pitfalls to prevent:** PITFALL-03 (settlement reads trip_costs, never parallel ledger), PITFALL-04 (draft/finalize state machine + optimistic lock on costs_reconciled_at), PITFALL-17 (Dexie schema version increment required)

**Research flags:** Standard patterns -- no phase research needed. Settlement domain fully specified in FEATURES.md.

---

### Phase 5-E: GPS Integration + Customer Portal

**Rationale:** GPS has the most external dependencies (device reconfiguration), most infrastructure complexity (table partitioning, HMAC auth, vehicle_last_position upsert), and customer portal only reaches full value when GPS positions are available.

**Delivers:** Fleet map in manager dashboard, shareable customer tracking links with delivery status, ETA display when GPS data is available.

**Features implemented:**
- gps_positions table (monthly partitions, 90-day retention ARQ cron), gps_devices registration table with HMAC auth
- vehicle_last_position upsert table for fast fleet map reads
- POST /api/v1/gps/webhook/{imei} (no JWT, device HMAC auth, get_session_raw)
- GET /api/v1/gps/vehicles/latest (manager auth, RLS-scoped)
- GPS position added to serialize_vehicle() and Control Tower KPI payload
- 10-second polling fleet map in manager dashboard (React Query refetchInterval)
- tracking_tokens table, POST /api/v1/tracking-tokens (manager auth), GET /api/v1/public/track/{token} (no auth)
- Next.js /track/[token] page (Server Component, excluded from auth middleware), staleness indicator when position age > 5 minutes
- slowapi rate limiting: 30 req/min per IP on tracking endpoint, 60 events/min per IMEI on GPS webhook

**Pitfalls to prevent:** PITFALL-05 (128-bit token + rate limiting), PITFALL-06 (staleness indicator always returned), PITFALL-07 (monthly partitions + vehicle_last_position from day one), PITFALL-08 (HMAC auth before tenant lookup), PITFALL-18 (per-IMEI rate limiting + circuit breaker)

**Research flags:** Teltonika/Coban actual JSON payload schemas are MEDIUM confidence -- obtain device documentation from operators before implementing normalization. 1-day research task at Phase 5-E kickoff. Confirm PostGIS on Railway before any geofencing design.

---

### External Blockers -- Start Immediately (Parallel to Phase 5-A)

**WhatsApp Business API Meta Approval (4-6 week lead time):**
- Register ROTAS on Meta for Developers with a Mozambique business phone number
- Submit Facebook Business Manager business verification (5-14 day process)
- Draft all 7 message templates in Portuguese: trip_dispatched, delivery_completed, eta_update, document_expiring, settlement_approved, settlement_disputed, driver_blocked
- Submit templates during Phase 5-B execution (1-3 days per template; can be rejected)
- Choose BSP: 360dialog (recommended for launch) or direct Meta Cloud API

**GPS Device Operator Survey (2-4 week field coordination):**
- Survey each current operator: device model, firmware version, who has Teltonika Configurator access
- Determine which devices can be reconfigured to HTTP POST mode vs locked to third-party TCP server
- Get IMEI list from reconfigurable devices, coordinate configuration window with operators
- Assess whether any operators have Teltonika FOTA/FM accounts controlling device configuration

---

### Phase Ordering Summary

Phase 5-A: Infrastructure Hardening
  Sentry + R2/S3 + Tenant limits enforcement
  [Start immediately in parallel: WhatsApp Meta approval + GPS device operator survey]

Phase 5-B: RLS Policies
  47-table policy migration, role separation, cross-tenant test suite
  [Submit WhatsApp templates to Meta during this phase]

Phase 5-C: Onboarding + Notifications
  Self-service registration + ARQ notification infrastructure + WhatsApp/email dispatch
  [Requires: Meta templates approved, phonenumbers, Stripe wired]

Phase 5-D: Driver Settlement (Despacho)
  Advance -> expenses -> settlement -> PDF; offline sync entity types
  [Requires: notifications for settlement alerts]

Phase 5-E: GPS Ingestion + Customer Portal
  Webhook ingestion + fleet map + tracking tokens + public tracking page
  [Requires: GPS devices reconfigured, RLS on gps_positions table]

---

### Research Flags

**Phases needing dedicated research during planning:**

- **Phase 5-E (GPS):** Teltonika/Coban actual JSON payload schemas must be obtained from operators before implementing normalization layer. PostGIS on Railway needs confirmation before geofencing design. 1-day research task at kickoff.
- **Phase 5-C (Payments):** Flutterwave Mozambique live availability needs current confirmation. Manual bank transfer is the safe v2.0 fallback if unavailable.

**Phases with standard patterns (skip research-phase):**

- **Phase 5-A:** Sentry FastAPI init, aiobotocore R2 presign, service layer limit guards -- all standard, well-documented.
- **Phase 5-B:** RLS already 80% implemented in this codebase. Policy SQL is standard PostgreSQL.
- **Phase 5-D:** Settlement domain fully specified in FEATURES.md and ARCHITECTURE.md. TripCost model inspected and understood.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack additions | HIGH | All versions confirmed from PyPI index 2026-06-06; aiobotocore compatibility verified |
| Features -- table stakes | HIGH | Mozambican trucking settlement flow and SaaS onboarding patterns are well-established |
| Features -- GPS specifics | MEDIUM | Teltonika HTTP webhook mode is documented but firmware version affects JSON codec support; verify per-device |
| Architecture integration | HIGH | All findings from direct codebase inspection; session types, RLS ContextVar, ARQ wiring confirmed |
| Pitfalls -- RLS | HIGH | SET vs SET LOCAL, BYPASSRLS, after_begin event all confirmed in Phase 4 research with codebase verification |
| Pitfalls -- settlement | HIGH | costs.py code path inspected directly; paid_by field confirmed; reconcile call path confirmed |
| Pitfalls -- GPS | HIGH | Standard PostgreSQL time-series patterns; HMAC auth design is security-standard |
| WhatsApp Meta approval timeline | MEDIUM | Meta does not publish SLAs; 5-14 day estimate is approximate |
| Mozambique payment gateway | MEDIUM | Flutterwave MZ availability is training-data knowledge (cutoff Aug 2025); needs live verification |
| GPS device reconfigurability | LOW | Operator-specific; firmware version, installer access, existing server config unknown -- needs field survey |

**Overall confidence: HIGH** for architecture and implementation decisions. MEDIUM for external dependency timelines. LOW for operator-side GPS field conditions.

### Gaps to Address Before or During Phase Planning

1. **GPS device field survey (before Phase 5-E planning):** Without knowing which devices operators have and whether they can be reconfigured, the GPS scope is undefined. Worst case (TCP socket server) requires separate infrastructure not feasible on Railway.

2. **WhatsApp BSP selection (before Phase 5-C planning):** 360dialog vs direct Meta Cloud API affects the API integration pattern and pricing model. Must be decided before notification implementation begins.

3. **Flutterwave Mozambique live verification (before Phase 5-C planning):** If unavailable, manual bank transfer + invoice is the only safe v2.0 payment path.

4. **Mozambique e-fatura compliance (before billing goes live):** ROTAS issuing monthly SaaS subscription invoices to Mozambican companies may require AT digital invoice registration. Legal validation needed.

5. **PostGIS on Railway PostgreSQL (before Phase 5-E geofencing):** If unavailable, geofencing must use bounding-box SQL approximation. Affects schema design.

6. **Dexie.js sync scope for settlement (before Phase 5-D):** Determine which settlement entities need to be in the driver PWA sync queue. Defines the Dexie schema version bump scope.

---

## Sources

### Primary -- HIGH confidence (direct codebase inspection)

- backend/app/modules/trips/costs.py -- reconcile_trip_costs(), paid_by field, reconcile call path
- backend/app/modules/files/service.py -- storage_provider, local file path pattern
- backend/app/modules/tenants/models.py -- max_vehicles, max_drivers, max_users, whatsapp_number
- backend/app/modules/sync/service.py -- sync dispatch pattern, entity_type processing
- backend/app/database.py -- RLS ContextVar, after_begin event listener, get_session_raw pattern
- backend/app/config.py -- Settings, admin_database_url, alembic_database_url
- backend/app/main.py -- ARQ wiring, Redis wiring, module registration
- apps/driver/src/db.ts -- Dexie schema version 1 confirmed
- apps/manager/middleware.ts -- auth redirect scope
- .planning/phases/04-production-hardening-scale-preparation/04-RESEARCH.md -- RLS patterns D-17/D-18/D-19
- PyPI version index -- all package versions confirmed 2026-06-06

### Secondary -- MEDIUM confidence (established patterns, training knowledge)

- Teltonika FMB HTTP data sending mode -- documented non-enterprise path; firmware-version-dependent
- WhatsApp Business Cloud API v22.0 -- stable REST API, well-documented
- 360dialog Africa coverage -- Mozambique (+258) support needs live verification
- PostgreSQL declarative partitioning for time-series -- standard pattern, widely documented

### Tertiary -- LOW confidence (operator-specific, needs field validation)

- GPS device reconfigurability -- operator-dependent; firmware version and installer access unknown
- Flutterwave Mozambique current availability -- training data cutoff Aug 2025; live verification needed
- Mozambique e-fatura compliance for SaaS invoices -- legal domain; AT requirements not confirmed

---
*Research completed: 2026-06-06*
*Ready for roadmap: yes*