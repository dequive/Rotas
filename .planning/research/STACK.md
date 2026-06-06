# Technology Stack — ROTAS v2.0

**Project:** ROTAS v2.0 — Plataforma Operacional Completa
**Researched:** 2026-06-06
**Scope:** New library additions only. Existing validated stack (FastAPI, SQLAlchemy 2, asyncpg, Dexie.js 4, Next.js 14, Vite, ARQ, Redis 7, fpdf2, openpyxl, PyJWT, slowapi, boto3) is NOT re-researched.

---

## Feature 1 — GPS Integration (Teltonika FMB, Coban TK103)

### How these devices communicate

Teltonika FMB series supports two data delivery mechanisms:
- **HTTP/HTTPS data sending**: device POSTs JSON (Codec 8/8E/16) to a configured endpoint every N seconds or on event trigger. This is the easiest integration — just add a FastAPI webhook endpoint.
- **TCP socket (proprietary Codec 8)**: device opens a persistent TCP connection to a server. Requires a separate TCP listener process. Significantly more complex — requires non-HTTP asyncio server, device authentication via IMEI, binary protocol parsing.

Coban TK103 supports HTTP polling or GPRS push to a custom server.

**Recommendation: HTTP webhook mode only for v2.0.** Configure all devices to use HTTP data sending. No new TCP listener needed. No extra library required beyond what already exists.

### GPS position storage

Do NOT add PostGIS or GeoAlchemy2 for v2.0. The overhead (PostGIS extension install on Railway PostgreSQL, migration complexity, geospatial query learning curve) is disproportionate for the use case: storing lat/lng history and serving last-known position. Plain `Numeric(9,6)` columns for latitude and longitude plus an append-only table with a `recorded_at` timestamp is sufficient. Railway PostgreSQL supports TimescaleDB-style partitioning via standard PostgreSQL PARTITION BY RANGE if needed later.

If geofencing is needed in v2.0, the Haversine formula in Python is adequate for expected fleet sizes (< 200 vehicles per tenant). GeoAlchemy2 is a Phase 3+ consideration if spatial indexing becomes a performance concern.

### Real-time position to manager dashboard

Use Server-Sent Events (SSE) rather than WebSocket. The control tower is read-only (server pushes, client never sends). SSE is simpler: no protocol upgrade, works through Vercel's reverse proxy, and `sse-starlette` integrates directly with FastAPI as a response class.

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `sse-starlette` | `>=3.4.4` | SSE endpoint for real-time position push to manager dashboard | Low |

**No new library needed for GPS webhook ingestion** — FastAPI handles JSON POST natively.

**No GeoAlchemy2 or PostGIS in v2.0** — plain Numeric columns, Haversine in Python.

### Redis pub/sub for GPS fan-out

When a GPS position arrives via webhook, it must be broadcast to all manager dashboard browser sessions watching that vehicle. Use Redis pub/sub: the webhook handler publishes to a channel `gps:{vehicle_id}`, and each SSE handler subscribes to that channel. The `redis[asyncio]` client is already declared in `pyproject.toml` (`redis>=7.4`). No new library needed.

### Installation

```bash
pip install "sse-starlette>=3.4.4"
```

### Integration complexity: Medium

The webhook receiver is low complexity. The complexity comes from: (1) device configuration — each Teltonika device must be reconfigured via Teltonika Configurator desktop tool (hardware work, not software); (2) the `gps_positions` table must have a write TTL strategy from day one to prevent unbounded growth (a `recorded_at` index + periodic delete of records older than 90 days via ARQ cron); (3) the SSE + Redis pub/sub fan-out pattern must handle subscriber cleanup on client disconnect.

---

## Feature 2 — Despacho Financeiro (Driver Cash Advance and Expense Reconciliation)

**No new libraries required.**

All needed capabilities already exist:
- `fpdf2>=2.8.7` already in use for billing PDFs — reuse for the settlement document PDF with full UTF-8 support for Mozambican names.
- `openpyxl>=3.1` already in use — reuse for XLSX export if needed.
- `Numeric(10,2)` migration pattern already established in project constraints.
- ARQ already configured for background export jobs (`billing/exporters.py` pattern).

The settlement document is a pure domain + PDF generation problem. The existing billing exporters are the template to follow.

### Integration complexity: Low

Pure backend domain work. No external API, no new library, no infrastructure change. The risk is data model design (advance state machine: requested → approved → disbursed → reconciled → settled) and ensuring all monetary columns use `Numeric(10,2)` from the start.

---

## Feature 3 — Customer Portal (Shareable Tracking Link, No Auth)

### Approach

A shareable link like `https://app.rotas.co.mz/track/[opaque-token]` renders a minimal page showing ETA and last known position.

**Option A: Next.js page in the existing manager app (recommended).** Add route `apps/manager/app/track/[token]/page.tsx`. This page is public (excluded from auth middleware). It calls a new FastAPI endpoint `GET /api/v1/track/{token}` that validates the token and returns sanitized position + ETA data. No new deployment, no new app.

**Option B: Separate Vite SPA** — rejected. Same Vercel deployment, extra build config, no benefit.

### Token generation for shareable links

Use `itsdangerous` for time-limited signed tokens. This avoids a tracking_tokens database table (stateless) while allowing expiry via TTL and revocation via secret rotation.

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `itsdangerous` | `>=2.2.0` | Time-limited signed tokens for shareable tracking URLs | Low |

`itsdangerous` is a Pallets project (same maintainer as Flask, Werkzeug). It is likely already installed as a transitive dependency — verify with `pip show itsdangerous`. If present, import without adding to `pyproject.toml`; if absent, add it.

### Map display in customer portal

Do NOT bundle Mapbox or Google Maps. The portal is a minimal read-only page. Options in order of preference:

1. **Static map tile** (`<img src="https://tile.openstreetmap.org/...">`) — zero JS, zero API key, sufficient for showing a pin on a map.
2. **Leaflet + react-leaflet** — if an interactive map (pan/zoom) is required. MIT license, no API key, OpenStreetMap free tiles.

```bash
# Only if interactive map is required
npm install leaflet react-leaflet @types/leaflet  # in apps/manager/
```

`react-leaflet` v4.x is compatible with React 18 and Next.js 14 App Router (requires dynamic import with `ssr: false`).

**Do NOT use Google Maps** (billing account + API key exposure). **Do NOT use Mapbox** (usage-based pricing, token in frontend).

### Installation

```bash
pip install "itsdangerous>=2.2.0"
```

### Integration complexity: Low

The stateless token pattern is a one-day implementation. Position data comes from the GPS module (Feature 1). The Next.js page is a read-only server component with a map embed. The only non-obvious requirement is excluding `/track/*` from the Next.js auth middleware matcher in `apps/manager/middleware.ts`.

---

## Feature 4 — Notifications (WhatsApp Business API and Email Fallback)

### WhatsApp Business API

**No dedicated Python SDK.** The WhatsApp Business Cloud API (Meta) is a REST API. Use `httpx` (already a dev dependency and likely a transitive runtime dependency) for async HTTP calls from within ARQ jobs. Wrapper libraries (`whatsapp-python`, `heyoo`) add dependency risk for a thin layer over 2-3 API calls.

Integration pattern:
1. Register WhatsApp Business account on Meta for Developers.
2. Get a permanent System User access token and Phone Number ID.
3. ARQ cron job calls `POST https://graph.facebook.com/v22.0/{phone-number-id}/messages` with a JSON body referencing a pre-approved template.

For document expiry alerts: the existing ARQ cron in `app/jobs/worker.py` is extended to query documents expiring in 30/7/1 days and dispatch messages.

**Ensure `httpx` is in runtime dependencies** (currently it is dev-only). Add `httpx>=0.28.1` to the main dependencies list in `pyproject.toml`.

### Phone number validation

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `phonenumbers` | `>=9.0.0` | Validate and format MZ phone numbers (+258) before sending | Low |

`phonenumbers` is Google's libphonenumber port for Python. It verifies a number is a valid Mozambique mobile number (Vodacom MZ: +258 84/85/86, Tmcel: +258 82/83, Movitel: +258 87) before attempting a WhatsApp API call. This prevents silent failures from malformed numbers stored in driver profiles.

### Email Fallback

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `aiosmtplib` | `>=5.1.1` | Async SMTP for email fallback notifications | Low |

Use `aiosmtplib` for async SMTP — the synchronous `smtplib` blocks the event loop. Send via SMTP credentials from Resend, SendGrid, or Mailgun (all provide SMTP, no SDK needed). Use Python's standard `email.mime` module for message construction; Jinja2 (likely already a transitive dependency) for templates.

### New env vars required

```
WHATSAPP_ACCESS_TOKEN=<meta-permanent-token>
WHATSAPP_PHONE_NUMBER_ID=<meta-phone-number-id>
SMTP_HOST=smtp.resend.com
SMTP_PORT=587
SMTP_USERNAME=resend
SMTP_PASSWORD=<api-key>
SMTP_FROM=noreply@rotas.co.mz
```

All must be added to `Settings` in `app/config.py` with `Field(validation_alias=...)`. In production validation, require SMTP settings when `ENVIRONMENT=production`.

### Installation

```bash
pip install "aiosmtplib>=5.1.1" "phonenumbers>=9.0.0"
# Also move httpx to main dependencies:
# httpx>=0.28.1  (currently dev-only)
```

### Integration complexity: Medium

The HTTP call to Meta's API is simple. The complexity is external process:
1. **Meta Business verification**: WhatsApp Business API access requires submitting business documents to Meta — 5 to 14 day external approval process. This is the longest lead-time item in v2.0. Start immediately.
2. **Message template approval**: WhatsApp requires pre-approved templates for outbound notifications (not session messages). Template approval takes 1-3 days per template.
3. **Rate limits**: Meta enforces per-phone-number tier limits and per-user 24-hour session windows.
4. **Mozambique WhatsApp penetration**: High in urban areas (Maputo, Beira, Nampula), low in rural areas. Email fallback is important, not optional.

---

## Feature 5 — Onboarding Self-Service (New Tenant Registration)

### No new backend libraries beyond email (aiosmtplib, already in Feature 4).

The flow is: landing page form → create tenant + owner user → email verification → plan selection → payment → dashboard access.

For plan selection and future payment, add Stripe now even if payment is deactivated in v2.0 MVP. This avoids a disruptive billing integration later when tenants have been onboarded manually and need to be migrated to subscriptions.

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `stripe` | `>=15.2.0` | Subscription plan management and payment processing | Medium |

**Why Stripe:** supports metered billing (per-vehicle pricing model fits ROTAS), supports MZN as presentment currency via international acquiring, provides hosted checkout that avoids PCI scope on ROTAS servers, has a mature Python SDK with async support.

**Why add in v2.0 even if payments are deferred:** the `Tenant` model already has `plan`, `max_vehicles`, `max_drivers`, `max_users` fields. Wiring them to Stripe subscriptions when they are freshly created (no historical tenants to migrate) is the lowest-friction moment.

### Email verification for self-registration

Use `itsdangerous` (already added in Feature 3) for time-limited verification tokens. Token is emailed to registrant; clicking the link validates and activates the tenant. Same pattern as password reset tokens.

### Frontend

New Next.js pages in the manager app: `/register`, `/register/verify`, `/register/plan`. These are public routes (excluded from auth middleware). No new frontend library — React state for form handling is sufficient at this scale.

### Installation

```bash
pip install "stripe>=15.2.0"
```

### Integration complexity: Medium

Tenant creation logic is simple (extends existing `tenants` module). Complexity is:
- Stripe webhook handling: `subscription.created`, `payment_failed`, `customer.subscription.deleted` → update tenant plan/status. Requires a FastAPI webhook endpoint with Stripe signature verification.
- Stripe requires HTTPS in production for webhook delivery — already required by Railway deployment.
- Local development: use `stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe` for testing.
- Idempotency: Stripe sends webhooks with retries — the handler must be idempotent (use the existing `idempotency_keys` table or Stripe's event ID as deduplication key).

---

## Feature 6 — Observabilidade (Sentry Error Tracking)

### Backend: FastAPI

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `sentry-sdk[fastapi]` | `>=2.61.1` | Error tracking, performance monitoring, SQLAlchemy slow query breadcrumbs | Low |

Use the `[fastapi]` extra — it installs the core SDK plus `FastApiIntegration` and `SqlalchemyIntegration`. The SQLAlchemy integration captures slow query breadcrumbs, which is directly useful for diagnosing the Control Tower's 38-query performance issue.

```python
# backend/app/main.py — add before app = FastAPI()
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,   # 10% of requests traced
        send_default_pii=False,   # GDPR: no PII in error reports
    )
```

Guard behind `if settings.sentry_dsn` so local dev without a DSN does not error.

### Frontend: Next.js Manager App

| Package | Purpose | Complexity |
|---------|---------|------------|
| `@sentry/nextjs` (latest) | Error tracking for App Router server components, API routes, and client-side | Low |

Use `@sentry/nextjs`, not generic `@sentry/react`. It handles Next.js App Router instrumentation including server components and edge runtime. Run `npx @sentry/wizard@latest -i nextjs` once to generate config files.

**Do NOT add `@sentry/react` separately** — `@sentry/nextjs` includes it.

### New env vars required

```
SENTRY_DSN=https://...@o0.ingest.sentry.io/...
NEXT_PUBLIC_SENTRY_DSN=https://...@o0.ingest.sentry.io/...
```

### Installation

```bash
# Backend
pip install "sentry-sdk[fastapi]>=2.61.1"

# Frontend (in apps/manager/)
npm install @sentry/nextjs
npx @sentry/wizard@latest -i nextjs
```

### Integration complexity: Low

Sentry has thorough FastAPI and Next.js App Router documentation. The init is 5 lines. Main decision is sampling rate — start at 10% for performance traces, 100% for errors. Do not set `traces_sample_rate=1.0` in production — at scale this generates significant Sentry bill.

---

## Feature 7 — File Storage (R2/S3 via aiobotocore)

### Current state

`boto3>=1.43` is installed (confirmed). `files/service.py` always uses `LOCAL_UPLOAD_PROVIDER` — the R2/S3 branch is not yet implemented despite the config scaffolding (`local_upload_dir` in Settings, `storage_provider` column on `File` model).

### Recommendation: aiobotocore[boto3] replacing standalone boto3

`boto3` is synchronous. Calling `boto3.client('s3').generate_presigned_url(...)` from a FastAPI async handler does not block (presigned URL generation is CPU-only, no network call). But server-side upload/download operations would block the event loop.

`aiobotocore>=3.7.0` is the async-native S3 SDK. It wraps the same botocore primitives with asyncio and is compatible with Cloudflare R2 (S3-compatible API).

**Critical compatibility note:** `aiobotocore` and `boto3` pin each other's versions at the botocore layer. Do NOT install both independently — they will conflict. Use the `[boto3]` extra to get a compatible pinned boto3:

```bash
pip install "aiobotocore[boto3]>=3.7.0"
```

This replaces the current standalone `boto3` entry in `pyproject.toml`. The presigned URL generation code in `files/service.py` is compatible — the presign API has not changed across boto3 versions.

| Library | Version | Purpose | Complexity |
|---------|---------|---------|------------|
| `aiobotocore[boto3]` | `>=3.7.0` | Async S3/R2 file operations; replaces standalone boto3 | Low |

### New env vars required

```
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=<key>
R2_SECRET_ACCESS_KEY=<secret>
R2_BUCKET_NAME=rotas-uploads
R2_PUBLIC_DOMAIN=https://files.rotas.co.mz   # optional CDN domain for public files
```

Add to `Settings` with production validation requiring `R2_ENDPOINT_URL` when `ENVIRONMENT=production`.

### Integration complexity: Low

Presigned URL pattern is already scaffolded. Work is: (1) add R2 config to Settings; (2) implement `r2_storage_provider` branch in `files/service.py` generating presigned PUT for upload and presigned GET for download; (3) an Alembic migration is not needed — the `storage_provider` column already exists. New files use R2; existing local files continue to serve from local storage until manually migrated.

---

## Feature 8 — RLS PostgreSQL (Row Level Security)

### No new libraries needed.

RLS is implemented entirely in PostgreSQL DDL (Alembic migrations). No Python library change.

### Implementation pattern

```sql
-- Per table (run for each of the 30+ tenant-owned tables)
ALTER TABLE vehicles ENABLE ROW LEVEL SECURITY;
ALTER TABLE vehicles FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON vehicles
    USING (tenant_id = current_setting('app.tenant_id', TRUE)::uuid);
```

The `TRUE` argument to `current_setting` makes it return NULL instead of raising an error when the setting is absent (used by the admin role which bypasses the policy anyway).

The FastAPI application sets `app.tenant_id` per request:

```python
# In database.py — called from get_session() after extracting tenant_id from JWT
async def set_rls_context(session: AsyncSession, tenant_id: str) -> None:
    await session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": str(tenant_id)})
```

`SET LOCAL` is transaction-scoped — it is automatically cleared when the transaction ends. This prevents leaking across pooled connections.

### Role separation (already established)

The `ADMIN_DATABASE_URL` and `ALEMBIC_DATABASE_URL` in `config.py` point to a `rotas_admin` role that has `BYPASSRLS`. This role is already used by the ARQ worker (`app/jobs/worker.py`) and Alembic. No new role setup needed — but it must be provisioned correctly in Railway's managed PostgreSQL (Railway does allow `CREATE ROLE` with `BYPASSRLS` on its PostgreSQL instances).

### Integration complexity: High

RLS is the highest complexity item in v2.0:
1. **Coverage**: 30+ tables across 21 modules. Every tenant-owned table needs a policy. Audit tables need a different policy (append-only, admin-only reads). Public tables (tenants, plans) need no RLS.
2. **Test suite**: All 18 existing test modules run as the app role. With RLS active, tests need `SET LOCAL app.tenant_id` in their setup fixtures or run as BYPASSRLS role. Retrofitting all tests is significant work.
3. **Railway verification**: Confirm Railway PostgreSQL allows `CREATE ROLE WITH BYPASSRLS` before committing to this approach.
4. **Performance**: `current_setting()` adds overhead on every query. Benchmark with realistic data volumes.
5. **ARQ worker correctness**: The worker already uses `ADMIN_DATABASE_URL` (BYPASSRLS), so cross-tenant jobs work correctly. This must be documented and enforced — any new worker function that should be tenant-scoped must use the normal URL + set tenant context.

**Dedicate a full standalone phase to RLS.** Do not combine with feature development.

---

## Feature 9 — Tenant Limits Enforcement

### No new libraries needed.

This is service-layer logic. The `Tenant` model already has `max_vehicles`, `max_drivers`, `max_users` integer fields.

Pattern (same for drivers, users):

```python
async def _enforce_vehicle_limit(db: AsyncSession, tenant_id: UUID) -> None:
    count = await db.scalar(
        select(func.count(Vehicle.id))
        .where(Vehicle.tenant_id == tenant_id, Vehicle.active.is_(True))
    )
    tenant = await db.get(Tenant, tenant_id)
    if tenant.max_vehicles and count >= tenant.max_vehicles:
        raise ApiError("vehicle_limit_reached", f"Plan allows {tenant.max_vehicles} vehicles.", 402)
```

**Critical**: the limit check must also be added to the sync batch processor in `backend/app/modules/sync/`. Drivers can be created via offline sync — if the limit is only enforced in the REST endpoints, a tenant can bypass it by creating drivers offline.

### Integration complexity: Low

Logic is trivial. Risk is incomplete coverage (sync processor, not just REST endpoints).

---

## Feature 10 — Gestão de Clientes e Contas a Receber

**Milestone:** v2.0 — Gestão de Clientes e Contas a Receber

### Backend: No new Python libraries required

All capabilities needed to build the client registry and accounts receivable module are already present in the stack:

| Capability | How it is covered | Library already present |
|------------|------------------|------------------------|
| UUID primary keys, tenant isolation | Standard SQLAlchemy 2 pattern | `sqlalchemy[asyncio]>=2.0` |
| Monetary precision (saldo, pagamentos) | `Numeric(12,2)` + `Mapped[Decimal]` — pattern established in billing module | Python stdlib `decimal` |
| Aging bucket calculation (30/60/90 days) | `(date.today() - invoice_date).days` — Python stdlib `datetime.date` | None |
| Client statement PDF | `fpdf2>=2.8.7` — DejaVuSans already handles full UTF-8 Portuguese/Mozambican names | `fpdf2>=2.8.7` |
| Client statement XLSX | `openpyxl>=3.1` — reuse billing exporter pattern | `openpyxl>=3.1` |
| Background export jobs | ARQ `ExportJob` pattern already in `billing/models.py` | `arq>=0.28` |
| Pydantic validation (NUIT regex, credit_limit) | Pydantic v2 `Field(pattern=r'^\d{9}$')` for NUIT; no external validator | `pydantic-settings>=2.2` (brings pydantic v2) |
| Idempotent payment registration | `idempotency_keys` table already in use for billing mutations | existing infra |

**Do NOT add `python-accounting`, `financetoolkit`, or any third-party accounting library.** Aging calculation is four integer comparisons. A full accounting library imposes a data model contract that conflicts with ROTAS's existing billing structure.

**Do NOT add `python-dateutil` for aging.** The relativedelta approach is needed for calendar-aware month arithmetic. For aging buckets, the requirement is simply days elapsed since `issued_at`: `(date.today() - invoice.issued_at.date()).days`. Python stdlib is sufficient and already used throughout the codebase (see `billing/domain.py`).

### Frontend: Two packages to add

#### 1. `@tanstack/react-table` — aging report table

The accounts receivable dashboard requires a sortable, filterable table showing outstanding invoices grouped by aging bucket. The existing manager app has no table library — all current tables are plain HTML or ad-hoc divs.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@tanstack/react-table` | `^8.21.3` | Headless table with sort/filter/grouping for aging report | Stable v8 (v9 is in beta as of 2026-06-06); headless = works with existing Tailwind/shadcn components; 14KB bundle |

**Use v8, not v9.** TanStack Table v9.0.0-beta.1 was released 2026-06-05 — too new for a production milestone. v8.21.3 is the stable release. Pin `^8.21.3` to stay on v8 patch channel.

The aging table needs:
- Column-level sorting (client name, amount due, days overdue)
- Row grouping by aging bucket (current, 1-30, 31-60, 61-90, >90)
- Column totals row (sum of each bucket)

All of this is native TanStack Table v8 capability. No additional plugin needed.

#### 2. `@tanstack/react-query` — data fetching for financial views

This package is listed in `CLAUDE.md` as part of the manager stack but is **absent from `apps/manager/package.json`**. The accounts receivable dashboard has multiple async data needs (client list, AR summary, statement) that benefit from query caching and background refetch. Add it now.

| Package | Version | Purpose | Why |
|---------|---------|---------|-----|
| `@tanstack/react-query` | `^5.101.0` | Server-state caching for AR dashboard data fetching | Already treated as present; v5 stable; prevents waterfall fetches in financial views |

**Note:** The existing billing components (`BillingTripActions.tsx`, board components) use direct `fetch` calls without caching. Adding react-query enables the AR dashboard to have optimistic updates on payment registration and stale-while-revalidate for the aging report — without refactoring existing components.

### Installation

```bash
# Frontend (in apps/manager/)
npm install @tanstack/react-table@^8.21.3 @tanstack/react-query@^5.101.0
```

No backend installation needed.

### Migration strategy: `contract.client_name` → `contract.client_id`

Both `contracts.client_name` (String 160) and `billing_documents.client_name` (String 160) must be migrated to FK references. This is a **three-step Alembic migration** — do NOT do it in a single migration:

**Step 1 — Create `clients` table, add nullable FK columns:**
```sql
CREATE TABLE clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(160) NOT NULL,
    nuit VARCHAR(9),           -- 9-digit tax number, optional (some clients are informal)
    ...
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE contracts ADD COLUMN client_id UUID REFERENCES clients(id);
ALTER TABLE billing_documents ADD COLUMN client_id UUID REFERENCES clients(id);
```
Both FK columns are nullable at this point. Deploy this migration. Old data continues to work via `client_name`.

**Step 2 — Backfill data migration:**
```sql
-- For each distinct (tenant_id, client_name) pair in contracts:
-- Insert one Client record, then update contract.client_id
INSERT INTO clients (id, tenant_id, name)
SELECT gen_random_uuid(), tenant_id, client_name
FROM contracts
WHERE client_name IS NOT NULL
GROUP BY tenant_id, client_name;

UPDATE contracts c
SET client_id = cl.id
FROM clients cl
WHERE cl.tenant_id = c.tenant_id AND cl.name = c.client_name;

UPDATE billing_documents bd
SET client_id = cl.id
FROM clients cl
WHERE cl.tenant_id = bd.tenant_id AND cl.name = bd.client_name;
```
This runs as a data migration inside the Alembic `upgrade()` function using `op.execute()`. One Client per distinct name per tenant. Names that were free-text strings become canonical client records.

**Step 3 — Enforce NOT NULL, add index (separate migration after validation):**
```sql
ALTER TABLE contracts ALTER COLUMN client_id SET NOT NULL;
ALTER TABLE billing_documents ALTER COLUMN client_id SET NOT NULL;
CREATE INDEX ix_contracts_tenant_client ON contracts (tenant_id, client_id);
CREATE INDEX ix_billing_docs_tenant_client ON billing_documents (tenant_id, client_id);
```
Only run this after verifying Step 2 left no NULLs in production. Keep `client_name` columns in place for the entire v2.0 release cycle — they serve as the human-readable denormalized cache and the rollback safety net. Remove them only in v3.0 after confirmed data integrity.

**Why three steps, not one:** A single migration that creates the table, backfills data, and enforces NOT NULL is a long-running transaction that locks the `contracts` and `billing_documents` tables. On Railway PostgreSQL, this will cause visible downtime for existing tenants. Separate migrations allow each step to complete and be verified independently.

### NUIT validation

NUIT (Número Único de Identificação Tributária) is Mozambique's tax number: exactly 9 numeric digits. Validate in the Pydantic schema — no external library:

```python
from pydantic import BaseModel, Field

class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    nuit: str | None = Field(default=None, pattern=r'^\d{9}$')
    credit_limit: Decimal | None = Field(default=None, ge=0)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
```

The `pattern=r'^\d{9}$'` validator is built into Pydantic v2 `Field`. No external NUIT library exists and none is needed.

### Aging bucket calculation

Pure Python, no library:

```python
from datetime import date
from decimal import Decimal

def aging_bucket(invoice_date: date, today: date | None = None) -> str:
    today = today or date.today()
    days = (today - invoice_date).days
    if days <= 0:
        return "current"
    elif days <= 30:
        return "1_30"
    elif days <= 60:
        return "31_60"
    elif days <= 90:
        return "61_90"
    else:
        return "over_90"
```

The service layer computes buckets in-process from query results — no SQL-level bucketing needed at this scale (each tenant has at most a few hundred open invoices at a time).

### AR Dashboard KPIs — Redis cache

The AR dashboard header shows total issued, total received, total open, and overdue amounts. These aggregate across all billing documents for the tenant. Use Redis (already provisioned, `redis>=7.4` already in `pyproject.toml`) to cache the KPI snapshot with a 5-minute TTL — same pattern recommended for Control Tower (CT-02):

```python
cache_key = f"ar_kpi:{tenant_id}"
# SET ar_kpi:{tenant_id} <json> EX 300
```

No new library. The `redis[asyncio]` client is already available.

### Integration complexity: Medium

The data model work (Client table, FK migration) is the highest-risk part — specifically Step 2 (backfill). Risk mitigation: run Step 2 in a transaction with an explicit rollback if any `client_id` remains NULL after the UPDATE. The domain logic (aging, balance calculation) is trivial. The frontend AR dashboard is the most time-consuming part: the aging table, payment registration modal, and client statement view are three separate UI components.

---

## Summary Table — New Additions to pyproject.toml

| Package | Version Constraint | Feature | Rationale |
|---------|-------------------|---------|-----------|
| `sse-starlette` | `>=3.4.4` | GPS real-time push | SSE simpler than WebSocket for read-only push; works through Vercel proxy |
| `itsdangerous` | `>=2.2.0` | Customer portal tokens + email verification | Stateless signed tokens; avoids token DB table |
| `aiosmtplib` | `>=5.1.1` | Email notifications | Async SMTP; does not block event loop |
| `phonenumbers` | `>=9.0.0` | WhatsApp number validation | Validates MZ mobile numbers (+258) before API call |
| `stripe` | `>=15.2.0` | Onboarding plan selection | Handles subscription lifecycle; available in MZ |
| `sentry-sdk[fastapi]` | `>=2.61.1` | Error tracking backend | Auto-instruments FastAPI + SQLAlchemy |
| `aiobotocore[boto3]` | `>=3.7.0` | R2/S3 async file storage | Async-safe; replaces standalone boto3 |
| `httpx` | `>=0.28.1` | WhatsApp API HTTP client | Move from dev to main dependencies |

**Feature 10 (Clientes e Contas a Receber): zero new backend packages.** All capabilities covered by existing stack.

**Note on boto3**: Replace `boto3>=1.43` in pyproject.toml with `aiobotocore[boto3]>=3.7.0`. Do not keep both.

**Total new backend packages: 7 (plus httpx promoted to main deps)**

## Summary Table — New Additions to apps/manager/package.json

| Package | Version | Feature | Rationale |
|---------|---------|---------|-----------|
| `@sentry/nextjs` | latest | Observabilidade | Official Next.js SDK; instruments App Router server + client |
| `@tanstack/react-table` | `^8.21.3` | AR aging report table | Headless table with sort/filter/grouping; stable v8 (v9 in beta) |
| `@tanstack/react-query` | `^5.101.0` | AR dashboard data fetching | Missing from package.json despite being in stack docs; needed for caching financial view data |
| `leaflet` + `react-leaflet` + `@types/leaflet` | latest | Customer portal map | Free tiles, no API key; only if interactive map required |

**Total new frontend packages: 3 required + 3 optional (Leaflet)**

---

## What NOT to Add

| Rejected Library | Reason |
|-----------------|--------|
| `GeoAlchemy2` / PostGIS | Overkill for v2.0; Haversine in Python + Numeric columns sufficient for fleets < 200 vehicles |
| `websockets` / `python-socketio` | SSE is sufficient for read-only GPS push; WebSocket adds protocol complexity with no benefit here |
| Teltonika TCP codec library | HTTP webhook mode eliminates the need; TCP listener is a separate server process (deploy risk) |
| `whatsapp-python` / `heyoo` | Thin wrappers over Meta REST API; `httpx` directly is more maintainable and avoids dependency risk |
| `celery` | ARQ already configured and deployed; two job queue systems is unnecessary complexity |
| `sendgrid` SDK / `mailgun` SDK | SMTP credentials from these providers work with `aiosmtplib`; no vendor SDK needed |
| `Mapbox GL JS` / `Google Maps JS API` | Cost, API key exposure in frontend, vendor lock-in; Leaflet + OpenStreetMap is free |
| Separate customer portal Vite app | Same Next.js app serves public `/track/*` route; separate app = unnecessary infra |
| `boto3` (standalone) | Replaced by `aiobotocore[boto3]` to avoid botocore version conflicts |
| `APScheduler` | ARQ cron already handles scheduled jobs; APScheduler is a third job scheduler |
| `python-accounting` | Full double-entry accounting library; imposes conflicting data model, overkill for aging + balance calc |
| `python-dateutil` / `relativedelta` | Calendar-aware month arithmetic not needed; aging uses `(today - date).days` which is Python stdlib |
| `financetoolkit` | DSO analytics package; no AR-specific features that justify the dependency |
| `@tanstack/react-table` v9 | In beta as of 2026-06-05; use stable v8.21.3 |

---

## Stack Contract Changes

All v2.0 additions are strictly additive. The following existing constraints remain unchanged:

- FastAPI + Next.js + Vite/React + PostgreSQL — base stack unchanged.
- Dexie.js 4 IndexedDB schema — unchanged. GPS positions are server-side only (devices push to backend webhook, not to driver PWA).
- `tenant_id` filter in every query — RLS adds a second isolation layer but does NOT replace the application-level `WHERE tenant_id = ?` filter.
- `Numeric(10,2)` / `Numeric(12,2)` for monetary columns — client credit_limit, payment amounts, AR balances must all use this from day one.
- UTF-8 in all outputs — `fpdf2` already handles Portuguese/Mozambican characters; reuse for client statement PDF.

**One contract change**: `boto3` standalone replaced by `aiobotocore[boto3]`. This changes boto3 to the version pinned by aiobotocore's compatibility matrix (currently boto3 1.37.x range for aiobotocore 3.7.0). Verify existing `files/service.py` presigned URL code against this version before deploying — the S3 presign API is stable across versions, so this should be risk-free.

---

## Sources

- PyPI version index (`pip index versions <package>`) — all versions confirmed as of 2026-06-06
  - `sentry-sdk`: latest 2.61.1
  - `aiobotocore`: latest 3.7.0
  - `sse-starlette`: latest 3.4.4
  - `aiosmtplib`: latest 5.1.1
  - `phonenumbers`: latest 9.0.32
  - `stripe`: latest 15.2.0
  - `itsdangerous`: latest 2.2.0
  - `httpx`: latest 0.28.1 (installed)
- TanStack Table releases: https://github.com/TanStack/table/releases — v8.21.3 confirmed stable; v9.0.0-beta.1 released 2026-06-05 (too new)
- TanStack Query v5: https://github.com/tanstack/query/releases — v5.101.0 confirmed latest stable as of 2026-06-06
- NUIT format: https://tin-check.com/en/mozambique/ — 9 numeric digits, first digit = entity type, last digit = checksum; regex `^\d{9}$` sufficient for format validation
- Codebase analysis: `backend/pyproject.toml`, `backend/app/modules/billing/models.py`, `backend/app/modules/contracts/models.py`, `backend/app/modules/billing/domain.py`, `apps/manager/package.json`
- Teltonika FMB HTTP data sending mode: training knowledge (MEDIUM confidence — HTTP mode is the documented non-enterprise path, but firmware version matters for JSON codec support; verify with Teltonika Configurator for specific device models in use)
- WhatsApp Business Cloud API v22.0: training knowledge (HIGH confidence — stable REST API, well-documented)
- RLS complexity assessment: HIGH confidence (based on direct codebase analysis of 30+ tables across 21 modules)
- Client/AR migration strategy: HIGH confidence (standard Alembic three-step pattern; based on direct analysis of `contracts.client_name` and `billing_documents.client_name` columns in codebase)
