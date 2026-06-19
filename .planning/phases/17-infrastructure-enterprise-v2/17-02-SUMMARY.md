---
phase: 17-infrastructure-enterprise-v2
plan: "02"
subsystem: infra
tags: [prometheus, metrics, health-check, arq, redis, fastapi, monitoring]

# Dependency graph
requires:
  - phase: 17-01
    provides: [structlog, redis rate limiter, ARQ worker startup/shutdown lifecycle]
provides:
  - INFRA2-03 — /metrics endpoint (Prometheus, http_requests_total, histograms, rotas_active_tenants_total)
  - INFRA2-04 — /health/deep endpoint (DB + Redis + ARQ worker checks, HTTP 503 on degraded)
  - ARQ worker heartbeat via Redis key arq:health:worker_heartbeat (TTL 90s)
  - ARQ cron: task_update_active_tenants_metric (every 5 min) + task_worker_heartbeat (every minute)
affects: [monitoring, alerting, deployment, grafana-dashboards]

# Tech tracking
tech-stack:
  added:
    - prometheus-fastapi-instrumentator>=7.0 (metrics exposure + auto-instrumentation)
    - prometheus_client (Gauge for rotas_active_tenants_total)
  patterns:
    - Instrumentator.expose() pattern — never add manual @app.get("/metrics") (causes duplicate)
    - ARQ heartbeat pattern — setex with 3x TTL of interval (90s for 30s heartbeat)
    - /health stays ultra-lightweight (always 200); /health/deep does full dependency check
    - asyncio.wait_for() with timeout=2.0 for DB check, timeout=1.0 for Redis ping
    - app.state.engine exposed for use in health check (set in lifespan before yield)

key-files:
  created: []
  modified:
    - backend/app/main.py (Prometheus integration, /health/deep endpoint, engine in app.state)
    - backend/app/worker.py (task_update_active_tenants_metric, task_worker_heartbeat, cron registrations)
    - backend/pyproject.toml (prometheus-fastapi-instrumentator>=7.0 dependency declared)

key-decisions:
  - "Prometheus Instrumentator configured with excluded_handlers=[/metrics, /health, /health/deep] — prevents these ops endpoints from polluting route histogram buckets"
  - "/health remains always-200 for Railway TCP probe; /health/deep is the real monitoring endpoint"
  - "ARQ worker heartbeat uses minute granularity cron (every minute via set(range(60))) — ARQ cron does not support second-level granularity in stable versions"
  - "arq:health:worker_heartbeat TTL=90s (3x the 30s target interval) — dead after 3 missed beats, tolerates transient slowness"
  - "rotas_active_tenants_total Gauge registered at app startup in lifespan (before yield) so it is in the Prometheus registry from first /metrics request; worker cron updates the value every 5 min"
  - "prometheus_client Gauge in worker wrapped in try/except — allows worker to run in envs without prometheus_client"
  - "Startup also sets initial heartbeat key in on_startup so /health/deep does not report stale on first check immediately after deploy"

patterns-established:
  - "Health split: /health (always 200, Railway probe) vs /health/deep (full dependency check, for Grafana/Datadog alerts)"
  - "Worker heartbeat pattern: cron task writes to Redis with TTL=3x interval; API reads and compares age"

requirements-completed: [INFRA2-03, INFRA2-04]

# Metrics
duration: 10min
completed: "2026-06-19"
---

# Phase 17 Plan 02: Prometheus Metrics + Deep Health Check Summary

**Prometheus /metrics endpoint auto-instrumenting all FastAPI routes (histograms, request counters, in-progress gauge) plus /health/deep checking DB, Redis, and ARQ worker liveness with HTTP 503 on any failure.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-19T16:17:00Z
- **Completed:** 2026-06-19T16:27:00Z
- **Tasks:** 5
- **Files modified:** 3

## Accomplishments

- `prometheus-fastapi-instrumentator>=7.0` declared in `pyproject.toml` and integrated in lifespan — `/metrics` exposes `http_requests_total`, `http_request_duration_seconds_bucket` (p50/p95/p99 calculable in Grafana), and `http_requests_inprogress`
- Custom `rotas_active_tenants_total` Gauge registered at startup; updated every 5 minutes by `task_update_active_tenants_metric` ARQ cron
- `/health/deep` endpoint checks DB (2s timeout via `asyncio.wait_for`), Redis (1s timeout), and ARQ worker heartbeat (reads `arq:health:worker_heartbeat` Redis key, stale after 90s); returns HTTP 503 with JSON body on any failure
- `task_worker_heartbeat` ARQ cron writes ISO timestamp to `arq:health:worker_heartbeat` with TTL=90s every minute; initial heartbeat also written in `on_startup` to prevent false stale on deploy
- `/health` endpoint kept as ultra-lightweight always-200 probe for Railway TCP health check

## Task Commits

All 5 tasks were already committed in a prior session (same pattern as Plan 17-01 — implementation completed before GSD execution). Verified against HEAD:

1. **Task 1: Install prometheus-fastapi-instrumentator** — `pyproject.toml` line `prometheus-fastapi-instrumentator>=7.0` present in HEAD (commit `0d26655`)
2. **Task 2: Prometheus integration in main.py** — `Instrumentator`, `_instrumentator.instrument(app)`, `_instrumentator.expose(app, endpoint="/metrics")`, `rotas_active_tenants_total` Gauge all present in HEAD
3. **Task 3: task_update_active_tenants_metric cron** — function + WorkerSettings registration in HEAD
4. **Task 4: task_worker_heartbeat cron** — function + `arq:health:worker_heartbeat` setex + cron registration in HEAD
5. **Task 5: /health/deep endpoint** — full dependency check with asyncio.wait_for timeouts + JSON 503 response in HEAD

**Plan metadata commit:** created in this execution (docs commit below)

## Files Created/Modified

- `backend/app/main.py` — Added Prometheus imports (`Instrumentator`, `Gauge`), lifespan block for Instrumentator setup + gauge registration, `app.state.engine = _engine`, `/health/deep` endpoint with full 3-way check
- `backend/app/worker.py` — `task_update_active_tenants_metric` (every 5 min cron updating Prometheus gauge via admin DB session), `task_worker_heartbeat` (every-minute cron writing heartbeat to Redis), both registered in `WorkerSettings.functions` and `WorkerSettings.cron_jobs`; initial heartbeat written in `startup()`
- `backend/pyproject.toml` — `prometheus-fastapi-instrumentator>=7.0` added to dependencies

## Decisions Made

- Prometheus `Instrumentator` configured with `excluded_handlers=["/metrics", "/health", "/health/deep"]` — prevents ops endpoints from polluting route histogram buckets and creating high-cardinality label noise
- `/health` kept always-200 (no dependencies checked) — Railway TCP probe must never return non-200 due to a Redis blip
- ARQ heartbeat cron uses `minute=set(range(60))` (every-minute) instead of `second=30` — ARQ stable versions do not support second-level cron granularity; every-minute is the closest available
- TTL for heartbeat key is 90s (3x the effective 30s target) — tolerates transient ARQ slowness without false-positive stale detection
- `prometheus_client.Gauge` in worker wrapped in `try/except` — allows worker to function in test environments where `prometheus_client` may not be available

## Deviations from Plan

None — plan executed exactly as written. All implementations match the plan spec. The Gauge try/except in the worker (plan's own suggestion) was implemented as specified.

## Issues Encountered

None. The plan's note about ARQ not supporting second-level cron was anticipated and the every-minute fallback (`minute=set(range(60))`) was implemented as specified in the plan's "Verificar versão do ARQ" note.

## User Setup Required

None — no external service configuration required. Prometheus scraping configuration (adding the `/metrics` endpoint to a Prometheus target) is an operational concern documented in the monitoring runbook, not a setup step for this plan.

## Next Phase Readiness

- Phase 17 is now complete (both plans executed: INFRA2-01..04 all implemented)
- `/metrics` ready for Prometheus scraping — add `http://backend:8000/metrics` as a target in prometheus.yml
- `/health/deep` ready for uptime monitors (Grafana OnCall, Datadog, Better Uptime) — returns structured JSON with per-component status
- Grafana dashboards can query `rate(http_requests_total[5m])`, `histogram_quantile(0.95, http_request_duration_seconds_bucket)`, and `rotas_active_tenants_total`

---
*Phase: 17-infrastructure-enterprise-v2*
*Completed: 2026-06-19*

## Known Stubs

None.

## Self-Check: PASSED

- `backend/app/main.py` — exists; contains `Instrumentator`, `/health/deep`, `arq:health:worker_heartbeat`, `app.state.engine = _engine`
- `backend/app/worker.py` — exists; contains `task_update_active_tenants_metric`, `task_worker_heartbeat`, both in `WorkerSettings.functions` and `cron_jobs`
- `backend/pyproject.toml` — `prometheus-fastapi-instrumentator>=7.0` present
- All 5 task acceptance criteria verified via Python imports and grep
- Commit `0d26655` (HEAD) — verified contains all implementation
