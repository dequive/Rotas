# Phase 8: Infrastructure Hardening — Research

**Researched:** 2026-06-06
**Domain:** Sentry SDK integration, async S3/R2 file storage, tenant plan limit enforcement + Redis caching
**Confidence:** HIGH — all findings grounded in direct codebase inspection + established patterns from SUMMARY.md

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sentry: Observabilidade**
- D-01: Um único projecto Sentry chamado `rotas` com três DSNs separados: `SENTRY_DSN_BACKEND`, `SENTRY_DSN_MANAGER`, `SENTRY_DSN_DRIVER`. Painel único mas erros identificados por source.
- D-02: Sentry desactivado em dev — `sentry_sdk.init()` só corre quando `SENTRY_DSN_BACKEND` está definido e não vazio.
- D-03: `before_send` hook strips: `["driver_name", "cargo_description", "phone", "nuit", "email", "plate_number", "receiver_name", "receiver_contact"]` de extras e request data. SQL breadcrumbs também passam pelo scrubber.
- D-04: `traces_sample_rate=0.05` em produção. ARQ worker inicializa Sentry no arranque, antes de processar qualquer job.
- D-05: `environment` tag usa `settings.environment` (`"production"` / `"staging"` / `"development"`).

**R2/S3: Armazenamento de Ficheiros**
- D-06: Substituir `boto3>=1.43` por `aiobotocore[boto3]>=3.7.0`. Os dois NÃO podem coexistir — conflito na camada `botocore`.
- D-07: Implementar `backend/app/storage.py` com `StorageProvider` enum (`LOCAL`, `R2`) e funções `upload_file()` e `generate_presigned_url()` que despacham com base em `settings.storage_provider`. `files/service.py` passa a usar `storage.py`.
- D-08: Novos env vars: `STORAGE_PROVIDER` (default `"local"`), `R2_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`.
- D-09: Script de migração one-shot: `backend/scripts/migrate_files_to_r2.py`. Corre manualmente antes de mudar `STORAGE_PROVIDER` para `R2`.
- D-10: Script trata `storage_provider IN ('local', 'local_stub')`. **CRÍTICO:** o modelo usa `default="local_stub"` mas service usa `LOCAL_UPLOAD_PROVIDER = "local"` — ambos os valores devem ser incluídos.
- D-11: Falha do script: skip e continua. Resumo final de falhas. Exit code 1 se houver falhas, 0 se limpo.
- D-12: Gate de verificação: `SELECT count(*) FROM files WHERE storage_provider IN ('local', 'local_stub')` deve retornar 0 antes de mudar `STORAGE_PROVIDER=R2`.

**Tenant Limits: Enforcement**
- D-13: `null` em `max_vehicles/max_drivers/max_users` significa ilimitado. Guards fazem skip quando campo é `None`.
- D-14: Guards `_check_vehicle_limit()`, `_check_driver_limit()`, `_check_user_limit()` no topo de cada `create_*` service. Retornam `ApiError("plan_limit_reached", ..., 403)` com body `{"upgrade_url": settings.upgrade_url}`.
- D-15: Redis cache de contagens com TTL 30s: chave `tenant:limits:{tenant_id}`.
- D-16: Novo env var `UPGRADE_URL` em `Settings` (default `""`).
- D-17: Banner `<LimitWarningBanner>` no topo de todas as páginas do manager (layout principal). Não dismissível. Aparece quando qualquer dimensão ≥ 80% do limite.
- D-18: Endpoint `GET /api/v1/tenant/limits` retorna `{vehicle_count, vehicle_max, driver_count, driver_max, user_count, user_max, upgrade_url}`.

### Claude's Discretion

- Estratégia exacta de cache Redis (hash vs múltiplas chaves por dimensão) — planner decide a abordagem mais simples.
- Design visual exacto do `<LimitWarningBanner>` (cor amber/orange, ícone, CTA) — seguir o DESIGN.md do projecto.
- Formato exacto do log de progresso do script de migração — Claude decide.

### Deferred Ideas (OUT OF SCOPE)

- Dashboard de utilização por tenant para o owner/admin (histórico de crescimento) — Phase futuro
- Alertas automáticos de limite por email/WhatsApp — Phase 10
- Geofencing de limites de upload por ficheiro individual — fora de escopo
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INFRA-01 | Erros de produção visíveis no Sentry — SDK integrado no FastAPI backend, ARQ worker, Next.js manager e driver PWA; `before_send` PII scrubber activo | Sentry SDK patterns confirmed; init in lifespan handler; @sentry/nextjs in next.config.mjs; @sentry/vite-plugin in vite.config.mjs; ARQ worker startup hook established |
| INFRA-02 | Ficheiros armazenados em R2/S3 — ficheiros locais migrados antes de activar switch; zero registos `storage_provider=local` após migração | Current files/service.py code path fully inspected; dual-provider pattern is clean refactor; migration script scope confirmed (both 'local' and 'local_stub' values found in codebase) |
| INFRA-03 | Tenant com limite atingido recebe HTTP 403 com `upgrade_url` — max_vehicles/max_drivers/max_users verificados; aviso visual a 80% no manager dashboard | Existing limit checks found in services (partial implementation); Redis cache pattern already established in CT-02; GET /api/v1/tenant/limits is a new endpoint |
</phase_requirements>

---

## Summary

Phase 8 is a pure infrastructure phase with no new user-facing features beyond the limit warning banner. All three tracks (Sentry, R2, tenant limits) are independent and can be implemented in parallel — they share no code paths or data dependencies.

**Critical discovery: Tenant limits are already partially implemented.** Direct inspection of `vehicles/service.py`, `drivers/service.py`, and `users/service.py` confirms that `create_vehicle()`, `create_driver()`, and `create_user()` all already contain limit checks. However: (1) they use inconsistent error slugs (`vehicle_limit_reached` / `driver_limit_reached` / `user_limit_reached`) instead of the unified `plan_limit_reached` slug, (2) they return `details` with the max value but NOT an `upgrade_url`, (3) they do NOT use Redis caching — they query the DB directly every time, (4) `null` (unlimited) is not handled — the current check `active_count >= tenant.max_vehicles` would fail if `max_vehicles` is NULL because PostgreSQL NULL comparisons return NULL not False. The upgrade work is therefore targeted refactoring, not greenfield.

**Critical discovery: ARQ worker does not save files via files module.** The `worker.py:generate_billing_export()` function writes files directly to `LOCAL_UPLOAD_DIR` with `file_path.write_bytes(content)` and stores the path in `job.file_path` — it does NOT call `files.service.save_generated_file()`. This means generated billing PDFs/XLSX are NOT in the `files` table and will NOT be migrated by the R2 migration script. The storage.py refactor must include a plan to route worker-generated files through the files module.

**R2/S3 scope is larger than it appears.** `files/service.py` has three upload paths: `upload_file()` (direct binary upload), `presign_upload()` (client-side presigned URL), and `save_generated_file()` (ARQ worker). All three write to local disk directly. The `presign_upload()` path is particularly tricky — it returns `"upload_url": f"local://{storage_key}"` which is not a real URL. When `STORAGE_PROVIDER=R2`, presign must return a real S3 presigned PUT URL from R2. This is a distinct flow from the direct upload path.

**Primary recommendation:** Implement in this order: (1) Sentry init (no risks, immediate value), (2) Tenant limit refactor (targeted changes to 3 services + 1 new endpoint + Redis cache + frontend banner), (3) storage.py + R2 migration (most complex, requires careful sequencing).

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sentry-sdk[fastapi] | >=2.61.1 | Backend error tracking + performance tracing | Auto-instruments FastAPI, SQLAlchemy, HTTPX; before_send hook for PII scrubbing |
| @sentry/nextjs | ^8.x | Next.js App Router error tracking (server + client) | Official Sentry package for App Router; wraps next.config.mjs |
| @sentry/vite-plugin | ^2.x | Vite/React error tracking for driver PWA | Official Sentry package for Vite; wraps vite.config.mjs |
| aiobotocore[boto3] | >=3.7.0 | Async S3/R2 file operations | Async-safe; boto3 alone blocks asyncio event loop; replaces boto3 completely |
| redis[asyncio] | >=4.2,<6 | Tenant limit count caching (TTL 30s) | Already installed; CT-02 uses same pattern |

### Confirmed Already Installed

| Library | Version in pyproject.toml | Notes |
|---------|--------------------------|-------|
| redis[asyncio] | >=4.2,<6 | Already in main deps — no addition needed |
| arq | >=0.28 | ARQ worker already deployed |
| fpdf2 | >=2.8.7 | Already installed — billing export |

### New Packages to Add

**Backend (`backend/pyproject.toml`):**
```
sentry-sdk[fastapi]>=2.61.1
aiobotocore[boto3]>=3.7.0   # REPLACES boto3>=1.43 — do not keep both
```

**Manager (`apps/manager/`):**
```
@sentry/nextjs   # npm install @sentry/nextjs
```

**Driver PWA (`apps/driver/`):**
```
@sentry/vite-plugin  # npm install @sentry/vite-plugin
```

**Installation:**
```bash
# Backend
cd backend && pip install "sentry-sdk[fastapi]>=2.61.1" "aiobotocore[boto3]>=3.7.0"
# Remove boto3 from pyproject.toml, add aiobotocore[boto3]>=3.7.0

# Manager
cd apps/manager && npm install @sentry/nextjs

# Driver
cd apps/driver && npm install @sentry/vite-plugin
```

---

## Architecture Patterns

### Pattern 1: Sentry Init in FastAPI Lifespan

**What:** `sentry_sdk.init()` is called in the `lifespan` async context manager in `backend/app/main.py`, guarded by env var presence check.

**When to use:** Always for production error tracking. Guard prevents accidental init in local dev.

```python
# Source: sentry-sdk[fastapi] documentation + project decision D-02
import sentry_sdk

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Sentry init (INFRA-01) ---
    dsn = settings.sentry_dsn_backend  # New field on Settings
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            environment=settings.environment,
            traces_sample_rate=0.05,
            before_send=_scrub_pii,
        )
    # ... existing Redis and ARQ init ...
    yield
    # ... existing cleanup ...
```

### Pattern 2: PII Scrubber before_send Hook

**What:** A `before_send` function that recursively strips PII fields from event extras and request data.

**Critical:** SQL breadcrumbs may contain parameter values with PII. The scrubber must also clean breadcrumbs with `category="query"`.

```python
# Source: sentry-sdk before_send documentation
_PII_FIELDS = frozenset([
    "driver_name", "cargo_description", "phone", "nuit", "email",
    "plate_number", "receiver_name", "receiver_contact",
])

def _scrub_pii(event: dict, hint: dict) -> dict | None:
    """Strip PII fields from Sentry event before sending."""
    # Scrub request.data
    if "request" in event and "data" in event["request"]:
        event["request"]["data"] = _scrub_dict(event["request"]["data"])
    # Scrub extra context
    if "extra" in event:
        event["extra"] = _scrub_dict(event["extra"])
    # Scrub SQL breadcrumbs (may contain parameter values)
    for breadcrumb in event.get("breadcrumbs", {}).get("values", []):
        if breadcrumb.get("category") == "query":
            breadcrumb.pop("data", None)
    return event

def _scrub_dict(d: dict) -> dict:
    if not isinstance(d, dict):
        return d
    return {
        k: "[Filtered]" if k in _PII_FIELDS else _scrub_dict(v) if isinstance(v, dict) else v
        for k, v in d.items()
    }
```

### Pattern 3: Sentry in ARQ Worker

**What:** ARQ worker's `startup()` function initializes Sentry before the event loop processes jobs.

**When to use:** Required for D-04 — uncaught exceptions in ARQ tasks must appear in Sentry.

```python
# Source: arq worker + sentry-sdk integration
async def startup(ctx: dict) -> None:
    from app.config import get_settings
    from app.database import AsyncSessionLocal
    import sentry_sdk

    _settings = get_settings()
    dsn = _settings.sentry_dsn_backend
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            environment=_settings.environment,
            traces_sample_rate=0.05,
            before_send=_scrub_pii,
        )
    ctx["db_factory"] = AsyncSessionLocal
```

### Pattern 4: @sentry/nextjs for App Router

**What:** Sentry for Next.js 14 App Router requires wrapping the config and adding instrumentation files.

```javascript
// Source: @sentry/nextjs App Router documentation
// apps/manager/next.config.mjs
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig = { reactStrictMode: true };

export default withSentryConfig(nextConfig, {
  silent: true,          // suppress CLI output during build
  org: "rotas",
  project: "rotas-manager",
});
```

```javascript
// apps/manager/sentry.client.config.ts
import * as Sentry from "@sentry/nextjs";
Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN_MANAGER,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
  tracesSampleRate: 0.05,
});
```

```javascript
// apps/manager/sentry.server.config.ts
import * as Sentry from "@sentry/nextjs";
Sentry.init({
  dsn: process.env.SENTRY_DSN_MANAGER,
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT,
  tracesSampleRate: 0.05,
});
```

**Note:** App Router requires `instrumentation.ts` file at the root of `apps/manager/`:
```typescript
// apps/manager/instrumentation.ts
export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs") {
    await import("./sentry.server.config");
  }
  if (process.env.NEXT_RUNTIME === "edge") {
    await import("./sentry.edge.config");
  }
}
```

### Pattern 5: @sentry/vite-plugin for Driver PWA

```javascript
// apps/driver/vite.config.mjs — add sentryVitePlugin
import { sentryVitePlugin } from "@sentry/vite-plugin";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({ ... }),  // existing
    sentryVitePlugin({
      org: "rotas",
      project: "rotas-driver",
      // sourcemaps upload only in CI — skip in local dev
      disable: !process.env.SENTRY_AUTH_TOKEN,
    }),
  ],
  // Sentry SDK init happens in apps/driver/src/main.tsx (not vite config)
});
```

```typescript
// apps/driver/src/main.tsx — add Sentry init before ReactDOM.createRoot
import * as Sentry from "@sentry/react";
const sentryDsn = import.meta.env.VITE_SENTRY_DSN_DRIVER;
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.VITE_ENVIRONMENT || "development",
    tracesSampleRate: 0.05,
  });
}
```

### Pattern 6: storage.py Dual-Provider Backend

**What:** New module `backend/app/storage.py` abstracts file storage behind a `StorageProvider` enum. `files/service.py` calls `storage.upload_file()` instead of writing to disk directly.

**Critical:** Three upload paths in `files/service.py` must all be refactored:
1. `upload_file()` — direct binary upload (user-facing)
2. `save_generated_file()` — ARQ worker generated files
3. `presign_upload()` — presigned URL for client-side direct upload

For `presign_upload()` with R2 provider: generate a real S3 presigned PUT URL via `generate_presigned_url()`. For LOCAL provider: return the existing `"local://{storage_key}"` sentinel.

```python
# Source: aiobotocore documentation + project architecture decisions
from enum import Enum
from pathlib import Path
from uuid import UUID

import aiobotocore.session

from app.config import get_settings


class StorageProvider(str, Enum):
    LOCAL = "local"
    R2 = "r2"


async def upload_file(storage_key: str, content: bytes, *, mime_type: str) -> str:
    """Upload bytes to configured storage. Returns storage_provider string."""
    settings = get_settings()
    if settings.storage_provider.upper() == StorageProvider.R2:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        ) as client:
            await client.put_object(
                Bucket=settings.r2_bucket,
                Key=storage_key,
                Body=content,
                ContentType=mime_type,
            )
        return StorageProvider.R2
    else:
        # LOCAL: write to disk at local_upload_dir
        root = Path(settings.local_upload_dir)
        target = root / storage_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return StorageProvider.LOCAL


async def generate_presigned_url(storage_key: str, *, expires_in: int = 900) -> str:
    """Return a presigned PUT URL for R2, or a local sentinel for LOCAL."""
    settings = get_settings()
    if settings.storage_provider.upper() == StorageProvider.R2:
        session = aiobotocore.session.get_session()
        async with session.create_client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
        ) as client:
            url = await client.generate_presigned_url(
                "put_object",
                Params={"Bucket": settings.r2_bucket, "Key": storage_key},
                ExpiresIn=expires_in,
            )
        return url
    else:
        return f"local://{storage_key}"
```

### Pattern 7: R2 Migration Script

**What:** One-shot script that reads all `File` records with `storage_provider IN ('local', 'local_stub')`, uploads each to R2, and updates the record. Skip-and-continue on failure.

**Operator workflow:**
1. Run `python backend/scripts/migrate_files_to_r2.py`
2. Verify exit code 0 and "0 failed" in summary
3. Run gate query: `SELECT count(*) FROM files WHERE storage_provider IN ('local', 'local_stub')` = 0
4. Then set `STORAGE_PROVIDER=R2` in Railway

**Critical sequence:** Step 4 happens AFTER steps 1-3. Never toggle the switch first.

### Pattern 8: Tenant Limit Guard Refactor

**Discovery:** Limit checks already exist in all 3 services but must be refactored. Current state:

| Service | Current Error Slug | Missing |
|---------|-------------------|---------|
| `vehicles/service.py` | `vehicle_limit_reached` | `upgrade_url` in body, null check, Redis cache, unified slug |
| `drivers/service.py` | `driver_limit_reached` | `upgrade_url` in body, null check, Redis cache, unified slug |
| `users/service.py` | `user_limit_reached` | `upgrade_url` in body, null check, Redis cache, unified slug |

Refactor to use shared helper:

```python
# Source: project decision D-14, D-15 + existing CT-02 Redis pattern
async def _get_tenant_limit_counts(
    db: AsyncSession,
    tenant_id: UUID,
    redis: Redis | None = None,
) -> dict:
    """Returns {vehicle_count, driver_count, user_count} with Redis TTL 30s cache."""
    CACHE_KEY = f"tenant:limits:{tenant_id}"
    if redis:
        cached = await redis.hgetall(CACHE_KEY)
        if cached:
            return {k: int(v) for k, v in cached.items()}

    # Cache miss — query DB
    vehicle_count = await db.scalar(
        select(func.count(Vehicle.id)).where(
            Vehicle.tenant_id == tenant_id,
            Vehicle.status != "retired",
        )
    ) or 0
    driver_count = await db.scalar(
        select(func.count(Driver.id)).where(
            Driver.tenant_id == tenant_id,
            Driver.status != "inactive",
        )
    ) or 0
    user_count = await db.scalar(
        select(func.count(User.id)).where(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
        )
    ) or 0

    counts = {
        "vehicle_count": vehicle_count,
        "driver_count": driver_count,
        "user_count": user_count,
    }
    if redis:
        await redis.hset(CACHE_KEY, mapping=counts)
        await redis.expire(CACHE_KEY, 30)

    return counts
```

**Note on Redis access in services:** Services currently receive `db: AsyncSession` only. The Redis client is on `app.state.redis`. Two options:
1. Pass Redis client as optional parameter to service functions (consistent with existing pattern in CT service where `redis: Redis | None = None` is passed in)
2. Read Redis from request state in router and pass down

Option 1 is preferred — consistent with `get_ct_cached()` pattern in `control_tower/service.py`.

### Pattern 9: GET /api/v1/tenant/limits Endpoint

**What:** New endpoint in `tenants/router.py`. Returns current usage vs limits. `max = null` = unlimited.

```python
# Source: project decision D-18 + existing tenants/router.py pattern
@router.get("/me/limits")
async def get_tenant_limits(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
):
    redis = getattr(request.app.state, "redis", None)
    return await service.get_tenant_limits(db, principal.tenant_id, redis=redis)
```

### Pattern 10: LimitWarningBanner in layout.tsx

**What:** Server Component in `apps/manager/app/layout.tsx`. Fetches from the new `/api/v1/tenant/limits` endpoint. Renders amber banner when any dimension >= 80%.

**Design tokens from DESIGN.md:**
- Background: `--amber-light: #fef3c7`
- Text: `--amber-dark: #d97706`
- Icon: `lucide-react` TriangleAlert
- Font: Manrope 500 (body text), not mono
- One-line, not dismissible, positioned above main content area

```tsx
// Source: DESIGN.md tokens + project decision D-17
// apps/manager/app/components/LimitWarningBanner.tsx
export function LimitWarningBanner({ limits }: { limits: TenantLimits }) {
  const warnings = [];
  if (limits.vehicle_max !== null && limits.vehicle_count / limits.vehicle_max >= 0.8) {
    warnings.push(`Viaturas: ${limits.vehicle_count}/${limits.vehicle_max}`);
  }
  if (limits.driver_max !== null && limits.driver_count / limits.driver_max >= 0.8) {
    warnings.push(`Motoristas: ${limits.driver_count}/${limits.driver_max}`);
  }
  if (limits.user_max !== null && limits.user_count / limits.user_max >= 0.8) {
    warnings.push(`Utilizadores: ${limits.user_count}/${limits.user_max}`);
  }
  if (warnings.length === 0) return null;
  return (
    <div style={{ background: "var(--amber-light)", color: "var(--amber-dark)" }}
         className="flex items-center gap-2 px-4 py-2 text-sm font-medium">
      <TriangleAlert className="h-4 w-4 flex-shrink-0" />
      <span>Limite do plano: {warnings.join(" · ")}.</span>
      {limits.upgrade_url && (
        <a href={limits.upgrade_url} className="ml-auto underline font-semibold">
          Fazer upgrade →
        </a>
      )}
    </div>
  );
}
```

### Anti-Patterns to Avoid

- **Do not call `sentry_sdk.init()` at module level** in `main.py` — it must be inside the lifespan handler so it runs after settings are loaded and only when DSN is set.
- **Do not keep `boto3` and `aiobotocore[boto3]` simultaneously** — botocore version conflicts cause silent failures at runtime.
- **Do not use `SET app.tenant_id`** (only relevant for RLS in Phase 9, but noting it here as a warning for any DB session access in migration script — use `get_session_raw()` pattern from `database.py`).
- **Do not run the R2 migration AFTER enabling `STORAGE_PROVIDER=R2`** — new uploads go to R2 but old files are still on local disk and become unreachable.
- **Do not add `upgrade_url` to `details` dict** — it belongs in the top-level body as specified in D-14, not nested.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PII scrubbing in Sentry | Custom event filter middleware | `before_send` hook in `sentry_sdk.init()` | Built-in hook runs per-event; middleware would need to intercept Sentry's own transport |
| S3/R2 async client | Custom httpx-based S3 client | `aiobotocore` | Presigned URL generation, multipart upload, retry logic — hundreds of edge cases |
| Sentry in Next.js App Router | Custom error boundaries only | `@sentry/nextjs` + `withSentryConfig` | App Router server components and server actions require Sentry's instrumentation.ts approach |
| Tenant count cache invalidation | Event-based cache bust | TTL 30s expiry only (D-15) | Simplest correct approach; 30s stale is acceptable for a soft limit |
| Presigned URL for R2 uploads | Sign requests manually | `generate_presigned_url` via aiobotocore | HMAC signing, credential rotation, URL expiry — security-critical |

---

## Common Pitfalls

### Pitfall 1: boto3 + aiobotocore botocore conflict (PITFALL-14 adjacent)
**What goes wrong:** If both `boto3>=1.43` and `aiobotocore[boto3]>=3.7.0` are in `pyproject.toml`, pip may install mismatched `botocore` versions. Runtime errors manifest as `AttributeError` or `ImportError` — not obvious at install time.
**Why it happens:** `aiobotocore` pins `botocore` to a specific version range; `boto3` does the same. They are mutually exclusive.
**How to avoid:** Remove `boto3>=1.43` from `pyproject.toml` before adding `aiobotocore[boto3]>=3.7.0`. One line out, one line in.
**Warning signs:** `botocore` version conflicts shown by `pip check`.

### Pitfall 2: R2 migration run AFTER enabling R2 switch (PITFALL-14)
**What goes wrong:** If `STORAGE_PROVIDER=R2` is set in Railway before the migration script completes, new uploads go to R2 but existing files on ephemeral disk are lost on next deploy.
**Why it happens:** Railway's ephemeral filesystem is wiped on every new deployment. Files uploaded before the switch exist only on the current container.
**How to avoid:** Strict operator sequence: (1) run migration script, (2) verify 0 local records, (3) THEN set `STORAGE_PROVIDER=R2`.
**Warning signs:** `generate_billing_export` in `worker.py` writes directly to disk — this path also needs to be routed through `storage.py` before switching.

### Pitfall 3: ARQ worker saves files outside the files table
**What goes wrong:** `worker.py:generate_billing_export()` writes the export file to disk and stores the path in `ExportJob.file_path`. It does NOT insert a `File` record. After R2 migration, the file table is clean, but worker-generated exports are not in R2 and `file_path` points to a local path that will be wiped.
**Why it happens:** Worker was written before the files module was used as a unified storage layer.
**How to avoid:** Refactor `generate_billing_export()` to call `save_generated_file()` from `files/service.py`, which after the storage.py refactor will dispatch to R2. Update `ExportJob.file_path` to store the `File.id` or update it to store the storage_key.
**Warning signs:** `job.file_path = str(file_path)` in `worker.py` line 91.

### Pitfall 4: Sentry init at module level breaks tests
**What goes wrong:** If `sentry_sdk.init()` is called at module import time (top of `main.py`), tests that import the app without setting `SENTRY_DSN_BACKEND` will fail or produce unexpected behavior.
**Why it happens:** Module-level code runs at import time; tests import the app without production env vars.
**How to avoid:** Init only in the `lifespan` handler, guarded by `if settings.sentry_dsn_backend:`.

### Pitfall 5: Tenant limit null check omission
**What goes wrong:** `active_count >= tenant.max_vehicles` returns NULL (Python False) when `max_vehicles` is NULL in PostgreSQL/SQLAlchemy. Enterprise tenants with NULL limits are silently blocked at the default (5 vehicles) behavior — or allowed past the limit, depending on Python's handling.
**Why it happens:** SQLAlchemy maps NULL integer columns to Python `None`; `None >= 5` raises `TypeError` in Python.
**How to avoid:** Guard: `if tenant.max_vehicles is not None and active_count >= tenant.max_vehicles: raise ...`.
**Warning signs:** The current implementation in `vehicles/service.py` line 116: `if active_count is not None and active_count >= tenant.max_vehicles` — this will raise `TypeError` when `max_vehicles` is None.

### Pitfall 6: LimitWarningBanner fetches on every page load
**What goes wrong:** `layout.tsx` is a Server Component that wraps every page. If it `await apiFetch("/tenant/limits")` on every render without caching, it adds a serial network call to every page load.
**Why it happens:** Next.js Server Components don't cache `fetch()` calls automatically when using dynamic routes or `cookies()`.
**How to avoid:** Use `unstable_cache` or React's built-in `cache()` with a short TTL (30s matches Redis TTL). Alternatively, wrap the fetch in a try/catch and return null on error to prevent banner from blocking the page.

### Pitfall 7: @sentry/nextjs requires experimental instrumentation flag
**What goes wrong:** `instrumentation.ts` in Next.js App Router requires `experimental.instrumentationHook: true` in `next.config.mjs` for Next.js versions before 14.2.4. Without it, `register()` is never called and server-side Sentry is silently inactive.
**How to avoid:** Check Next.js version. If `next ^14.2.0` is installed, check if the installed minor version is < 14.2.4 and add the experimental flag if needed, or pin to `>=14.2.4` where it became stable.
**Warning signs:** Server-side exceptions not appearing in Sentry despite client-side ones working.

---

## Code Examples

### Settings additions required

```python
# Source: backend/app/config.py — new fields to add
class Settings(BaseSettings):
    # ... existing fields ...

    # INFRA-01: Sentry DSNs — optional, Sentry disabled if absent
    sentry_dsn_backend: str = Field(default="", validation_alias="SENTRY_DSN_BACKEND")
    sentry_dsn_manager: str = Field(default="", validation_alias="SENTRY_DSN_MANAGER")
    sentry_dsn_driver: str = Field(default="", validation_alias="SENTRY_DSN_DRIVER")

    # INFRA-02: R2/S3 storage
    storage_provider: str = Field(default="local", validation_alias="STORAGE_PROVIDER")
    r2_bucket: str = Field(default="", validation_alias="R2_BUCKET")
    r2_endpoint_url: str = Field(default="", validation_alias="R2_ENDPOINT_URL")
    r2_access_key_id: str = Field(default="", validation_alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: SecretStr = Field(default=SecretStr(""), validation_alias="R2_SECRET_ACCESS_KEY")

    # INFRA-03: Tenant upgrade URL
    upgrade_url: str = Field(default="", validation_alias="UPGRADE_URL")
```

### Existing Redis key pattern (CT-02 reference)

```python
# Source: backend/app/modules/control_tower/service.py — established cache-aside pattern
CT_KPI_TTL = 60   # seconds
key = f"ct:kpis:{tenant_id}"
lock_key = f"ct:kpis:{tenant_id}:lock"
# Uses SET NX EX for stampede lock
```

New pattern for tenant limits follows same structure:
```python
TENANT_LIMITS_TTL = 30  # seconds — D-15
LIMITS_KEY = f"tenant:limits:{tenant_id}"
```

### Error pattern for plan_limit_reached

```python
# Source: backend/app/core/errors.py ApiError pattern
raise ApiError(
    "plan_limit_reached",
    "Plan limit reached. Upgrade your plan to add more resources.",
    status_code=status.HTTP_403_FORBIDDEN,
    details={"upgrade_url": get_settings().upgrade_url},
)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| boto3 (sync) | aiobotocore[boto3] (async) | R2 availability + asyncio era | boto3 blocks event loop on upload; aiobotocore is async-native |
| Direct disk writes in services | storage.py abstraction layer | Phase 8 | Enables provider switching without touching business logic |
| Per-request DB count queries for limits | Redis-cached counts (TTL 30s) | Phase 8 | Eliminates COUNT query on every create_vehicle/create_driver/create_user call |

**Deprecated/outdated:**
- `LOCAL_UPLOAD_PROVIDER = "local"` constant in `files/service.py`: replaced by `StorageProvider` enum from `storage.py`
- `_tenant_upload_dir()` in `files/service.py`: moves to `storage.py` as internal implementation of LOCAL provider

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Redis | Tenant limit cache (D-15) | Yes | Redis 7 (port 6381) | Fallback to direct DB COUNT (already in current code) |
| R2/S3 endpoint | INFRA-02 file migration | External (Cloudflare R2) | — | LOCAL provider stays until R2 configured |
| Python >= 3.11 | aiobotocore | Yes | 3.13 (from .pyc cache) | — |
| Node.js 20.x | @sentry/nextjs build | Yes (engines.node=20.x in package.json) | — | — |
| Sentry account | INFRA-01 | External — must be created | — | Phase 8 blocked until DSNs exist |

**Missing dependencies with no fallback:**
- Sentry project + DSNs: must be created on sentry.io before INFRA-01 can be tested. DSNs are env vars — code can be written without them but cannot be validated.
- Cloudflare R2 bucket + credentials: must exist before INFRA-02 migration script can run.

**Missing dependencies with fallback:**
- Redis unavailable: limit checks fall back to direct DB queries (existing behavior is already the fallback).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio 0.23 (asyncio_mode = "auto") |
| Config file | `backend/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend && python -m pytest tests/test_tenant_user_alert_api.py tests/test_vehicle_driver_api.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | Sentry init only when DSN set | unit | `pytest tests/test_sentry_integration.py -x` | Wave 0 |
| INFRA-01 | PII scrubber strips all 8 fields | unit | `pytest tests/test_sentry_integration.py::test_scrub_pii -x` | Wave 0 |
| INFRA-01 | PII scrubber strips SQL breadcrumbs | unit | `pytest tests/test_sentry_integration.py::test_scrub_sql_breadcrumbs -x` | Wave 0 |
| INFRA-02 | storage.py LOCAL provider writes to disk | unit | `pytest tests/test_storage.py::test_local_upload -x` | Wave 0 |
| INFRA-02 | storage.py R2 provider calls put_object | unit (mocked) | `pytest tests/test_storage.py::test_r2_upload -x` | Wave 0 |
| INFRA-02 | Migration script skips missing files, exits 1 | unit | `pytest tests/test_migrate_files.py -x` | Wave 0 |
| INFRA-02 | Migration gate: zero local records | integration | `pytest tests/test_migrate_files.py::test_gate_query -x` | Wave 0 |
| INFRA-03 | Vehicle limit 403 with upgrade_url | integration | `pytest tests/test_vehicle_driver_api.py::test_vehicle_limit_reached -x` | Partial (exists, needs upgrade_url assertion) |
| INFRA-03 | Driver limit 403 with upgrade_url | integration | `pytest tests/test_vehicle_driver_api.py::test_driver_limit_reached -x` | Partial |
| INFRA-03 | User limit 403 with upgrade_url | integration | `pytest tests/test_tenant_user_alert_api.py::test_user_limit_reached -x` | Partial |
| INFRA-03 | Null max_vehicles = unlimited | integration | `pytest tests/test_vehicle_driver_api.py::test_no_limit_when_max_null -x` | Wave 0 |
| INFRA-03 | GET /api/v1/tenant/limits returns correct counts | integration | `pytest tests/test_tenant_limits_api.py -x` | Wave 0 |
| INFRA-03 | Redis cache used for limit counts | unit (mocked) | `pytest tests/test_tenant_limits_api.py::test_redis_cache_hit -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/test_vehicle_driver_api.py tests/test_tenant_user_alert_api.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_sentry_integration.py` — covers INFRA-01 (PII scrubber unit tests, init guard)
- [ ] `tests/test_storage.py` — covers INFRA-02 (LOCAL and R2 provider unit tests with mocked boto3)
- [ ] `tests/test_migrate_files.py` — covers INFRA-02 migration script (skip behavior, exit codes, gate query)
- [ ] `tests/test_tenant_limits_api.py` — covers INFRA-03 (GET /api/v1/tenant/limits, Redis cache, null unlimited)

Existing tests that need assertion updates (not new files):
- `tests/test_vehicle_driver_api.py` — add `upgrade_url` assertion to existing limit tests
- `tests/test_tenant_user_alert_api.py` — add `upgrade_url` assertion + null limit test

---

## Open Questions

1. **ExportJob.file_path migration path**
   - What we know: `worker.py` stores `str(file_path)` — a local OS path — in `ExportJob.file_path`. After R2 migration, this column becomes meaningless.
   - What's unclear: Should `ExportJob.file_path` be replaced by a FK to `files.id`? Or just the `storage_key`? The billing export download endpoint reads from `job.file_path` — it needs to change too.
   - Recommendation: Add `ExportJob.file_id` (nullable FK to `files.id`), populate in refactored worker, update download endpoint to use `files/service.get_file_path()` or presigned URL.

2. **@sentry/nextjs version compatibility with Next.js 14.2.x**
   - What we know: `next ^14.2.0` installed; `@sentry/nextjs` requires `instrumentation.ts` which became stable in Next.js 14.2.4+.
   - What's unclear: Exact installed minor version of Next.js.
   - Recommendation: Pin `next` to `>=14.2.4` in `apps/manager/package.json` or add `experimental: { instrumentationHook: true }` to `next.config.mjs` as a safe fallback.

3. **presign_upload() for R2 — client-side upload flow change**
   - What we know: Currently `presign_upload()` returns `"upload_url": "local://..."` which is consumed by the sync client in `apps/driver/src/sync.ts`. The client presumably detects this and uploads to the backend `/files/upload` endpoint instead.
   - What's unclear: How does the driver PWA sync client handle the `upload_url` field? If it unconditionally `fetch(upload_url)`, switching to a real R2 presigned URL changes the upload target.
   - Recommendation: Read `apps/driver/src/sync.ts` photo upload logic before finalizing presign flow change.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)

- `backend/app/modules/vehicles/service.py` — `create_vehicle()` with existing limit check at line 116
- `backend/app/modules/drivers/service.py` — `create_driver()` with existing limit check at line 122
- `backend/app/modules/users/service.py` — `create_user()` with existing limit check at line 116
- `backend/app/modules/files/service.py` — all three upload paths inspected (upload_file, presign_upload, save_generated_file)
- `backend/app/modules/files/models.py` — `File.storage_provider default="local_stub"` confirmed (not "local")
- `backend/app/modules/tenants/models.py` — `max_vehicles/max_drivers/max_users` are `Integer` (not nullable) with defaults 5/5/3
- `backend/app/main.py` — lifespan handler structure for Sentry init placement
- `backend/app/worker.py` — `generate_billing_export()` writes directly to disk, NOT through files module
- `backend/app/config.py` — Settings model; no Sentry or R2 fields yet
- `apps/manager/next.config.mjs` — bare config, no Sentry wrapper yet
- `apps/driver/vite.config.mjs` — VitePWA config, no Sentry plugin yet
- `apps/manager/app/layout.tsx` — bare layout, no LimitWarningBanner yet
- `backend/app/modules/control_tower/service.py` — Redis cache-aside pattern (TTL, key structure, stampede lock)
- `.planning/phases/08-infrastructure-hardening/08-CONTEXT.md` — all locked decisions
- `.planning/research/SUMMARY.md` — Phase 5-A section

### Secondary (MEDIUM confidence)

- sentry-sdk[fastapi] 2.61.1 documentation — before_send hook, FastAPI auto-instrumentation
- @sentry/nextjs App Router integration guide — instrumentation.ts requirement
- aiobotocore documentation — presigned URL generation, put_object API

### Tertiary (LOW confidence)

- Next.js 14.2.4 threshold for stable instrumentation.ts — verify against actual installed version

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions confirmed from SUMMARY.md PyPI audit (2026-06-06); direct pyproject.toml inspection
- Architecture: HIGH — all patterns from direct codebase inspection; no speculation
- Pitfalls: HIGH — pitfalls 1-4 discovered by reading actual code; pitfall 5 is a Python None/integer comparison confirmed by reading the existing guard pattern

**Research date:** 2026-06-06
**Valid until:** 2026-07-06 (stable ecosystem; aiobotocore API is stable)
