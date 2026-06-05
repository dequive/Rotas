---
phase: 03-manager-dashboard-reporting-layer
plan: "03"
subsystem: api
tags: [redis, arq, cache, control-tower, worker, export-jobs, postgresql]

# Dependency graph
requires:
  - phase: 03-02
    provides: redis[asyncio] and REDIS_URL already in config; control_tower service rewritten with batched queries

provides:
  - Redis cache-aside wrapper (get_ct_cached) in control_tower/service.py; TTL 60s; SET NX EX stampede lock
  - ARQ worker.py with WorkerSettings, startup/shutdown hooks, generate_billing_export stub
  - ExportJob SQLAlchemy model in billing/models.py with two composite indexes
  - Alembic migration d4e5f6a7b8c9 creating export_jobs table

affects:
  - 03-06 (billing PDF/XLSX export — uses ExportJob table and ARQ worker)
  - any plan reading CT summary (now returns cached response within TTL window)

# Tech tracking
tech-stack:
  added: [arq>=0.28 (bumped from 0.26)]
  patterns:
    - Redis cache-aside with SET NX EX stampede lock (prevent duplicate recalculation under concurrent requests)
    - FastAPI lifespan for Redis + ARQ pool lifecycle management
    - Graceful degradation — CT falls back to direct DB when Redis unavailable
    - app.state.redis (plain Redis for GET/SET) vs app.state.arq_redis (ARQ pool for enqueue_job) are distinct objects

key-files:
  created:
    - backend/app/worker.py
    - backend/alembic/versions/d4e5f6a7b8c9_add_export_jobs_table.py
  modified:
    - backend/app/main.py
    - backend/app/modules/control_tower/service.py
    - backend/app/modules/control_tower/router.py
    - backend/app/modules/billing/models.py
    - backend/pyproject.toml
    - backend/tests/test_control_tower_optimized.py

key-decisions:
  - "app.state.redis (redis.asyncio.Redis) and app.state.arq_redis (ArqRedis) are separate objects — never substitute"
  - "Cache key pattern: ct:kpis:{tenant_id}; stampede lock key: ct:kpis:{tenant_id}:lock (ex=10s)"
  - "CT_KPI_TTL=60s; CT_ALERT_TTL=30s constant defined for future alert-specific caching"
  - "ExportJob uses __table_args__ tuple for composite Index declarations (SQLAlchemy pattern)"

patterns-established:
  - "Cache-aside: redis.get → miss → SET NX EX lock → compute → setex TTL → delete lock; contention → direct DB call"
  - "Router extracts redis via getattr(request.app.state, 'redis', None) — safe even before lifespan initializes"

requirements-completed: [CT-02]

# Metrics
duration: 25min
completed: 2026-06-05
---

# Phase 3 Plan 03: Redis Cache-Aside CT-02 + ARQ Worker Scaffold Summary

**Redis cache-aside wrapping Control Tower with 60s TTL + SET NX EX stampede lock; ARQ worker with ExportJob table scaffolded for Plan 06 billing exports**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-05T22:00:00Z
- **Completed:** 2026-06-05T22:25:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- CT-02: `get_ct_cached` wraps `get_control_tower` — second identical request served from Redis, zero DB queries
- Cache stampede prevention via atomic `SET NX EX 10` lock pattern
- ARQ worker scaffolded with `WorkerSettings`, lifespan-managed ARQ pool on `app.state.arq_redis`
- `ExportJob` model with composite indexes for tenant-status and tenant-entity-type lookups
- Alembic migration `d4e5f6a7b8c9` ready to create `export_jobs` table
- 2 CT-02 test stubs (cache_hit, cache_ttl) implemented and green; all 7 CT tests pass

## Task Commits

1. **Task 1: Install arq + wire Redis lifespan in main.py** - `a316559` (feat)
2. **Task 2: CT-02 Redis cache-aside wrapper** - `289e38d` (feat)
3. **Task 3: ARQ worker scaffold + ExportJob model + migration** - `6afec42` (feat)

## Files Created/Modified

- `backend/app/main.py` — Added `@asynccontextmanager lifespan`, Redis + ARQ pool init, graceful degradation
- `backend/app/modules/control_tower/service.py` — Added `get_ct_cached`, `CT_KPI_TTL=60`, `CT_ALERT_TTL=30`, stampede lock
- `backend/app/modules/control_tower/router.py` — Injects `request.app.state.redis`, calls `get_ct_cached`
- `backend/app/modules/billing/models.py` — Appended `ExportJob` model with `__table_args__` composite indexes
- `backend/app/worker.py` — Created: `WorkerSettings`, `generate_billing_export` stub, startup/shutdown hooks
- `backend/alembic/versions/d4e5f6a7b8c9_add_export_jobs_table.py` — Created: migration with 2 indexes
- `backend/pyproject.toml` — Bumped `arq>=0.26` to `arq>=0.28`
- `backend/tests/test_control_tower_optimized.py` — Implemented CT-02 test stubs

## Decisions Made

- `app.state.redis` (plain `redis.asyncio.Redis`) and `app.state.arq_redis` (ARQ pool) are separate objects with distinct roles — never substitute one for the other
- Cache key `ct:kpis:{tenant_id}` with TTL 60s; lock key `ct:kpis:{tenant_id}:lock` with ex=10s to prevent stampede
- Router uses `getattr(request.app.state, "redis", None)` for safe access before lifespan runs
- `ExportJob` `__table_args__` tuple declares both composite indexes inline with the model

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Three pre-existing test failures confirmed not caused by this plan (verified via `git stash`):
- `test_pdf_renders_utf8_characters` — NotImplementedError stub (BILL-01, Plan 06)
- `test_tool_checkout_return_and_critical_calibration_controls` — pre-existing assertion failure
- `test_preventive_maintenance_evaluation_is_idempotent` — pre-existing assertion failure

All 7 CT tests pass. 106/109 tests pass (3 pre-existing failures out of scope).

## User Setup Required

None — no external service configuration required. Redis is already provisioned (port 6381). Worker can be started with `arq app.worker.WorkerSettings` once needed for Plan 06.

## Next Phase Readiness

- CT-02 complete: Control Tower KPIs served from Redis cache, 60s TTL
- ARQ worker importable and wired to Redis; ready for Plan 06 to implement `generate_billing_export`
- `ExportJob` model and migration ready — run `alembic upgrade head` to create the table
- Plan 04 (billing PDF/XLSX) has all scaffolding it needs from this plan

---
*Phase: 03-manager-dashboard-reporting-layer*
*Completed: 2026-06-05*
