# Stack Research
_Last updated: 2026-06-04_

## Summary

ROTAS has a confirmed stack that should not change. This research addresses five integration gaps that block production deployment: adding Workbox PWA to the driver Vite app, deploying FastAPI with Alembic on Railway/Render, implementing secure token refresh, using Cloudflare R2 from FastAPI, and replacing the hand-rolled PDF writer with a library that handles Portuguese/UTF-8 characters correctly. All five gaps have clear, low-risk solutions using well-maintained libraries.

---

## Service Worker / PWA (Workbox + Vite)

**Recommendation: `vite-plugin-pwa` v1.x with `injectManifest` strategy.**

Use `injectManifest` (not `generateSW`) because ROTAS needs a custom background sync queue to hold offline `POST /api/v1/sync/batch` requests until connectivity returns. `generateSW` is config-only and cannot express this logic. `injectManifest` compiles your own `src/sw.ts` file and injects the precache manifest into it.

### Installation

```bash
# in apps/driver/
npm install -D vite-plugin-pwa workbox-precaching workbox-routing workbox-strategies workbox-background-sync
```

### `apps/driver/vite.config.mjs` additions

```ts
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      manifest: {
        name: 'ROTAS Driver',
        short_name: 'ROTAS',
        start_url: '/',
        display: 'standalone',
        theme_color: '#1e40af',
        background_color: '#ffffff',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      }
    })
  ]
})
```

### `apps/driver/src/sw.ts` (custom service worker)

```ts
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { registerRoute } from 'workbox-routing'
import { NetworkFirst, CacheFirst } from 'workbox-strategies'
import { BackgroundSyncPlugin } from 'workbox-background-sync'

declare let self: ServiceWorkerGlobalScope

cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

// Background sync queue for offline POSTs to /sync/batch
const syncQueue = new BackgroundSyncPlugin('sync-batch-queue', {
  maxRetentionTime: 7 * 24 * 60  // 7 days in minutes
})

registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/sync'),
  new NetworkFirst({
    cacheName: 'api-sync',
    plugins: [syncQueue]
  }),
  'POST'
)

// Static shell assets: cache-first
registerRoute(
  ({ request }) => ['style', 'script', 'font'].includes(request.destination),
  new CacheFirst({ cacheName: 'static-assets' })
)

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') self.skipWaiting()
})
```

### `apps/driver/src/main.tsx` registration

```ts
import { registerSW } from 'virtual:pwa-register'
registerSW({ onNeedRefresh() {}, onOfflineReady() {} })
```

### `tsconfig.json` for SW types

Add `"WebWorker"` to the `lib` array in `compilerOptions`.

**Important constraint:** Dexie.js 4 already handles offline data storage in IndexedDB — the service worker background sync is a complementary layer to flush queued network calls once connectivity returns. Do NOT replace Dexie with workbox-background-sync; keep both. Workbox queues failed fetch calls; Dexie persists domain records.

**Confidence: HIGH** — vite-plugin-pwa v1.x is the standard in the Vite ecosystem; official docs are current (2026).

---

## FastAPI Deploy (Railway / Render)

Both platforms support the same deployment model for FastAPI + Alembic. Recommendation: **Railway** as first choice due to its `preDeployCommand` feature that runs migrations in a separate container before traffic is cut over, giving zero-downtime migration semantics.

### Railway (`railway.toml` in `backend/`)

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2"
healthcheckPath = "/health"
healthcheckTimeout = 30
preDeployCommand = ["alembic upgrade head"]
restartPolicyType = "on-failure"
restartPolicyMaxRetries = 3
```

**How Railway pre-deploy works:**
- Runs `preDeployCommand` in a separate container before the new deployment goes live.
- Has full access to all environment variables (DATABASE_URL, etc.).
- If it exits non-zero, the deployment is cancelled — the previous version stays live.
- Filesystem changes are NOT persisted (no volumes) — fine for migrations.

**Required environment variables on Railway:**

| Var | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `JWT_SECRET_KEY` | long random string (required, no default) |
| `CORS_ORIGINS` | `["https://your-manager.vercel.app"]` |
| `R2_ACCOUNT_ID` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | R2 secret |
| `R2_BUCKET_NAME` | bucket name |

### Render (`render.yaml` in repo root)

```yaml
services:
  - type: web
    name: rotas-backend
    runtime: python
    buildCommand: pip install -e ./backend
    startCommand: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: rotas-db
          property: connectionString
```

For Alembic on Render, use a shell wrapper start command since Render has no pre-deploy hook:

```bash
# backend/start.sh
#!/bin/bash
set -e
cd /opt/render/project/src/backend
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers 2
```

Set `startCommand: bash backend/start.sh` in render.yaml.

### Health endpoint (must add to FastAPI)

```python
# backend/app/main.py
@app.get("/health")
async def health():
    return {"status": "ok"}
```

**FastAPI startup validation (SEC-01 / DEPLOY-01):** In `backend/app/config.py`, use `model_validator` to raise at startup if `JWT_SECRET_KEY == "change-me-in-env"` or is absent. Both Railway and Render will fail the health check and block traffic.

**Confidence: HIGH** — Railway `preDeployCommand` syntax is from official docs (retrieved 2026-06-04). Render pattern confirmed via official deploy-fastapi docs.

---

## Token Refresh Pattern

**Recommendation: Access token in memory, refresh token in HttpOnly Secure cookie, silent refresh via axios/fetch interceptor.**

### Backend endpoints needed

```
POST /api/v1/auth/refresh   — issue new access + new refresh (rotation)
POST /api/v1/auth/logout    — revoke refresh token
```

### Rotating refresh token model

Store refresh tokens in a DB table (not just stateless JWT):

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id: UUID = mapped_column(primary_key=True)
    user_id: UUID = mapped_column(ForeignKey("users.id"))
    tenant_id: UUID
    token_hash: str          # SHA-256 hash of the raw token
    issued_at: datetime
    expires_at: datetime
    revoked: bool = False
    replaced_by: UUID | None # chain for reuse detection
```

**Rotation flow:**
1. Client POSTs to `/auth/refresh` with cookie-sent refresh token.
2. Server: verify hash exists in DB, not revoked, not expired.
3. Server: mark old record `revoked=True`, set `replaced_by` = new token ID.
4. Server: insert new refresh token row, set cookie, return new access JWT.
5. If old token already has `replaced_by` set → token reuse detected → revoke entire chain for that user (force re-login).

### Frontend silent refresh (driver PWA)

```ts
// src/lib/apiClient.ts
let accessToken: string | null = null

async function refreshAccess(): Promise<string> {
  const res = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    credentials: 'include'   // sends HttpOnly cookie
  })
  if (!res.ok) throw new Error('session_expired')
  const { access_token } = await res.json()
  accessToken = access_token
  return access_token
}

// Intercept 401 responses — retry once after refresh
async function apiFetch(url: string, options: RequestInit = {}) {
  const headers = {
    ...options.headers,
    Authorization: `Bearer ${accessToken ?? ''}`
  }
  let res = await fetch(url, { ...options, headers })
  if (res.status === 401) {
    const newToken = await refreshAccess()
    res = await fetch(url, {
      ...options,
      headers: { ...options.headers, Authorization: `Bearer ${newToken}` }
    })
  }
  return res
}
```

**Driver PWA difference:** The driver uses a device-scoped token (driver_app scope), not a user session. Refresh still applies — the pairing code issues both an access token and a refresh token at pairing time. The driver app stores the refresh token in an HttpOnly cookie set by the backend (or in a secure IndexedDB field, since the PWA is a single-origin SPA and the backend may be cross-origin — validate CORS setup allows credentials).

**CORS requirement:** `allow_credentials=True` in FastAPI CORS middleware is required for cookies to work cross-origin. Must also set explicit `allow_origins` (not `["*"]`).

**Confidence: MEDIUM** — Pattern is well-established; specific refresh token DB schema is derived from community best practices, not a single authoritative source.

---

## File Storage (R2 + FastAPI)

**Recommendation: boto3 with S3-compatible endpoint, presigned PUT URLs for uploads, presigned GET URLs for downloads.**

The existing code at `backend/app/modules/` already has upload logic with SHA-256 validation. R2 is boto3-compatible — swap the storage backend without changing the API surface.

### boto3 client configuration

```python
# backend/app/storage.py
import boto3
from botocore.config import Config
from app.config import settings

def get_r2_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4")
    )
```

### Presigned PUT (upload)

```python
def generate_upload_url(bucket: str, key: str, content_type: str, expires: int = 3600) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': key, 'ContentType': content_type},
        ExpiresIn=expires
    )
```

**Client must send `Content-Type` header matching the one used to sign the URL.** Mismatch causes 403.

### Presigned GET (download / proof of delivery)

```python
def generate_download_url(bucket: str, key: str, expires: int = 900) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=expires
    )
```

### Environment variables to add

```
R2_ACCOUNT_ID=<cloudflare_account_id>
R2_ACCESS_KEY_ID=<r2_key>
R2_SECRET_ACCESS_KEY=<r2_secret>
R2_BUCKET_NAME=rotas-uploads
```

### Install

```bash
# in backend/pyproject.toml dependencies
boto3>=1.34
```

**R2 limitations to know:**
- `POST` multipart form uploads (HTML forms) are not supported via presigned URL — use presigned `PUT` only.
- Presigned URLs work only with the `*.r2.cloudflarestorage.com` domain, not custom domains.
- No server-side encryption key management required (R2 encrypts at rest by default).

**Confidence: HIGH** — Official Cloudflare R2 docs confirm boto3 pattern with exact `endpoint_url` format (retrieved 2026-06-04).

---

## PDF Generation (UTF-8 support)

**Recommendation: `fpdf2` v2.8.x.**

The existing hand-rolled writer in `backend/app/modules/billing/exporters.py` (pure stdlib BytesIO + zip) does not handle non-ASCII characters reliably. This is a known defect noted in PROJECT.md (BILL-01).

**Decision matrix:**

| Library | UTF-8 support | External deps | Complexity | Verdict |
|---------|--------------|---------------|------------|---------|
| fpdf2 2.8.x | Full TrueType subset embedding — any Unicode font | None (pure Python) | Low | **RECOMMENDED** |
| WeasyPrint | Full via HTML/CSS + system fonts | Cairo, Pango, GDK (heavy C libs) | Medium | Overkill; deployment headache on Railway/Render |
| ReportLab | Supports TTF fonts but requires manual font registration for non-Latin | None (pure Python) | Medium | More complex API, not worth it for billing PDFs |
| hand-rolled stdlib | No proper font handling | None | Low | Broken for accented chars — remove |

**Why fpdf2 wins:** It is pure Python (no system library dependencies, no cairo, no wkhtmltopdf), installs cleanly on Railway/Render with a single pip install, and supports TrueType font embedding with full UTF-8 subset — meaning Mozambican names with cedillas (ç), tildes (ã, õ), and accents (é, ê, â) render correctly without any font hacks.

### Usage pattern (Mozambique UTF-8 names)

```python
from fpdf import FPDF

class InvoicePDF(FPDF):
    def header(self):
        # DejaVuSans covers Latin Extended (all Portuguese diacritics)
        self.add_font("DejaVu", fname="DejaVuSans.ttf")
        self.set_font("DejaVu", size=12)

def generate_invoice_pdf(invoice_data: dict) -> bytes:
    pdf = InvoicePDF()
    pdf.add_page()
    pdf.set_font("DejaVu", size=10)
    pdf.cell(text=f"Cliente: {invoice_data['client_name']}")  # handles ã, ç, é
    return pdf.output()
```

Bundle `DejaVuSans.ttf` (license: permissive, open source) in `backend/app/static/fonts/`. DejaVu Sans covers the full Latin Extended-A block required for Portuguese/Mozambican names.

### Install

```toml
# backend/pyproject.toml
fpdf2 = ">=2.8"
```

**Current version:** 2.8.7 (released 2026-02-28). Actively maintained.

**Confidence: HIGH** — fpdf2 docs explicitly list Latin Extended UTF-8 support; version confirmed from official docs retrieved 2026-06-04.

---

## Gaps / Unknowns

1. **Tailwind CSS in manager app:** `STACK.md` notes no `tailwind.config.*` found despite shadcn/ui being listed. Shadcn/ui requires Tailwind. Needs a quick file system audit before building manager UI phases.

2. **Redis client missing:** Redis 7 is provisioned in Docker Compose but `redis-py` or `redis[asyncio]` is not in `backend/pyproject.toml`. For CT-02 (KPI caching), `redis[asyncio]>=5.0` needs to be added. Pattern: `redis.asyncio.from_url(settings.REDIS_URL)`.

3. **CORS + credentials for cross-origin cookies:** The driver PWA (Vite dev at port 5174) and backend (port 8000) are different origins. `allow_credentials=True` in CORSMiddleware requires explicit origins — validate that `CORS_ORIGINS` env var is set correctly in production, including the Vercel manager URL and any custom domain used for the PWA.

4. **`python-jose` deprecation risk:** `python-jose` (current in `pyproject.toml`) has had slow maintenance. The Authlib or `PyJWT` libraries are more actively maintained alternatives. Not a blocker for MVP but worth noting for v2 security review.

5. **Node.js version pin:** No `.nvmrc` in the repo. Vercel will use its default Node.js version. Pin to Node 20 LTS in both `apps/driver/package.json` and `apps/manager/package.json` via `"engines": { "node": ">=20" }` to avoid build surprises.

6. **`asyncio_mode = "auto"` in pytest config:** Confirm this is set in `backend/pyproject.toml` under `[tool.pytest.ini_options]` to avoid async test warnings when adding new test coverage.
