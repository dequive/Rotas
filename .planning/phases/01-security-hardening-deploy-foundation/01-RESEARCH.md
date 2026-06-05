# Phase 1: Security Hardening + Deploy Foundation — Research

**Researched:** 2026-06-05
**Domain:** Python JWT security, FastAPI rate limiting, pydantic-settings validation, Railway/Vercel deployment, Next.js cookie hardening
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01/D-02 (SEC-05 first):** Migrate `python-jose` → `PyJWT >= 2.8`. Update `backend/app/core/auth.py` and `backend/app/core/tokens.py` (all `jose.jwt.*` calls). Remove `python-jose[cryptography]` from `pyproject.toml`.
- **D-03 (SEC-01):** `jwt_secret_key` must use pydantic-settings `SecretStr` with NO default. Remove `"change-me-in-env"`.
- **D-04 (DEPLOY-01):** Required env vars that block startup if missing: `JWT_SECRET_KEY`, `DATABASE_URL`, `ENVIRONMENT`. `REDIS_URL` and `R2_*` are optional — app starts but features degrade.
- **D-05:** `ENVIRONMENT=production` activates strict mode: CORS enforced, `Secure` cookies, test-token bypass disabled.
- **D-06 (test-token):** `"Bearer test-token"` bypass stays active in development. All 17 existing tests keep passing unchanged. Automatically disabled when `ENVIRONMENT=production`. No test migration in Phase 1.
- **D-07 (SEC-03):** Use `slowapi` (FastAPI-native) with in-memory store. No Redis dependency for rate limiting at this stage.
- **D-08:** Thresholds: `10 requests/minute per IP` on `/api/v1/auth/login`, `/api/v1/auth/refresh`, and `/api/v1/driver-auth/pair`.
- **D-09/D-10/D-11 (SEC-02):** CORS allows production domain only — Vercel-assigned URL. No wildcard `*`. `CORS_ORIGINS` env var accepts a JSON list. In `ENVIRONMENT=production`, app refuses to start if `CORS_ORIGINS` is empty or contains `"*"`. CORS middleware always attached (remove conditional logic in `main.py`).
- **D-12 (SEC-04):** Manager Next.js cookies: add `secure: process.env.NODE_ENV === "production"` to both `apps/manager/app/api/auth/login/route.ts` and `apps/manager/app/lib/auth.ts`. SameSite should be `Lax`.
- **D-13 (AUTH-03):** Replace `get_current_principal` with `get_driver_principal` in both `/api/v1/sync/batch` and `/api/v1/sync/bootstrap` handlers in `backend/app/modules/sync/router.py`.
- **D-14/D-15/D-16/D-17 (DEPLOY-01/02/04):** Deploy target: Railway. `railway.toml` at repo root with `preDeployCommand`. Start command: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`. Required Railway env vars: `JWT_SECRET_KEY`, `DATABASE_URL` (Railway PostgreSQL add-on URL), `ENVIRONMENT=production`, `CORS_ORIGINS`.
- **D-18/D-19/D-20 (DEPLOY-03):** `vercel.json` at `apps/manager/vercel.json`. `NEXT_PUBLIC_API_URL` env var. Pin Node.js `"engines": { "node": "20.x" }` in root `package.json` and `apps/manager/package.json`. Use Vercel-assigned URL.
- **D-21:** Before phase closes, write cross-tenant regression tests for vehicle, driver, and trip endpoints returning 404 (not data) for wrong tenant.

### Claude's Discretion

- Specific `pyproject.toml` version pins for `PyJWT` and `slowapi` — use latest stable
- Exact `railway.toml` service name and region — use Railway defaults
- Structure of the startup validation (validator function, model_validator, or post_init) — follow pydantic-settings conventions
- Which exact tenant IDs to use in cross-tenant regression tests — use existing test fixtures

### Deferred Ideas (OUT OF SCOPE)

- Full test suite migration from `"Bearer test-token"` to real JWT fixtures — Phase 1 only gates the bypass by ENVIRONMENT; test suite update is deferred.
- PostgreSQL RLS as a second isolation layer — deferred to Phase 4.
- Redis-backed rate limiting — deferred to when multi-worker Railway deployment is needed.
- `billing-api.ts` `ROTAS_MANAGER_TOKEN` escape hatch removal — addressed as part of cookie auth unification if time allows, otherwise Phase 2.
- Password reset flow — out of scope for Phase 1.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SEC-05 | Migrate `python-jose` → `PyJWT >= 2.8` to close CVE-2025-61152 | PyJWT 2.13.0 (latest stable) verified. API differs from python-jose: `jwt.decode()` requires explicit `algorithms=["HS256"]` list, rejects `alg=none` by default. Both `auth.py` and `tokens.py` must be updated. |
| SEC-01 | JWT_SECRET_KEY read from required env var at startup — eliminate default `"change-me-in-env"` | pydantic-settings: field with no default + SecretStr = required. `ValidationError` raised at import time if missing. `.get_secret_value()` needed to pass string to PyJWT. |
| SEC-02 | CORS configured for explicit production domains — fail-closed in production without env var | `CORSMiddleware` always attached. Production startup validator rejects empty `CORS_ORIGINS` or `"*"` in origins list. |
| SEC-03 | Rate limiting on `/auth/login`, `/auth/refresh`, `/driver-auth/pair` | `slowapi` 0.1.9 (latest). Requires `request: Request` parameter in each rate-limited endpoint. `@limiter.limit("10/minute")` decorator. Limiter added to `app.state.limiter`. Exception handler registered. |
| SEC-04 | Session cookies with `Secure` flag in production | Two cookie-setting paths: `route.ts` and `auth.ts`. Both need `secure: process.env.NODE_ENV === "production"` and `sameSite: "lax"` added to the cookie opts object. |
| AUTH-03 | `/sync/batch` and `/sync/bootstrap` validated with `get_driver_principal` only | `get_driver_principal` already exists in `auth.py`. Drop-in replacement for `get_current_principal` in both router handlers. Manager tokens rejected with HTTP 403. |
| DEPLOY-01 | All critical env vars validated at startup | pydantic-settings `model_validator(mode="after")` or custom `@validator` for cross-field production checks. Required fields (no default) raise `ValidationError` automatically. |
| DEPLOY-02 | FastAPI backend deployed on Railway with CI/CD | `railway.toml` with `[deploy]` section: `preDeployCommand` as list, `startCommand` string. Railway PostgreSQL add-on provides `DATABASE_URL`. |
| DEPLOY-03 | Manager Next.js deployed on Vercel | `vercel.json` at `apps/manager/`. `engines.node = "20.x"` in both `package.json` files. `NEXT_PUBLIC_API_URL` env var. |
| DEPLOY-04 | Alembic migrations run automatically on deploy | `preDeployCommand = ["alembic upgrade head"]` in `railway.toml`. Alembic uses sync psycopg3 driver (already in `pyproject.toml`). |
</phase_requirements>

---

## Summary

Phase 1 is a pure hardening + deployment phase on a brownfield codebase that is ~70% production-ready. There are no net-new product features — every change either closes a security gap or wires up deployment infrastructure.

The most acute item is CVE-2025-61152 in `python-jose`: tokens with `alg=none` are accepted without signature verification, which is a complete auth bypass. The fix is a library swap to `PyJWT >= 2.8`, which rejects `alg=none` by design. Two files use `jose.jwt` directly (`backend/app/core/auth.py` and `backend/app/core/tokens.py`) — both must be updated together.

The remaining security items (startup validation, rate limiting, CORS hardening, secure cookies, sync endpoint auth fix) are each single-file or two-file changes with well-understood patterns. The deployment work (Railway `railway.toml`, Vercel `vercel.json`, Node.js version pinning) is configuration, not code.

The biggest planning risk is the `slowapi` integration: it requires the `request: Request` parameter to be explicitly declared in each rate-limited endpoint function. The existing auth router functions do not have this parameter — they must be added. Decorator order (route decorator above limiter decorator) is also mandatory.

**Primary recommendation:** Execute in dependency order: SEC-05 (JWT library) → SEC-01 (secret validation) → DEPLOY-01 (startup validation) → SEC-02/SEC-03/SEC-04/AUTH-03 (remaining hardening) → DEPLOY-02/03/04 (deploy config) → D-21 (cross-tenant regression tests).

---

## Standard Stack

### Core (Phase 1 additions)

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `PyJWT` | `2.13.0` (latest stable) | JWT encode/decode, replaces python-jose | Actively maintained, rejects `alg=none` by default, no CVE. `python-jose` is unmaintained. |
| `slowapi` | `0.1.9` (latest stable) | Per-endpoint IP rate limiting for FastAPI/Starlette | Port of flask-limiter, first-class FastAPI support, in-memory store sufficient for single-process MVP |

### Existing Stack (unchanged)

| Library | Version | Purpose |
|---------|---------|---------|
| `pydantic-settings` | `>=2.2` | Settings, env var loading, SecretStr, validation |
| `fastapi` | `>=0.111` | HTTP framework |
| `uvicorn[standard]` | `>=0.29` | ASGI server |
| `alembic` | `>=1.13` | Database migrations (for preDeployCommand) |
| `next` | `^14.2.0` | Manager frontend (cookie hardening target) |

### Removed

| Library | Reason |
|---------|--------|
| `python-jose[cryptography]` | CVE-2025-61152 — unmaintained, remove from `pyproject.toml` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `slowapi` | `fastapi-limiter` (Redis-backed) | Redis-backed is more robust under multi-worker but adds a Redis dependency. Decision: in-memory `slowapi` for MVP, Redis-backed deferred to Phase 4 |
| `PyJWT` | `authlib` | `authlib` is heavier (full OAuth2 stack). PyJWT is the standard drop-in for HMAC JWTs. |

**Installation:**
```bash
# From backend/
pip install "PyJWT>=2.8" "slowapi>=0.1.9"
# Remove python-jose from pyproject.toml dependencies
```

**Verified versions (2026-06-05):**
- PyJWT: latest = 2.13.0, installed on this machine = 2.12.1. Pin `PyJWT>=2.8` in pyproject.toml.
- slowapi: latest = 0.1.9. Pin `slowapi>=0.1.9`.

---

## Architecture Patterns

### Pattern 1: PyJWT Migration (python-jose → PyJWT)

**What:** Replace `jose.jwt` calls with `jwt` (PyJWT). The API is similar but not identical.

**Key differences from python-jose:**
- `jwt.encode()` in PyJWT returns a `str`, not `bytes` (no `.decode("utf-8")` needed)
- `jwt.decode()` requires `algorithms` as a keyword argument (not positional)
- Exception hierarchy changes: `jose.JWTError` → `jwt.exceptions.PyJWTError` (base) or specific subclasses
- `alg=none` tokens raise `jwt.exceptions.DecodeError` automatically — no extra check needed

**`backend/app/core/tokens.py` change:**
```python
# Before (python-jose)
from jose import jwt
jwt.encode(claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

# After (PyJWT)
import jwt
jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm)
# Note: get_secret_value() needed once jwt_secret_key becomes SecretStr
```

**`backend/app/core/auth.py` change:**
```python
# Before (python-jose)
from jose import JWTError, jwt
claims = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
# ...
except (JWTError, KeyError, TypeError, ValueError) as exc:

# After (PyJWT)
import jwt
claims = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=[settings.jwt_algorithm])
# ...
except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
```

Source: [PyJWT usage docs](https://pyjwt.readthedocs.io/en/stable/usage.html), verified 2026-06-05. Confidence: HIGH.

---

### Pattern 2: pydantic-settings Required Fields + Production Validation

**What:** Fields with no `default` or `default_factory` in `BaseSettings` are required — pydantic raises `ValidationError` at instantiation if the env var is missing. For cross-field validation (e.g., "in production, CORS_ORIGINS must be non-empty"), use `model_validator(mode="after")`.

**`backend/app/config.py` target shape:**
```python
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ROTAS"
    environment: str = Field(validation_alias="ENVIRONMENT")           # required, no default
    api_v1_prefix: str = "/api/v1"
    version: str = "0.1.0"

    database_url: str = Field(validation_alias="DATABASE_URL")         # required, no default
    jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY")  # required, no default, SecretStr

    access_token_minutes: int = 15
    refresh_token_days: int = 30
    jwt_algorithm: str = "HS256"

    cors_origins: list[str] = Field(default_factory=list)
    local_upload_dir: str = Field(default=".rotas_uploads", validation_alias="LOCAL_UPLOAD_DIR")

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_config(self) -> "Settings":
        if self.environment == "production":
            if not self.cors_origins or "*" in self.cors_origins:
                raise ValueError(
                    "CORS_ORIGINS must be set to explicit origins (not '*') in ENVIRONMENT=production"
                )
        return self
```

**Critical detail:** Once `jwt_secret_key` is `SecretStr`, every call-site that passes the raw string to PyJWT must call `.get_secret_value()`. There are two call-sites:
- `backend/app/core/tokens.py:45` — `settings.jwt_secret_key` → `settings.jwt_secret_key.get_secret_value()`
- `backend/app/core/auth.py:54` — same

The `lru_cache` on `get_settings()` means validation runs once at first import. If `JWT_SECRET_KEY` is absent, the import of `app.main` fails with a clear `ValidationError` — this is the desired startup behavior.

Confidence: HIGH (pydantic-settings official docs, cross-referenced with existing code patterns in `config.py`).

---

### Pattern 3: slowapi Rate Limiting

**What:** Limiter singleton attached to `app.state.limiter`. Routes decorated with `@limiter.limit()`. `request: Request` must be an explicit parameter in each decorated function.

**Setup in `backend/app/main.py`:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

**Decorator on auth router endpoints (`backend/app/modules/auth/router.py`):**
```python
from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Import limiter from main or instantiate in a shared module
from app.main import limiter

@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,           # REQUIRED — slowapi reads the IP from this
    payload: schemas.LoginRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.login(db, payload)
```

**Critical gotchas:**
1. `request: Request` must be explicitly in the function signature — not injected via `Depends`. slowapi inspects the actual function signature.
2. Decorator order: `@router.post(...)` must be ABOVE `@limiter.limit(...)`. Reversed order causes the limit to not fire.
3. The limiter is defined in `main.py` but used in routers — creates a circular import risk. Standard solution: define limiter in a separate `app/core/limiter.py` module and import from there in both `main.py` and the router.

Source: [slowapi docs](https://slowapi.readthedocs.io/en/latest/), [GitHub examples](https://github.com/laurentS/slowapi). Confidence: HIGH.

---

### Pattern 4: CORS Always-Attached

**What:** Remove the `if settings.cors_origins:` conditional in `main.py`. Always attach `CORSMiddleware`. In production, the startup validator (Pattern 2) ensures `cors_origins` is non-empty before the app reaches this point.

**`backend/app/main.py` change:**
```python
# Before (conditional — broken in production if CORS_ORIGINS not set)
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)

# After (unconditional — validation at startup prevents empty list in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

In development (empty `cors_origins`), `CORSMiddleware` with an empty allow_origins list effectively rejects all cross-origin requests — but since development uses localhost, this is acceptable. Add the Vercel origin to your local `.env` file's `CORS_ORIGINS` when testing cross-origin locally.

---

### Pattern 5: Secure Cookies in Next.js

**What:** Both cookie-setting paths need `secure` and `sameSite` flags added.

**`apps/manager/app/api/auth/login/route.ts` (line 27 area):**
```typescript
// Before
const opts = { httpOnly: true, path: "/", maxAge: 60 * 60 * 8 } as const;

// After
const isProduction = process.env.NODE_ENV === "production";
const opts = {
  httpOnly: true,
  path: "/",
  maxAge: 60 * 60 * 8,
  secure: isProduction,
  sameSite: "lax" as const,
};
```

**`apps/manager/app/lib/auth.ts` (line 49 area):** Same change, same opts object.

Note: `as const` on the whole opts object prevents adding `secure` and `sameSite` because it freezes the type. Remove the `as const` on the object literal and use `as const` on individual string literals where needed, or use a typed variable.

---

### Pattern 6: railway.toml Structure

**What:** Config-as-code file at repo root. `preDeployCommand` is an array of strings. `startCommand` is a single string.

```toml
[deploy]
preDeployCommand = ["alembic upgrade head"]
startCommand = "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

**Important:** The module path in `startCommand` is `backend.app.main:app` (dot-separated from repo root), not `app.main:app`. This is because the repo root is the working directory on Railway, and the `backend/` directory is a Python package only if it has `__init__.py`. Verify this exists or use `cd backend && uvicorn app.main:app ...` syntax.

The Railway PostgreSQL add-on injects `DATABASE_URL` automatically using its internal format. The format may differ from the local dev URL — Railway uses `postgresql://` (psycopg2 scheme) by default, but the app needs `postgresql+asyncpg://`. Set `DATABASE_URL` manually in Railway env vars using the asyncpg format, or add a `@field_validator` that rewrites the scheme.

Source: [Railway config-as-code reference](https://docs.railway.com/config-as-code/reference). Confidence: HIGH.

---

### Pattern 7: Vercel Configuration for Next.js App Router

**What:** `vercel.json` at `apps/manager/vercel.json`. For Next.js 14 with App Router, minimal configuration is needed — Vercel auto-detects the framework.

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "installCommand": "npm install",
  "buildCommand": "npm run build",
  "outputDirectory": ".next"
}
```

For a monorepo (root `package.json` + `apps/manager/`), Vercel must be configured to deploy from `apps/manager/` as the root directory — set in the Vercel project settings UI, not in `vercel.json`. The `vercel.json` at `apps/manager/` is relative to that root.

**Required environment variable:** `NEXT_PUBLIC_API_URL` pointing to the Railway backend URL (e.g., `https://rotas-backend.up.railway.app`). This replaces `ROTAS_API_BASE_URL` used in the existing `route.ts` and `auth.ts` files — verify which env var name is actually read by the manager code. Current code reads `process.env.ROTAS_API_BASE_URL`. Either rename to `NEXT_PUBLIC_API_URL` (public, accessible client-side) or keep `ROTAS_API_BASE_URL` (server-only, used only in server components/actions). Since `route.ts` and `auth.ts` are server-side, `ROTAS_API_BASE_URL` without `NEXT_PUBLIC_` prefix is correct and more secure.

Source: [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json). Confidence: HIGH.

---

### Pattern 8: Cross-Tenant Regression Tests

**What:** Tests that authenticate as tenant A and attempt to access tenant B resources. Pattern matches existing test structure (no conftest.py, self-contained, uses `test-token` bypass).

```python
# New file: backend/tests/test_cross_tenant_isolation.py
async def test_vehicle_not_accessible_from_other_tenant():
    tenant_a = await create_tenant()
    tenant_b = await create_tenant()
    # Create vehicle in tenant A
    async with await create_api_client() as client:
        create = await client.post("/api/v1/vehicles", headers=auth_headers(tenant_a.id), json={...})
        vehicle_id = create.json()["id"]
        # Attempt to access from tenant B — must 404, not return data
        response = await client.get(f"/api/v1/vehicles/{vehicle_id}", headers=auth_headers(tenant_b.id))
        assert response.status_code == 404
```

Minimum coverage: vehicle, driver, and trip endpoints. Follow the copy-paste pattern from `test_vehicle_driver_api.py` including the `dispose_engine_between_tests` fixture.

---

### Anti-Patterns to Avoid

- **Circular import via limiter:** Do NOT import `limiter` from `app.main` in routers. Define in `app/core/limiter.py` and import from there in both `main.py` and the routers.
- **`algorithms` as positional arg:** PyJWT requires `algorithms=["HS256"]` as keyword. Positional passing will raise `TypeError` at decode time.
- **Railway DATABASE_URL scheme mismatch:** Railway injects `postgresql://` but asyncpg needs `postgresql+asyncpg://`. Do not rely on the auto-injected value without scheme rewriting.
- **`as const` blocking SecretStr opts:** The `{ ... } as const` TypeScript pattern prevents adding new properties. Remove it from the opts object before adding `secure` and `sameSite`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JWT `alg=none` rejection | Manual header check before decode | `PyJWT >= 2.8` | PyJWT rejects `alg=none` at the library level — not a user-space check that can be bypassed |
| IP-based rate limiting | Manual counter in memory/Redis | `slowapi` | Edge cases: IPv6 normalization, distributed headers (X-Forwarded-For), atomic counter under concurrent requests |
| pydantic-settings required field validation | Custom startup function that checks env vars | `SecretStr` field with no default | pydantic raises `ValidationError` with clear field-level messages at import time, before any request handling |
| CORS header management | Manual `Access-Control-Allow-*` headers | FastAPI's `CORSMiddleware` | Preflight handling, credential header whitelisting, wildcard restrictions — non-trivial to get right |

**Key insight:** The security primitives in this phase all have canonical library implementations. Custom solutions in each area have well-known failure modes: `alg=none` bypass, timing attacks on counters, silent env var fallbacks, and CORS preflight bugs.

---

## Common Pitfalls

### Pitfall 1: slowapi requires `request: Request` in route function signature
**What goes wrong:** Adding `@limiter.limit("10/minute")` to a route that does not declare `request: Request` as a parameter causes slowapi to silently skip rate limiting or raise `AttributeError` at runtime.
**Why it happens:** slowapi uses Python function introspection to find the `Request` object. It does not fall back to dependency injection.
**How to avoid:** Add `request: Request` as the first parameter to each rate-limited function. Import `Request` from `fastapi`.
**Warning signs:** Rate limiting appears not to work (no 429 responses) — slowapi silently fails when it cannot find the request.

### Pitfall 2: Decorator order for slowapi
**What goes wrong:** If `@limiter.limit()` is placed above `@router.post()`, the rate limit never fires.
**Why it happens:** FastAPI decorator registration order — the outermost decorator wraps first.
**How to avoid:** Always keep the router decorator (`@router.post(...)`) as the outermost decorator, limiter below it.

### Pitfall 3: `jwt_secret_key.get_secret_value()` call-sites
**What goes wrong:** After converting `jwt_secret_key` to `SecretStr`, passing `settings.jwt_secret_key` directly to `jwt.encode()` or `jwt.decode()` causes a `TypeError` because PyJWT receives a `SecretStr` object instead of a string.
**Why it happens:** `SecretStr` does not implicitly coerce to `str` — that is the point of the type.
**How to avoid:** Search for all usages of `settings.jwt_secret_key` and append `.get_secret_value()`. Call-sites: `backend/app/core/tokens.py:45` and `backend/app/core/auth.py:54`.
**Warning signs:** `jwt.encode()` raises `TypeError: expected str, bytes or bytearray, not SecretStr`.

### Pitfall 4: Railway DATABASE_URL scheme incompatibility
**What goes wrong:** Railway's PostgreSQL add-on injects `DATABASE_URL=postgresql://...`. The app uses `asyncpg` which requires `postgresql+asyncpg://`. Alembic also needs the psycopg3 scheme (`postgresql+psycopg://`). If the injected URL is used as-is, the app fails to connect.
**Why it happens:** Railway uses the standard libpq URL format, not the SQLAlchemy driver-specific format.
**How to avoid:** Set `DATABASE_URL` manually in Railway environment variables using the correct scheme. Or add a `@field_validator("database_url", mode="before")` in `Settings` that rewrites `postgresql://` → `postgresql+asyncpg://`.
**Warning signs:** `asyncpg` driver import errors or "could not translate host name" at startup.

### Pitfall 5: `lru_cache` on `get_settings()` causes stale settings after env var changes
**What goes wrong:** `get_settings()` is cached with `@lru_cache`. If tests set environment variables after the first call, the cached settings object is returned with the old values.
**Why it happens:** `lru_cache` returns the same object for all subsequent calls.
**How to avoid:** In tests, call `get_settings.cache_clear()` before tests that depend on specific env var values. The existing test suite uses `ENVIRONMENT=development` (default) so this is not a current issue — but cross-tenant tests must not accidentally set `ENVIRONMENT=production` without clearing the cache.
**Warning signs:** Tests fail with unexpected validation errors or wrong environment behavior.

### Pitfall 6: `CORS_ORIGINS` env var format
**What goes wrong:** pydantic-settings needs to parse `list[str]` from an env var string. Railway/Vercel env vars are plain strings. If `CORS_ORIGINS=https://rotas-manager.vercel.app` (no brackets), pydantic-settings parses it as a list of characters. If `CORS_ORIGINS=["https://rotas-manager.vercel.app"]` (JSON), it parses correctly.
**Why it happens:** pydantic-settings uses JSON parsing for complex types from env vars.
**How to avoid:** Set `CORS_ORIGINS` as a JSON list string in Railway/Vercel: `["https://rotas-manager.vercel.app"]`.
**Warning signs:** 403/CORS errors in production; logging shows origins list contains individual characters.

### Pitfall 7: Next.js monorepo Vercel root directory
**What goes wrong:** Vercel deploys from the repo root and tries to build `next build` from there. The `package.json` at root has no `next` dependency and no `build` script that runs next.
**Why it happens:** Vercel monorepo detection is heuristic. Without explicit configuration, it may target the wrong directory.
**How to avoid:** Set the Vercel project's **Root Directory** to `apps/manager` in the Vercel UI project settings. This is a UI setting, not in `vercel.json`.
**Warning signs:** Build fails with "next: command not found" or "Module not found: next".

---

## Code Examples

Verified patterns from official sources and existing codebase:

### PyJWT encode/decode (replacing jose.jwt)
```python
# Source: https://pyjwt.readthedocs.io/en/stable/usage.html
import jwt  # PyJWT — not python-jose

# Encoding (tokens.py)
token: str = jwt.encode(claims_dict, secret_str, algorithm="HS256")
# Returns str directly (no .decode() needed)

# Decoding (auth.py)
try:
    claims = jwt.decode(token, secret_str, algorithms=["HS256"])
    # algorithms= is a list, always
except jwt.PyJWTError as exc:
    # Base exception for all PyJWT errors
    # Includes: ExpiredSignatureError, InvalidAlgorithmError, DecodeError, etc.
    raise ApiError("invalid_token", ..., status_code=401) from exc
```

### pydantic-settings SecretStr with model_validator
```python
# Source: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
from pydantic import SecretStr, Field, model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret_key: SecretStr = Field(validation_alias="JWT_SECRET_KEY")
    environment: str = Field(validation_alias="ENVIRONMENT")

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production":
            if not self.cors_origins or "*" in self.cors_origins:
                raise ValueError("CORS_ORIGINS must be explicit in production")
        return self

# Usage:
settings.jwt_secret_key.get_secret_value()  # → raw string for PyJWT
```

### slowapi setup and route decoration
```python
# Source: https://slowapi.readthedocs.io/en/latest/
# app/core/limiter.py (new file — avoids circular import)
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# app/main.py additions
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# app/modules/auth/router.py
from fastapi import Request
from app.core.limiter import limiter

@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,  # MUST be explicit
    payload: schemas.LoginRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.login(db, payload)
```

### railway.toml (verified format)
```toml
# Source: https://docs.railway.com/config-as-code/reference
[deploy]
preDeployCommand = ["alembic upgrade head"]
startCommand = "uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

### Next.js secure cookie options
```typescript
// Source: Next.js cookies() API + SEC-04 decision
const isProduction = process.env.NODE_ENV === "production";
const opts = {
  httpOnly: true,
  path: "/",
  maxAge: 60 * 60 * 8,
  secure: isProduction,
  sameSite: "lax" as const,
};
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-jose` JWT | `PyJWT` | python-jose became unmaintained ~2023, CVE-2025-61152 disclosed Oct 2025 | `alg=none` rejection is now library-level, not application-level |
| Manual CORS conditional | Always-attached `CORSMiddleware` | Project decision (Phase 1) | Fail-closed in production if CORS_ORIGINS unset |
| `str` for JWT secret | `SecretStr` (pydantic) | Phase 1 hardening | Secret value masked in logs and exception messages |

**Deprecated/outdated:**
- `python-jose`: Unmaintained, not safe for production. No future fixes expected. CVE-2025-61152 will remain unpatched in that library.

---

## Open Questions

1. **`backend.app.main:app` module path on Railway**
   - What we know: Railway runs from the repo root. The `backend/` directory is a Python package if it has `__init__.py`.
   - What's unclear: Whether `backend/__init__.py` exists. If it doesn't, the dot-path won't work.
   - Recommendation: Planner should verify `backend/__init__.py` exists. If not, use `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT` in `startCommand`, or add the `__init__.py` as a task.

2. **Alembic's DATABASE_URL during preDeployCommand**
   - What we know: Alembic uses the sync psycopg3 driver (`psycopg[binary]` already in pyproject.toml). The `alembic.ini` or `env.py` must read `DATABASE_URL` from the environment.
   - What's unclear: Whether current `backend/alembic/env.py` reads from `DATABASE_URL` env var or hardcodes the connection string.
   - Recommendation: Planner should verify `alembic/env.py` reads `DATABASE_URL` from env. If it uses `config.py`'s `get_settings()`, the asyncpg URL will fail for the sync driver — Alembic needs a `postgresql+psycopg://` URL, not `postgresql+asyncpg://`.

3. **Vercel monorepo root directory setting**
   - What we know: `vercel.json` at `apps/manager/` is relative to the project root. Vercel needs the root directory set to `apps/manager` in the UI.
   - What's unclear: Whether Vercel auto-detects the `apps/manager` sub-directory as a Next.js app in a workspace.
   - Recommendation: Planner should add a task to configure Vercel project root directory to `apps/manager` in the Vercel UI as part of DEPLOY-03.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Backend runtime | Yes | 3.13 (cpython-313 .pyc files) | — |
| Node.js 20.x | Vercel deploy requirement | Yes (locally: 24.x) | v24.16.0 | Pin to 20.x in engines field; Vercel uses its own Node version |
| npm | Package management | Yes | 11.13.0 | — |
| PyJWT 2.13.0 | SEC-05 JWT library | Not installed in venv | — | Install via pip |
| slowapi 0.1.9 | SEC-03 rate limiting | Not installed in venv | — | Install via pip |
| Railway CLI | DEPLOY-02 deployment | Not checked | — | Deploy via Railway web UI or GitHub integration |
| Vercel CLI | DEPLOY-03 deployment | Not checked | — | Deploy via Vercel web UI or GitHub integration |
| PostgreSQL 16 (local) | Test suite | Yes (assumed, default URL in config.py) | 16 on port 55432 | Tests skip with OperationalError if unavailable |

**Missing dependencies with no fallback:**
- PyJWT: must be installed before the auth.py migration can be tested

**Missing dependencies with fallback:**
- Railway CLI: web UI / GitHub integration is the standard deploy method; CLI optional
- Vercel CLI: same — web UI / GitHub integration is the standard

**Note on Node.js version:** Locally installed Node is 24.x. Vercel requires `engines.node = "20.x"` to be declared, but it uses its own Node.js installation during build — the local version does not matter. Declaring `"engines": { "node": "20.x" }` is for Vercel's build environment selection, not local enforcement.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ with pytest-asyncio 0.23+ |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && pytest tests/test_auth_api.py tests/test_vehicle_driver_api.py -x` |
| Full suite command | `cd backend && pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SEC-05 | `alg=none` token rejected with HTTP 401 | integration | `pytest tests/test_auth_api.py -k "alg_none" -x` | ❌ Wave 0 — new test needed |
| SEC-01 | Missing JWT_SECRET_KEY raises ValidationError at startup | unit | `pytest tests/test_startup_validation.py -x` | ❌ Wave 0 |
| SEC-02 | CORS headers present with explicit origin; absent for unknown origin | integration | `pytest tests/test_cors.py -x` | ❌ Wave 0 |
| SEC-03 | 11th request within 1 minute returns HTTP 429 | integration | `pytest tests/test_rate_limiting.py -x` | ❌ Wave 0 |
| SEC-04 | Cookie `Secure` flag set in production NODE_ENV | unit/manual | Manual inspection in production (Next.js) | manual-only |
| AUTH-03 | Manager token rejected on `/sync/batch` with HTTP 403 | integration | `pytest tests/test_auth_api.py -k "sync_batch_manager_rejected" -x` | ❌ Wave 0 |
| DEPLOY-01 | Missing `ENVIRONMENT` raises ValidationError at startup | unit | `pytest tests/test_startup_validation.py -x` | ❌ Wave 0 |
| DEPLOY-02/04 | Alembic migrations run on deploy; backend reachable at Railway URL | smoke/manual | Manual smoke test against Railway URL | manual-only |
| DEPLOY-03 | Manager frontend reachable at Vercel URL | smoke/manual | Manual smoke test against Vercel URL | manual-only |
| D-21 | Cross-tenant vehicle/driver/trip returns 404 (not data) | integration | `pytest tests/test_cross_tenant_isolation.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest tests/test_auth_api.py -x` (fast, real auth path)
- **Per wave merge:** `cd backend && pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_startup_validation.py` — covers SEC-01, DEPLOY-01 (validates Settings ValidationError on missing env vars)
- [ ] `backend/tests/test_cors.py` — covers SEC-02 (CORS headers present/absent)
- [ ] `backend/tests/test_rate_limiting.py` — covers SEC-03 (429 after 10 requests)
- [ ] `backend/tests/test_auth_api.py` — add `alg=none` test case to existing file (covers SEC-05)
- [ ] `backend/tests/test_auth_api.py` — add manager-token-on-sync-batch test (covers AUTH-03)
- [ ] `backend/tests/test_cross_tenant_isolation.py` — covers D-21 cross-tenant regression

**Important for test isolation:** SEC-05 test (alg=none) and SEC-01 test (missing env var) require controlling `ENVIRONMENT` and `JWT_SECRET_KEY`. Use `monkeypatch.setenv()` and `get_settings.cache_clear()` to avoid lru_cache contamination between tests.

---

## Sources

### Primary (HIGH confidence)
- [PyJWT 2.13.0 docs — usage](https://pyjwt.readthedocs.io/en/stable/usage.html) — encode/decode API, exception hierarchy, alg=none behavior
- [PyPI — PyJWT](https://pypi.org/project/PyJWT/) — version 2.13.0 confirmed as latest stable
- [PyPI — slowapi](https://slowapi.readthedocs.io/en/latest/) — version 0.1.9, setup pattern, decorator requirements
- [Railway config-as-code reference](https://docs.railway.com/config-as-code/reference) — `railway.toml` TOML structure verified
- [Vercel project configuration](https://vercel.com/docs/project-configuration/vercel-json) — `vercel.json` schema
- Codebase direct read — `backend/app/core/auth.py`, `backend/app/core/tokens.py`, `backend/app/config.py`, `backend/app/main.py`, `backend/app/modules/sync/router.py`, `backend/app/modules/auth/router.py`

### Secondary (MEDIUM confidence)
- [CVE-2025-61152 NVD detail](https://nvd.nist.gov/vuln/detail/CVE-2025-61152) — confirmed CVSS 6.5, affects python-jose through 3.3.0
- [Wiz CVE-2025-61152](https://www.wiz.io/vulnerability-database/cve/cve-2025-61152) — exploitation and mitigation context
- [slowapi GitHub examples](https://github.com/laurentS/slowapi/blob/master/docs/examples.md) — decorator order and Request parameter requirement

### Tertiary (LOW confidence)
- None — all findings are verified via official docs or direct code inspection.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyJWT and slowapi versions verified against PyPI; existing stack read directly from pyproject.toml
- Architecture: HIGH — PyJWT API verified from official docs; slowapi patterns verified from official docs and GitHub; railway.toml syntax verified from Railway reference
- Pitfalls: HIGH — all pitfalls derived from direct code inspection (existing router signatures, cookie opts pattern, `as const` usage) combined with official library behavior

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (stable libraries — 30-day window)
