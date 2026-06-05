# Phase 1: Security Hardening + Deploy Foundation — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-05
**Phase:** 01-security-hardening-deploy-foundation
**Areas discussed:** Backend deploy platform, Rate limiting approach, Startup validation & test-token bypass, CORS boundary

---

## Backend Deploy Platform

| Option | Description | Selected |
|--------|-------------|----------|
| Railway | ROADMAP already has railway.toml details. Nixpacks auto-detects Python, preDeployCommand runs Alembic, env vars in Railway dashboard. Best for speed. | ✓ |
| Render | render.yaml config, similar CI/CD. Slightly more infra YAML. | |
| Either — you decide | Leave it to the planner. | |

**User's choice:** Railway (Recommended)
**Notes:** Default plan (Hobby), nearest region, service name derived from repo.

---

## Rate Limiting Approach

### Library choice

| Option | Description | Selected |
|--------|-------------|----------|
| slowapi in-memory | Add slowapi, per-IP limits, in-memory store. Simple, no Redis dependency. | ✓ |
| slowapi + Redis backend | Redis as rate limit store. Survives process restarts. Requires REDIS_URL. | |

**User's choice:** slowapi in-memory

### Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| 10/minute | Blocks brute-force, permissive enough for real users. Standard for login endpoints. | ✓ |
| 5/minute | Stricter. Could false-positive on slow mobile connections. | |
| You decide | Leave thresholds to the planner. | |

**User's choice:** 10 requests/minute per IP

---

## Startup Validation & Test-Token Bypass

### Required env vars at startup

| Option | Description | Selected |
|--------|-------------|----------|
| Core 3 only | JWT_SECRET_KEY, DATABASE_URL, ENVIRONMENT. REDIS_URL and R2_* optional. | ✓ |
| Core 3 + REDIS_URL + R2_* | Strict production checklist. All infra vars required. | |

**User's choice:** Core 3 only

### Test-token bypass fate

| Option | Description | Selected |
|--------|-------------|----------|
| Gate by ENVIRONMENT=production | Bypass stays in dev, disabled in production. Zero test migration work. | ✓ |
| Remove entirely + update tests | Cleaner security posture but 17 test files need new JWT fixture. | |

**User's choice:** Gate by ENVIRONMENT=production

---

## CORS Boundary

### Allowed origins

| Option | Description | Selected |
|--------|-------------|----------|
| Production domain only | Explicit Vercel production URL only. No wildcards. Fail-closed if CORS_ORIGINS not set. | ✓ |
| Production + Vercel preview URLs | Also allow *.vercel.app for staging. Broader attack surface. | |

**User's choice:** Production domain only

### Domain name

| Option | Description | Selected |
|--------|-------------|----------|
| Vercel-assigned URL for now | Use whatever Vercel assigns. Updatable via env var later. | ✓ |
| Custom domain | User provides custom domain. | |

**User's choice:** Vercel-assigned URL for now

---

## Claude's Discretion

- Specific PyJWT and slowapi version pins
- Exact railway.toml service name and region
- Structure of startup validation (model_validator vs post_init)
- Exact tenant IDs for cross-tenant regression tests

## Deferred Ideas

- Test suite migration from test-token to real JWT fixtures (Phase 1 only gates by ENVIRONMENT)
- PostgreSQL RLS as second isolation layer (Phase 4)
- Redis-backed rate limiting (post-MVP multi-worker)
- billing-api.ts ROTAS_MANAGER_TOKEN escape hatch removal (may slip to Phase 2)
- Password reset flow (out of scope for Phase 1)
