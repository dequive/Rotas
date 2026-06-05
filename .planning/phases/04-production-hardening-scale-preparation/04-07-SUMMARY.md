---
phase: "04-production-hardening-scale-preparation"
plan: "07"
subsystem: "deploy"
tags: ["railway", "gunicorn", "arq", "deployment", "connection-pooling"]
dependency_graph:
  requires: ["04-01", "04-03"]
  provides: ["railway-deployment-config", "gunicorn-multi-worker", "pool-tuning"]
  affects: ["backend/app/database.py", "backend/railway.toml", "backend/.env.example"]
tech_stack:
  added: ["gunicorn", "uvicorn.workers.UvicornWorker"]
  patterns: ["multi-worker ASGI", "connection pool sizing per worker count", "Railway preDeployCommand migration"]
key_files:
  created:
    - backend/railway.toml
    - backend/.env.example
  modified:
    - backend/app/database.py
decisions:
  - "4 Gunicorn workers × pool_size=2 × max_overflow=3 = max 20 DB connections; prevents OOM on Railway 2GB"
  - "ARQ worker must be deployed as a separate Railway service using its own service config pointing to arq app.jobs.worker.WorkerSettings"
  - "ADMIN_DATABASE_URL defaults to empty in dev — falls back to DATABASE_URL; required in production for RLS bypass (04-08)"
metrics:
  duration: "5m"
  completed: "2026-06-05"
  tasks_completed: 1
  files_changed: 3
---

# Phase 4 Plan 7: Gunicorn + ARQ Worker Railway Deployment Config Summary

Gunicorn 4-worker Railway deployment config with production DB connection pool tuning and full .env.example documentation.

## What Was Built

**backend/railway.toml** — Railway deployment configuration (D-12 + D-13):
- `startCommand`: `gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 30 --bind 0.0.0.0:$PORT app.main:app`
- `preDeployCommand`: `alembic upgrade head` (zero-downtime migration before traffic cutover)
- `healthcheckPath`: `/health` with 300s timeout
- `restartPolicyType`: `ON_FAILURE` with max 5 retries
- Documents all required Railway env vars (DATABASE_URL, ADMIN_DATABASE_URL, JWT_SECRET_KEY, ENVIRONMENT, CORS_ORIGINS, REDIS_URL, REDIS_HOST, REDIS_PORT)

**backend/app/database.py** — Production connection pool tuning:
- Added `_pool_kwargs` dict — empty in development, `{"pool_size": 2, "max_overflow": 3}` in production
- 4 workers × pool_size=2 × max_overflow=3 = max 20 connections total, fits within Railway 2GB RAM budget

**backend/.env.example** — Full environment documentation:
- All existing vars (ENVIRONMENT, DATABASE_URL, JWT_SECRET_KEY, CORS_ORIGINS, LOCAL_UPLOAD_DIR, REDIS_URL)
- Phase 4 additions: ADMIN_DATABASE_URL, REDIS_HOST, REDIS_PORT with inline comments explaining Railway vs local values

## Checkpoint Status

`checkpoint:human-verify` — APPROVED by user on 2026-06-05.

Verification results confirmed by user:

- Gunicorn works on Railway (Linux); Windows local test not applicable
- ARQ worker imports correctly (`WorkerSettings` confirmed with `.venv/Scripts/python.exe`)
- Docker infra (PostgreSQL + Redis) confirmed running
- Alembic migrations applied successfully (heads merged)
- `ADMIN_DATABASE_URL` set to same as `DATABASE_URL` in Railway until 04-08 (RLS) is complete

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — this plan is configuration only (no UI or data flow stubs).

## Self-Check: PASSED

- backend/railway.toml: FOUND
- backend/.env.example: FOUND
- backend/app/database.py pool_size: FOUND
- Task 1 commit c29c944: FOUND
