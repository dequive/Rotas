# Phase 16 — Hours of Service + Availability Router: Context

## What Exists (Read Before Writing Code)

### availability/service.py — Already complete, do NOT rewrite
`backend/app/modules/availability/service.py` is a fully implemented service with:
- `require_vehicle_available(db, tenant_id, vehicle_id)` — raises 409 if vehicle has active work order, compliance violations, or active trip. Already called by `create_trip()`.
- `require_driver_available(db, tenant_id, driver_id)` — raises 409 if driver has compliance violations or active trip. Does NOT check HOS hours — this is the gap.
- `require_vehicle_and_driver_available(db, tenant_id, vehicle_id, driver_id)` — combined call, used in `trips/service.py create_trip()`.
- `vehicle_availability_summary(db, tenant_id, vehicle_id)` — returns full availability dict for a single vehicle.
- `driver_availability_summary(db, tenant_id, driver_id)` — returns full availability dict for a single driver.
- `vehicle_compliance_violations()`, `driver_compliance_violations()` — sync helpers.

The service has NO models — the module has no `models.py`. Therefore `availability` does NOT belong in `database.py MODEL_MODULES` (that list is for modules with ORM models). This was a documentation gap, not a code gap.

### What is Genuinely Missing
1. No `router.py` in `backend/app/modules/availability/` — so no REST endpoints exist
2. No `hos_service.py` — HOS (Hours of Service) calculation is not implemented anywhere
3. `require_driver_available()` has no HOS check — a driver with 9+ hours driven today can still be assigned
4. No tests for HOS logic or availability endpoints

### What Already Works (do NOT duplicate)
- Vehicle maintenance block: `require_vehicle_available()` already raises `vehicle_workshop_blocked` 409 with `work_order_id` when vehicle has an active WorkOrder in `("approved", "in_progress", "quality_check")`.
- Vehicle trip conflict block: already raises `vehicle_assignment_conflict` 409.
- Driver compliance block: already raises `driver_compliance_blocked` 409 for expired/missing documents.
- `create_trip()` in `trips/service.py` already calls `require_vehicle_and_driver_available()` — we extend `require_driver_available` to add HOS check.

## Architecture Decisions

### HOS Thresholds
- Warning: >= 8h driven today (driver should rest soon)
- Violation: >= 9h driven today OR >= 48h driven this week (cannot be assigned)
- Week = Monday 00:00 UTC to Sunday 23:59 UTC

### HOS Calculation Approach
- Source data: `trips` table, `actual_departure` and `actual_arrival` columns
- Scope: trips WHERE `driver_id = X AND tenant_id = T AND status IN ('in_progress', 'completed')`
- Today: trips where `actual_departure::date = target_date` (UTC)
- This week: trips where `actual_departure >= week_start` (Monday UTC)
- Duration: `actual_arrival - actual_departure` for completed trips; `NOW() - actual_departure` for in_progress trips
- Trips with NULL `actual_departure` are excluded (planned/dispatched trips have no driving time)

### Override Policy
- `hos_override_reason` field on `TripCreate` schema (nullable string)
- If driver has HOS violation AND `hos_override_reason` is None: raise `hos_violation_active` 409 with `{override_required: true, hours_today: float, hours_this_week: float}`
- If `hos_override_reason` is provided: allow assignment, record in audit log
- Override requires admin/owner role — enforced in router via `require_permission(FLEET_WRITE)`

### Redis Cache for Availability Endpoints
- Same pattern as control_tower: `av:drivers:{tenant_id}` and `av:vehicles:{tenant_id}`, TTL 30s
- Cache-aside with NX+EX stampede lock
- Falls back to DB if Redis unavailable

### No New Models — No Migration Needed
HOS data comes from existing `trips` table. No new tables required for this phase.

## Key Files

| File | Role |
|------|------|
| `backend/app/modules/availability/service.py` | Existing — extend `require_driver_available()` |
| `backend/app/modules/drivers/hos_service.py` | New — HOS calculation |
| `backend/app/modules/availability/router.py` | New — availability endpoints |
| `backend/app/main.py` | Add availability router import + `include_router` |
| `backend/app/modules/trips/schemas.py` | Add `hos_override_reason: str | None` to `TripCreate` |
| `backend/app/modules/trips/service.py` | Call HOS check inside `create_trip()` |
| `backend/tests/test_hos_service.py` | New test module |
| `backend/tests/test_availability_endpoints.py` | New test module |

## Redis Cache Pattern (from control_tower/service.py)

```python
key = f"av:drivers:{tenant_id}"
lock_key = f"av:drivers:{tenant_id}:lock"

cached = await redis.get(key)
if cached:
    return json.loads(cached)

locked = await redis.set(lock_key, "1", nx=True, ex=5)
if not locked:
    # Another request is computing — fall through to DB
    pass
else:
    result = await _compute_drivers(db, tenant_id, ...)
    await redis.set(key, json.dumps(result, default=str), ex=30)
    await redis.delete(lock_key)
    return result

return await _compute_drivers(db, tenant_id, ...)
```

## RBAC Constants Used
- `FLEET_READ` — for GET endpoints on availability
- `FLEET_WRITE` — for HOS override (already on trip creation)

From `backend/app/core/rbac.py` — import as: `from app.core.rbac import FLEET_READ, require_permission`

## Schemas Pattern
`TripCreate` is in `backend/app/modules/trips/schemas.py`. Add field:
```python
hos_override_reason: str | None = Field(None, max_length=500)
```
