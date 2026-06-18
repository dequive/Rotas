---
plan: 08-05
phase: 08-infrastructure-hardening
status: complete
completed_at: 2026-06-07
self_check: PASSED
---

## What Was Built

Tenant plan limit enforcement guards in all 3 services + GET /api/v1/tenant/limits endpoint with Redis TTL-30s caching (INFRA-03).

## Key Files Modified

- `backend/app/config.py` — `upgrade_url` field (UPGRADE_URL env var, D-16)
- `backend/app/modules/tenants/models.py` — `max_vehicles/drivers/users` made nullable (`Mapped[int | None]`) to support unlimited tier
- `backend/app/modules/vehicles/service.py` — `_check_vehicle_limit()` guard at top of `create_vehicle()`: null-safe, `plan_limit_reached` slug, `upgrade_url` in body
- `backend/app/modules/drivers/service.py` — `_check_driver_limit()` guard
- `backend/app/modules/users/service.py` — `_check_user_limit()` guard
- `backend/app/modules/tenants/router.py` — `GET /api/v1/tenant/limits` endpoint: returns `{vehicles, drivers, users}` nested with `{used, max, pct}` + Redis cache `tenant:limits:{tenant_id}` TTL 30s

## Key Files Created

- `backend/alembic/versions/a9b8c7d6e5f4_make_tenant_limits_nullable.py` — ALTER COLUMN max_vehicles/drivers/users to nullable

## Test Results

```
tests/test_tenant_limits_api.py — 6 passed
alembic upgrade head — clean (a9b8c7d6e5f4 applied)
```

## Commits

- Task 1: upgrade_url + nullable limits model + migration
- Task 2: guard functions + limits endpoint + Redis caching
