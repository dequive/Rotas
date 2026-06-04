# External Integrations
_Last updated: 2026-06-04_

## Summary

ROTAS currently has zero active third-party external service integrations — everything runs locally. The architecture is designed to accommodate Cloudflare R2 (file storage), WhatsApp Business (notifications), and two Mozambican mobile payment providers (M-Pesa and e-Mola), but none of these are wired into the application code yet. All integration surface areas are expressed only as placeholder env vars in `.env.example`.

---

## APIs & External Services

### Currently Active

**None.** No third-party API calls are made from application code at this time.

### Planned / Stubbed (env vars exist, code does not)

**Cloudflare R2 (Object Storage):**
- Intended use: Replace local filesystem file uploads with cloud object storage
- Env vars: `CLOUDFLARE_R2_BUCKET`, `CLOUDFLARE_R2_ENDPOINT`, `CLOUDFLARE_R2_ACCESS_KEY_ID`, `CLOUDFLARE_R2_SECRET_ACCESS_KEY`
- Current state: File service hard-codes `storage_provider = "local"` and writes files to `LOCAL_UPLOAD_DIR` on disk (`backend/app/modules/files/service.py`)
- No boto3, s3transfer, or Cloudflare SDK in `backend/pyproject.toml`

**WhatsApp Business API:**
- Intended use: Driver/manager notifications
- Env vars: `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_TOKEN`
- Current state: Not referenced in any Python or TypeScript source file

**M-Pesa (Vodacom Mozambique):**
- Intended use: Mobile payment collection
- Env var: `MPESA_API_KEY`
- Current state: Not referenced in any source file

**e-Mola (Mozambique mobile money):**
- Intended use: Mobile payment collection
- Env var: `EMOLA_API_KEY`
- Current state: Not referenced in any source file

---

## Data Storage

### Primary Database

**PostgreSQL 16**
- Connection: `DATABASE_URL` env var (`postgresql+asyncpg://...` for runtime, `postgresql+psycopg://...` for Alembic migrations)
- Client (runtime): SQLAlchemy 2.0 async engine + `asyncpg` driver (`backend/app/database.py`)
- Client (migrations): `psycopg[binary]` 3.x (Alembic env uses sync connection)
- Local dev: Docker container `rotas-postgres`, port 55432, data persisted in Docker volume `rotas_postgres_data`
- Schema managed by Alembic — 20+ migrations in `backend/alembic/versions/`
- Timezone: `Africa/Maputo` (set in `backend/alembic.ini`)

### Offline / Client-Side Storage

**Dexie.js (IndexedDB wrapper)**
- Used by: `apps/driver/` PWA only
- Database name: `RotasMotoristaDB`
- Schema version: 1
- Tables: `driverProfile`, `vehicles`, `checklistTemplates`, `pendingChecklists`, `checklistResponses`, `activeTrip`, `tripStops`, `loadPermits`, `cargoManifests`, `transportDocuments`, `deliveryProofs`, `tripCosts`, `pendingFuelLogs`, `photoQueue`, `syncQueue`, `destinations`
- Implementation: `apps/driver/src/db.ts`

### File Storage (Current)

**Local Filesystem**
- Upload root: `LOCAL_UPLOAD_DIR` env var (default: `.rotas_uploads/`)
- Path structure: `{tenant_id}/{entity_type}/{file_id}_{safe_filename}`
- Max upload size: 8 MB
- Allowed MIME types: `application/pdf`, `.xlsx`, `image/jpeg`, `image/png`, `image/webp`
- Implementation: `backend/app/modules/files/service.py`

### Caching

**Redis 7** (infrastructure provisioned, application not connected)
- Local dev: Docker container `rotas-redis`, port 6381, AOF persistence enabled, data in Docker volume `rotas_redis_data`
- No Redis client package in backend dependencies
- No Redis usage found in backend application code

---

## Authentication & Identity

**Custom JWT — no external auth provider**
- Library: `python-jose[cryptography]` (`backend/app/core/tokens.py`)
- Algorithm: HS256
- Secret: `JWT_SECRET_KEY` env var
- Access token TTL: 15 minutes
- Refresh token TTL: 30 days (opaque token stored in DB)
- Two scopes: `user` (manager web app) and `driver` (driver PWA)
- Driver pairing via one-time codes (see `backend/alembic/versions/c19ed2fa0823_add_driver_pairing_codes.py`)
- Manager session: HTTP-only cookies storing `rotas_access_token`, `rotas_tenant_id`, `rotas_user_id`, `rotas_role`, `rotas_full_name` (`apps/manager/app/lib/auth.ts`)
- Driver session: Bearer token passed via `Authorization` header from localStorage/env

---

## Multi-Tenancy

All API requests carry a `X-Tenant-Id` header (UUID). Backend enforces tenant isolation at the service layer. Multi-tenant row-level scoping in SQLAlchemy models — no row-level security (RLS) at the database level detected.

---

## Sync Protocol

**Custom offline sync endpoint — no third-party sync service**
- Endpoint: `POST /api/v1/sync/batch`
- Driver PWA queues operations locally in Dexie `syncQueue` and `photoQueue` tables
- Sync runner: `apps/driver/src/sync.ts` — `processSyncQueue()` called with a token
- Retry logic: up to 5 retries per item, statuses: `local_only → syncing → synced/retrying/conflict/failed`
- Idempotency: server-side idempotency key deduplication via `IdempotencyKey` table (`backend/app/core/idempotency.py`), TTL 30 days (90 days for billing)

---

## Monitoring & Observability

**Error tracking:** None (no Sentry, Datadog, etc.)

**Logging:** Python stdlib `logging` via Alembic/SQLAlchemy logger config in `backend/alembic.ini`. No structured logging framework in application code.

**Audit log:** Internal — `audit_log` table written by `backend/app/modules/audit/service.py`, called on all create/update/delete operations throughout backend services.

---

## CI/CD & Deployment

**CI pipeline:** Not detected (no `.github/workflows/`, `.gitlab-ci.yml`, or similar)

**Hosting:** Not configured (no `Dockerfile`, `fly.toml`, `vercel.json`, `railway.toml`, etc. found)

**Process manager:** Uvicorn started directly (no Gunicorn, Supervisor, or systemd config found)

---

## Environment Configuration Summary

| Var | App | Status | Notes |
|---|---|---|---|
| `DATABASE_URL` | Backend | Active | PostgreSQL asyncpg URL |
| `JWT_SECRET_KEY` | Backend | Active | HS256 signing key |
| `CORS_ORIGINS` | Backend | Active | JSON list of allowed origins |
| `LOCAL_UPLOAD_DIR` | Backend | Active | Filesystem upload root |
| `ENVIRONMENT` | Backend | Active | `development` / `production` |
| `ROTAS_API_BASE_URL` | Manager | Active | Backend base URL |
| `VITE_ROTAS_API_BASE_URL` | Driver PWA | Active | Backend base URL |
| `VITE_ROTAS_TENANT_ID` | Driver PWA | Active (dev) | Pre-configured tenant for dev demo |
| `VITE_ROTAS_DRIVER_TOKEN` | Driver PWA | Active (dev) | Pre-configured token for dev demo |
| `CLOUDFLARE_R2_*` | Backend | Planned | Not implemented |
| `WHATSAPP_*` | Backend | Planned | Not implemented |
| `MPESA_API_KEY` | Backend | Planned | Not implemented |
| `EMOLA_API_KEY` | Backend | Planned | Not implemented |

---

## Gaps / Unknowns

- Redis is running locally but has no application consumer — purpose is unspecified (likely intended for rate limiting, session cache, or job queue in future phases)
- No background task queue (Celery, ARQ, RQ) present — all operations are synchronous within the HTTP request cycle
- No email provider configured (no SMTP, SendGrid, Mailgun env vars)
- No CDN or static asset hosting configured for production
- `apps/manager/.env.local` file exists (visible in glob output) but contents are not read per security policy — may contain active local overrides
- Cloudflare R2 integration path requires adding boto3/aiobotocore or the Cloudflare Workers SDK and updating `backend/app/modules/files/service.py` storage provider logic
