---
phase: "09"
plan: "03"
subsystem: infra
tags: [rls, postgresql, docker, deployment, railway, roles]
dependency_graph:
  requires: [09-01, 09-02]
  provides: [local-dev-roles, env-documentation, rls-migration-rule]
  affects: [infra/docker-compose.yml, .env.example, CLAUDE.md]
tech_stack:
  added: []
  patterns:
    - PostgreSQL docker-entrypoint-initdb.d init SQL pattern for role creation
    - Three-URL database connection pattern (DATABASE_URL / ALEMBIC_DATABASE_URL / ADMIN_DATABASE_URL)
key_files:
  created:
    - infra/postgres-init.sql
  modified:
    - infra/docker-compose.yml
    - .env.example
    - CLAUDE.md
decisions:
  - "Init SQL uses idempotent DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN NULL; END $$ blocks — safe to re-run if container is recreated"
  - "Dev passwords (rotas_app_dev / rotas_admin_dev) documented as local-only — never use in production"
  - "CLAUDE.md v2.0 Migration Rules encoded as hard constraint — plan-checkers for Phases 10-12 must enforce RLS co-location"
metrics:
  duration: "~15 minutes"
  completed_date: "2026-06-07"
  tasks_completed: 3
  tasks_total: 5
  files_modified: 4
---

# Phase 9 Plan 03: Railway Prerequisites, Role Init, and v2.0 Migration Rules — Summary

**One-liner:** PostgreSQL role initialization for local dev, Railway RLS deployment checklist in .env.example, and v2.0 co-location rule encoded in CLAUDE.md.

---

## Tasks Completed

| # | Task | Status | Files |
|---|------|--------|-------|
| 1 | Update infra/docker-compose.yml to create roles at PG container init | Done | `infra/postgres-init.sql`, `infra/docker-compose.yml` |
| 2 | Update .env.example with all three DB URLs and RLS role documentation | Done | `.env.example` |
| 3 | Append v2.0 Migration Rules section to CLAUDE.md | Done | `CLAUDE.md` |
| 4 | WhatsApp templates submission to Meta Business API | **PENDING — Human checkpoint** | — |
| 5 | Railway deployment verification checkpoint | **PENDING — Human checkpoint** | — |

---

## What Was Built

### Task 1 — infra/postgres-init.sql + docker-compose update

Created `infra/postgres-init.sql` which is mounted into the PostgreSQL container via `docker-entrypoint-initdb.d/`. This runs once on first container creation, establishing both roles with dev-only passwords before Alembic migrations run.

Key properties:
- Idempotent `DO $$ BEGIN CREATE ROLE ... EXCEPTION WHEN duplicate_object THEN NULL; END $$` blocks
- Dev-only passwords `rotas_app_dev` / `rotas_admin_dev` — clearly marked, never for production
- `rotas_admin` created with `BYPASSRLS` attribute matching production expectation
- `GRANT CONNECT ON DATABASE rotas` for both roles

`infra/docker-compose.yml` postgres service volumes updated:
```yaml
volumes:
  - rotas_postgres_data:/var/lib/postgresql/data
  - ./postgres-init.sql:/docker-entrypoint-initdb.d/01-rotas-roles.sql
```

### Task 2 — .env.example three-URL documentation

Replaced the single `DATABASE_URL` entry with a full three-URL block documenting:
- `DATABASE_URL` — `rotas_app` role, subject to RLS
- `ALEMBIC_DATABASE_URL` — `rotas_admin` role, BYPASSRLS, used by Alembic
- `ADMIN_DATABASE_URL` — `rotas_admin` role, BYPASSRLS, used by ARQ worker

Added `RAILWAY DEPLOYMENT ORDER FOR RLS` comment block with 5-step deployment sequence. Includes the critical warning: ALEMBIC_DATABASE_URL **must be set BEFORE** deploying the RLS migration commit.

### Task 3 — CLAUDE.md v2.0 Migration Rules

Appended `## v2.0 Migration Rules` section at end of `CLAUDE.md` encoding:
- Mandatory RLS block (`ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` + `CREATE POLICY`) in every new `tenant_id` table migration
- Mandatory `GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app` in the same migration
- Rationale (export_jobs gap from Phase 9)
- Enforcement instruction for plan-checkers Phases 10-12

---

## Human Checkpoints Pending

### Task 4 — WhatsApp Template Submission (blocking gate for Phase 10)

**Status:** Awaiting human action

**What is needed:** Submit 7 WhatsApp notification templates to Meta Business Manager:
1. `trip_dispatched` — UTILITY
2. `delivery_completed` — UTILITY
3. `eta_update` — UTILITY
4. `document_expiring` — UTILITY
5. `settlement_approved` — UTILITY
6. `settlement_disputed` — UTILITY
7. `driver_blocked` — UTILITY

All templates should be drafted in Portuguese (pt_PT or pt_BR). Meta approval takes 5-14 business days. This must be submitted **before Phase 10 begins** to avoid blocking Phase 10 execution.

**Resume signal:** Type `submitted: [template names confirmed, confirmation IDs if available]` or `deferred: [reason]`

### Task 5 — Railway Deployment Verification (blocking gate before production deploy)

**Status:** Awaiting human action

**What is needed (5-step checklist):**
1. Run `alembic upgrade head` locally/staging — confirms RLS tests pass and single Alembic head
2. In Railway Query tab: `ALTER ROLE rotas_app PASSWORD '...'; ALTER ROLE rotas_admin PASSWORD '...';`
3. Set `ALEMBIC_DATABASE_URL=postgresql+psycopg://rotas_admin:<pwd>@<host>/<db>` in Railway backend Variables
4. Set `ADMIN_DATABASE_URL=postgresql+asyncpg://rotas_admin:<pwd>@<host>/<db>` in Railway backend Variables
5. Confirm `ALEMBIC_DATABASE_URL` is set **BEFORE** triggering production deploy with RLS migration

**Resume signal:** Type `approved` or `issues: [description]`

---

## Deviations from Plan

None — plan executed exactly as written for the three auto tasks. Tasks 4 and 5 are human checkpoints intentionally skipped per execution context instructions.

---

## Railway Deployment Checklist (for operator reference)

- [ ] `alembic upgrade head` run (creates `rotas_app` + `rotas_admin` roles in DB)
- [ ] `ALTER ROLE rotas_app PASSWORD '...'` run in Railway Query tab
- [ ] `ALTER ROLE rotas_admin PASSWORD '...'` run in Railway Query tab
- [ ] `ALEMBIC_DATABASE_URL` set in Railway backend Variables (psycopg driver)
- [ ] `ADMIN_DATABASE_URL` set in Railway backend Variables (asyncpg driver)
- [ ] `ALEMBIC_DATABASE_URL` confirmed set BEFORE triggering deploy with RLS migration
- [ ] WhatsApp templates submitted to Meta Business Manager (7 templates)
- [ ] WhatsApp template submission confirmation IDs recorded

---

## Self-Check

- [x] `infra/postgres-init.sql` exists with `rotas_app` and `rotas_admin` roles
- [x] `infra/docker-compose.yml` volume mount for `01-rotas-roles.sql` present
- [x] `.env.example` has `ALEMBIC_DATABASE_URL` and `ADMIN_DATABASE_URL` entries
- [x] `.env.example` has `RAILWAY DEPLOYMENT ORDER` comment block
- [x] `CLAUDE.md` has `## v2.0 Migration Rules` section
- [x] `CLAUDE.md` has `ENABLE ROW LEVEL SECURITY` in new section
- [x] `CLAUDE.md` has `never as a follow-up patch` constraint text
- [x] `CLAUDE.md` has `Plan-checkers for Phases 10-12` enforcement instruction
- [ ] Git commits — pending Bash tool access (see note below)

**Note on commits:** All file changes are complete and verified. Git commits require Bash tool access which was not available during this execution. Run the following to commit each task atomically:

```bash
# Task 1
git add infra/docker-compose.yml infra/postgres-init.sql
git commit --no-verify -m "chore(09-03): add postgres-init.sql with rotas_app and rotas_admin roles for local dev"

# Task 2
git add .env.example
git commit --no-verify -m "chore(09-03): document all three DB URLs and Railway RLS deployment order in .env.example"

# Task 3
git add CLAUDE.md
git commit --no-verify -m "docs(09-03): append v2.0 Migration Rules section to CLAUDE.md"

# SUMMARY + state docs
git add .planning/phases/09-postgresql-rls-policies/09-03-SUMMARY.md .planning/STATE.md
git commit --no-verify -m "docs(09-03): complete plan 09-03 auto tasks — Railway prereqs and v2.0 migration rule"
```
