---
phase: 09-postgresql-rls-policies
verified: 2026-06-07T00:00:00Z
status: passed
score: 5/5 must-haves verified
gaps: []
human_verification:
  - test: "Run alembic upgrade head against production Railway DB"
    expected: "Single head (a9b8c7d6e5f4), RLS policies visible in pg_policies for all 47 tables"
    why_human: "Cannot execute alembic upgrade against production DB programmatically"
  - test: "Railway: CREATE ROLE / ALTER ROLE rotas_app and rotas_admin with production passwords"
    expected: "Both roles exist with BYPASSRLS on rotas_admin, RLS-enforced on rotas_app"
    why_human: "Requires manual Railway Query console access"
  - test: "Set ALEMBIC_DATABASE_URL and ADMIN_DATABASE_URL in Railway Variables before RLS migration deploy"
    expected: "Alembic and ARQ worker connect as rotas_admin (BYPASSRLS), not rotas_app"
    why_human: "Railway Variables UI — cannot automate"
---

# Phase 9: PostgreSQL RLS Policies — Verification Report

**Phase Goal:** PostgreSQL RLS for all tenant-scoped tables, Alembic multi-head resolved, Railway deployment prerequisites documented.
**Verified:** 2026-06-07
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | RLS + tenant_isolation policy on all 46 core tenant-scoped tables | VERIFIED | `4b0a7802dc3c_add_rls_policies.py` iterates over 46-table `TENANT_SCOPED_TABLES` list, calls `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY`, and `CREATE POLICY tenant_isolation` for each |
| 2 | export_jobs table has RLS policy (gap-closure) | VERIFIED | `e1f2a3b4c5d6_add_rls_to_export_jobs.py` applies RLS + FORCE RLS + `CREATE POLICY tenant_isolation` + `GRANT ... TO rotas_app` on `export_jobs` |
| 3 | Alembic multi-head resolved to single head | VERIFIED | `python -m alembic heads` returns one head: `a9b8c7d6e5f4`. Merge migration `147542222231_merge_rls_and_export_jobs.py` resolves `b7e2a9c4d1f3` and `d4e5f6a7b8c9` into a linear chain |
| 4 | database.py injects `SET LOCAL app.tenant_id` per request for RLS enforcement | VERIFIED | `_rls_tenant` ContextVar set by `set_rls_tenant()` in `app/core/deps.py::get_session`. `after_begin` event listener in `database.py` executes `SET LOCAL app.tenant_id = '{tid}'` on every transaction. `get_session_raw()` deliberately excluded (auth routes have no tenant yet) |
| 5 | Railway deployment prerequisites documented | VERIFIED | `.env.example` has 3-URL block (DATABASE_URL / ALEMBIC_DATABASE_URL / ADMIN_DATABASE_URL) with Railway 5-step deployment order. `infra/postgres-init.sql` mounts into `docker-entrypoint-initdb.d/`. `CLAUDE.md` has `## v2.0 Migration Rules` section with mandatory RLS co-location rule for future migrations |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` | VERIFIED | 46 tables, idempotent DO-block policy creation, role creation with BYPASSRLS |
| `backend/alembic/versions/147542222231_merge_rls_and_export_jobs.py` | VERIFIED | down_revision is a tuple `('b7e2a9c4d1f3', 'd4e5f6a7b8c9')` — correct merge head |
| `backend/alembic/versions/e1f2a3b4c5d6_add_rls_to_export_jobs.py` | VERIFIED | export_jobs: ENABLE RLS, FORCE RLS, CREATE POLICY tenant_isolation, GRANT to rotas_app |
| `backend/app/database.py` | VERIFIED | `_rls_tenant` ContextVar, `set_rls_tenant()`, `after_begin` event fires `SET LOCAL app.tenant_id` |
| `backend/app/core/deps.py` | VERIFIED | `get_session()` calls `set_rls_tenant(str(principal.tenant_id))`, clears in finally block |
| `backend/app/worker.py` | VERIFIED | Uses `resolved_admin_database_url` (BYPASSRLS admin role), stores engine for cleanup in shutdown |
| `backend/app/config.py` | VERIFIED | `resolved_admin_database_url` property: falls back to `database_url` when `ADMIN_DATABASE_URL` unset |
| `backend/tests/test_rls.py` | VERIFIED | 5 tests: policy existence, SET LOCAL scoping, cross-tenant trip access, 47-table completeness gate, DB-role vehicle isolation (asyncpg direct connect with pytest.skip guard) |
| `infra/postgres-init.sql` | VERIFIED | Idempotent DO blocks for rotas_app + rotas_admin roles, dev passwords, GRANT CONNECT |
| `infra/docker-compose.yml` | VERIFIED | Volume mount `./postgres-init.sql:/docker-entrypoint-initdb.d/01-rotas-roles.sql` present |
| `.env.example` | VERIFIED | 3-URL block with RAILWAY DEPLOYMENT ORDER comment (5-step checklist) |
| `CLAUDE.md` | VERIFIED | `## v2.0 Migration Rules` section appended with ENABLE RLS + FORCE RLS + GRANT co-location mandate |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `deps.py::get_session` | `database.py::set_rls_tenant` | Direct import + call | WIRED | `set_rls_tenant(str(principal.tenant_id))` called before yielding session, cleared in finally |
| `database.py::after_begin` | PostgreSQL `SET LOCAL app.tenant_id` | SQLAlchemy event | WIRED | Event fires on every AsyncSession transaction start, reads `_rls_tenant` ContextVar |
| `worker.py::startup` | `config.py::resolved_admin_database_url` | Settings property | WIRED | `_settings.resolved_admin_database_url` used to create admin_engine; fallback to `database_url` in local dev |
| Alembic chain | `e1f2a3b4c5d6` (export_jobs RLS) | `147542222231` merge head → `e1f2a3b4c5d6` | WIRED | Migration chain is linear: merge → export_jobs RLS → `f0a1b2c3d4e5` → `a9b8c7d6e5f4` (current head) |

---

### Data-Flow Trace (Level 4)

Not applicable — this phase delivers database security infrastructure (migrations, session wiring, config) rather than data-rendering components. No UI components or API routes that render dynamic user data were added in this phase.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Single Alembic head | `python -m alembic heads` | `a9b8c7d6e5f4 (head)` | PASS |
| Merge migration resolves two-head split | down_revision in 147542222231 | `('b7e2a9c4d1f3', 'd4e5f6a7b8c9')` (tuple) | PASS |
| export_jobs gap-closure migration exists and has correct down_revision | `e1f2a3b4c5d6` down_revision | `147542222231` | PASS |
| worker.py uses BYPASSRLS admin URL, not AsyncSessionLocal | Inspect worker.py startup | `create_async_engine(_settings.resolved_admin_database_url)` — no AsyncSessionLocal import | PASS |
| SET LOCAL is transaction-scoped (not session-scoped) | Inspect after_begin event | `SET LOCAL app.tenant_id` (not `SET app.tenant_id`) | PASS |

---

### Requirements Coverage

No explicit `requirements:` frontmatter found in PLAN files. Coverage assessed from phase goal directly.

| Requirement | Status | Evidence |
|-------------|--------|----------|
| RLS on all tenant-scoped tables | SATISFIED | 46 tables in `4b0a7802dc3c` + `export_jobs` in `e1f2a3b4c5d6` |
| Alembic single head | SATISFIED | `alembic heads` confirms one head |
| Session injects SET LOCAL app.tenant_id | SATISFIED | `after_begin` event + `set_rls_tenant` ContextVar pattern in `database.py` + `deps.py` |
| ARQ worker uses BYPASSRLS connection | SATISFIED | `worker.py::startup` uses `resolved_admin_database_url` |
| Railway deployment prerequisites documented | SATISFIED | `.env.example` 3-URL block + 5-step Railway checklist + `CLAUDE.md` v2.0 rules |

---

### Anti-Patterns Found

| File | Pattern | Severity | Assessment |
|------|---------|----------|------------|
| `test_rls.py` comment on `test_rls_blocks_cross_tenant_vehicle_access` | "Expected: RED until plan 09-02 migration applies" | INFO | Stale comment — plan 09-02 is complete and the migration has been applied. Comment is misleading but does not affect behavior. |

No blockers. No stub implementations. No placeholder returns.

---

### Human Verification Required

#### 1. Production Railway migration run

**Test:** Run `alembic upgrade head` against Railway PostgreSQL
**Expected:** Completes without error; `SELECT tablename FROM pg_policies WHERE policyname = 'tenant_isolation' ORDER BY tablename` returns all 47 tables
**Why human:** Cannot execute Alembic against production DB programmatically

#### 2. Railway role password assignment

**Test:** In Railway Query console: `ALTER ROLE rotas_app PASSWORD '...'; ALTER ROLE rotas_admin PASSWORD '...';`
**Expected:** Roles exist (created by migration `4b0a7802dc3c`), passwords set to production values
**Why human:** Requires Railway console access and production secret management

#### 3. Railway Variables pre-deploy check

**Test:** Confirm `ALEMBIC_DATABASE_URL` and `ADMIN_DATABASE_URL` are set in Railway Variables **before** triggering production deploy with RLS migration
**Expected:** Alembic connects as `rotas_admin` (BYPASSRLS), ARQ worker connects as `rotas_admin`
**Why human:** Railway Variables UI — deployment ordering constraint cannot be automated

---

### Gaps Summary

No gaps. All 5 must-have truths are verified against actual code:

1. The main RLS migration (`4b0a7802dc3c`) correctly enables RLS and creates `tenant_isolation` policies on 46 tables using an idempotent DO-block pattern.
2. The export_jobs gap-closure migration (`e1f2a3b4c5d6`) exists and is substantive — it applies RLS, FORCE RLS, the policy, and GRANT to rotas_app.
3. The merge migration (`147542222231`) resolves the two-head split; `alembic heads` confirms one head.
4. The `SET LOCAL app.tenant_id` injection is properly wired: ContextVar set by `deps.py::get_session`, read by the `after_begin` event in `database.py`.
5. Railway prerequisites are fully documented in `.env.example` (3-URL block + deployment checklist) and `CLAUDE.md` (v2.0 migration rules).

Three human checkpoints remain for production deployment but are not blockers to phase completion — they are operator actions, not code gaps.

---

_Verified: 2026-06-07_
_Verifier: Claude (gsd-verifier)_
