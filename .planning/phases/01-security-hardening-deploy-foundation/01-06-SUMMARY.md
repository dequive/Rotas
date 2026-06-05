---
phase: 01-security-hardening-deploy-foundation
plan: 06
subsystem: infra
tags: [railway, vercel, deploy, deferred]

requires:
  - phase: 01-05
    provides: "railway.toml, vercel.json, NEXT_PUBLIC_API_URL, engines.node"
provides:
  - "DEFERRED — deploy infrastructure config exists but actual production deploy not yet executed"
affects: []

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: []

key-decisions:
  - "Deploy deferred by user decision — Phase 1 security hardening complete, product still in active development"
  - "Deploy config artifacts (railway.toml, vercel.json, .env.example) are ready when deployment is needed"

patterns-established: []

requirements-completed: []

duration: 0min
completed: 2026-06-05
deferred: true
defer_reason: "Product still in active development — deploy will be executed in a dedicated deploy session"
---

# Plan 01-06: Production Deploy Summary

**DEFERRED — Deploy config artifacts ready; actual Railway + Vercel deployment deferred by user decision**

## Status

Skipped at user request. Product is still in active development and production deploy is not yet needed.

## What's Ready (from Plan 01-05)

All infrastructure config artifacts are in place:
- `railway.toml` — preDeployCommand=alembic upgrade head, uvicorn startCommand
- `apps/manager/vercel.json` — framework=nextjs, Root Directory=apps/manager
- `NEXT_PUBLIC_API_URL` wired in api.ts and auth.ts
- `engines.node=20.x` in both package.json files
- `.env.example` documents all required Railway and Vercel env vars

## Steps Required When Deploying

See Plan 01-06 task descriptions:
1. Railway: connect repo, set ENVIRONMENT/JWT_SECRET_KEY/DATABASE_URL/CORS_ORIGINS, trigger deploy
2. Vercel: import repo, set Root Directory=apps/manager, set NEXT_PUBLIC_API_URL, trigger deploy
3. Update Railway CORS_ORIGINS with the Vercel URL, redeploy

## Requirements Status

- DEPLOY-02 (Railway config): ✓ Config created, deploy pending
- DEPLOY-03 (Vercel config): ✓ Config created, deploy pending
- DEPLOY-04 (migrations auto-run): ✓ preDeployCommand configured, execution pending

---
*Phase: 01-security-hardening-deploy-foundation*
*Deferred: 2026-06-05*
