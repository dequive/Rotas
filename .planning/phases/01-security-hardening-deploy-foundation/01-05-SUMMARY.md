---
phase: 01-security-hardening-deploy-foundation
plan: 05
subsystem: infra
tags: [railway, vercel, deploy, nodejs, alembic, docker]

requires:
  - phase: 01-02
    provides: "Config hardening — DATABASE_URL, ENVIRONMENT, CORS_ORIGINS all required"
provides:
  - "railway.toml: preDeployCommand=alembic upgrade head, uvicorn startCommand with $PORT"
  - "backend/__init__.py: backend.app.main:app module path enabled"
  - "apps/manager/vercel.json: framework=nextjs for Vercel monorepo detection"
  - "engines.node=20.x in root and manager package.json"
  - "NEXT_PUBLIC_API_URL rename in api.ts and auth.ts (Vercel build-time exposure)"
  - ".env.example updated with all required vars"
affects: [01-06]

tech-stack:
  added: []
  patterns: [railway-toml-config, vercel-json-framework, node-engines-declaration]

key-files:
  created:
    - railway.toml
    - backend/__init__.py
    - apps/manager/vercel.json
  modified:
    - .env.example
    - package.json
    - apps/manager/package.json
    - apps/manager/app/lib/api.ts
    - apps/manager/app/lib/auth.ts

key-decisions:
  - "NEXT_PUBLIC_ prefix required for Vercel to expose env var to Next.js browser bundle — ROTAS_API_BASE_URL was server-only"
  - "preDeployCommand as array ['alembic upgrade head'] — Railway docs specify array format"
  - "backend/__init__.py as package marker enables uvicorn backend.app.main:app from repo root"
  - "Railway DATABASE_URL must use postgresql+asyncpg:// — alembic/env.py auto-converts to psycopg"

patterns-established:
  - "Railway startCommand uses $PORT env var — never hardcode port"
  - "healthcheckPath = /health to delay traffic routing until app is ready"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04]

duration: 12min
completed: 2026-06-05
---

# Plan 01-05: Deploy Configuration Summary

**Railway + Vercel deploy config created: railway.toml with Alembic pre-deploy, vercel.json for Next.js, Node 20.x declared, NEXT_PUBLIC_API_URL wired**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-06-05T00:52:00Z
- **Completed:** 2026-06-05T01:04:00Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- railway.toml: Alembic runs before traffic, uvicorn starts with $PORT
- backend/__init__.py: backend.app.main:app module path enabled
- apps/manager/vercel.json: Vercel detects Next.js framework
- Both package.json: engines.node=20.x prevents version mismatch
- api.ts + auth.ts: NEXT_PUBLIC_API_URL exposes backend URL to Next.js build
- .env.example updated with full documentation
- 67/67 tests still pass

## Task Commits

1. **Task 1: Railway config, backend init, env.example** - `b957b7d` (feat)
2. **Task 2: Vercel config, engines, API URL rename** - `d2fce8c` (feat)

## Files Created/Modified
- `railway.toml` — Railway deployment configuration
- `backend/__init__.py` — package marker for uvicorn module path
- `apps/manager/vercel.json` — Vercel framework detection
- `package.json` — engines.node=20.x
- `apps/manager/package.json` — engines.node=20.x
- `apps/manager/app/lib/api.ts` — NEXT_PUBLIC_API_URL
- `apps/manager/app/lib/auth.ts` — NEXT_PUBLIC_API_URL (2 occurrences)
- `.env.example` — comprehensive env var reference

## Decisions Made
- NEXT_PUBLIC_API_URL required for Vercel browser bundle (server-only ROTAS_API_BASE_URL was invisible to browser)
- preDeployCommand array format per Railway docs

## Deviations from Plan
None.

## Issues Encountered
None — TypeScript check and full test suite passed on first run.

## Next Phase Readiness
- All config artifacts ready for Plan 01-06 (actual Railway + Vercel deployment)
- Plan 01-06 is a human-action checkpoint requiring Railway and Vercel accounts

---
*Phase: 01-security-hardening-deploy-foundation*
*Completed: 2026-06-05*
