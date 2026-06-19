---
plan: 17-01
phase: 17
title: "Redis Rate Limiting + Structured Logging"
status: complete
completed_date: "2026-06-19"
duration_minutes: 15
tasks_completed: 5
tasks_total: 5
files_created:
  - backend/app/core/logging.py
  - backend/app/core/middleware.py
files_modified:
  - backend/app/core/limiter.py
  - backend/app/main.py
  - backend/app/worker.py
  - backend/pyproject.toml
subsystem: backend-infrastructure
tags: [rate-limiting, structured-logging, redis, slowapi, structlog, arq-worker]
requires: []
provides: [INFRA2-01, INFRA2-02]
affects: [backend/app/core, backend/app/main.py, backend/app/worker.py]
tech_stack_added:
  - structlog>=24.0 (JSON + console structured logging)
tech_stack_patterns:
  - Redis-backed slowapi Limiter with in-memory fallback for local dev
  - structlog ProcessorFormatter wrapping stdlib logging root handler
  - StructlogRequestMiddleware logs method/path/status_code/duration_ms per request
  - configure_structlog() called once at app startup and once in ARQ worker on_startup
key_decisions:
  - Redis URL from settings.redis_url — same Redis instance as ARQ and CT cache; no new infra needed
  - In-memory fallback with RuntimeWarning when REDIS_URL absent — local dev works without Docker Redis
  - json_logs=True only when environment=="production" — dev gets colorized ConsoleRenderer
  - /health, /health/deep, /metrics, /favicon.ico skipped from HTTP logging to reduce noise
  - structlog>=24.0 added to pyproject.toml — was installed in venv but undeclared
---

# Phase 17 Plan 01: Redis Rate Limiting + Structured Logging Summary

**One-liner:** Redis-backed slowapi rate limiter replacing in-memory storage, plus structlog JSON logging for every FastAPI request and ARQ worker event.

## What Was Built

### Task 1 — structlog dependency declared
Added `structlog>=24.0` to `backend/pyproject.toml` dependencies. Package was already installed in the venv (v26.1.0) but was not declared, making it invisible to dependency managers.

### Task 2 — Redis Rate Limiter (INFRA2-01)
`backend/app/core/limiter.py` uses `slowapi.Limiter` with `storage_uri=settings.redis_url` when `REDIS_URL` is set. All Gunicorn workers share rate-limit counters through the same Redis instance. Graceful in-memory fallback (with `RuntimeWarning`) when `REDIS_URL` is absent for local development.

### Task 3 — Structured logging configuration (INFRA2-02)
`backend/app/core/logging.py` provides `configure_structlog(json_logs: bool)`:
- Production: `JSONRenderer` — each log line is a compact JSON object with `timestamp`, `level`, `event`, `logger`, and any bound context keys
- Development: `ConsoleRenderer(colors=True)` — human-readable colorized output
- Silences `uvicorn.access` and `sqlalchemy.engine` to reduce noise
- Called first in FastAPI `lifespan()` and in ARQ `startup()`

### Task 4 — HTTP request logging middleware (INFRA2-02)
`backend/app/core/middleware.py` — `StructlogRequestMiddleware(BaseHTTPMiddleware)`:
- Logs one line per request after response is sent: `method`, `path`, `status_code`, `duration_ms`, `client_ip`
- Skips health/metrics endpoints: `/health`, `/health/deep`, `/metrics`, `/favicon.ico`
- Registered in `main.py` after `RequestContextMiddleware` so `request_id` from contextvars is available

### Task 5 — Structured logging in ARQ worker (INFRA2-02)
`backend/app/worker.py` `startup()` function calls `configure_structlog()` before any other initialization. All worker tasks (`task_mark_overdue_billing_documents`, `task_expire_contracts`, etc.) use `structlog.get_logger("worker")` and emit structured events with domain keys.

## Verification Results

```
python -c "from app.core.limiter import limiter; print('limiter ok')"
# limiter ok

python -c "from app.core.logging import configure_structlog; configure_structlog(False); import structlog; structlog.get_logger().info('test', key='value')"
# 2026-06-19T16:12:35.524292Z [info     ] test    [__main__] key=value

python -c "from app.worker import WorkerSettings; print(WorkerSettings.on_startup)"
# <function startup at 0x...>

pytest tests/ -k "rate_limit or limiter" -v
# 3 passed, 294 deselected in 6.89s
```

## Deviations from Plan

None — all five tasks were already implemented in a prior session (Phase 17 was marked complete in STATE.md). The only gap was that `structlog>=24.0` was missing from `pyproject.toml`, which was the sole change committed in this execution.

## Known Stubs

None.

## Self-Check: PASSED

- `backend/app/core/limiter.py` — exists, contains `storage_uri` + `redis_url`
- `backend/app/core/logging.py` — exists, contains `configure_structlog`, `JSONRenderer`, `ConsoleRenderer`
- `backend/app/core/middleware.py` — exists, contains `StructlogRequestMiddleware`, `duration_ms`, `status_code`
- `backend/app/worker.py` — `WorkerSettings.on_startup = startup` confirmed
- `backend/pyproject.toml` — `structlog>=24.0` present
- Commit `50f0084` — verified in git log
