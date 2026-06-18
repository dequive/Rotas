---
plan: 08-02
phase: 08-infrastructure-hardening
status: complete
completed_at: 2026-06-07
self_check: PASSED
---

## What Was Built

Sentry SDK integration into FastAPI backend and ARQ worker with PII scrubbing (INFRA-01).

## Key Files Modified

- `backend/app/config.py` — added `sentry_dsn_backend`, `sentry_dsn_manager`, `sentry_dsn_driver` fields (DSN guard: empty string = Sentry disabled)
- `backend/app/main.py` — `_PII_FIELDS` frozenset (8 fields), `_scrub_pii()` before_send hook, `sentry_sdk.init()` in lifespan conditional on DSN
- `backend/app/worker.py` — Sentry init in `startup()` with same PII scrubber
- `backend/pyproject.toml` — added `sentry-sdk[fastapi]>=2.61.1`, `redis[asyncio]>=4.2,<6`
- `backend/tests/test_sentry_integration.py` — 5 tests GREEN (PII scrubbing, nested dicts, SQL breadcrumbs, DSN guard, request data)

## Test Results

```
tests/test_sentry_integration.py — 5 passed
```

## Commits

- `be51011` — feat(08-02): integrate sentry_sdk into FastAPI backend and ARQ worker with PII scrubber
