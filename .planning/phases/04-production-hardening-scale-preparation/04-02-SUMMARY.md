---
phase: 04-production-hardening-scale-preparation
plan: "02"
subsystem: backend/workshop
tags: [maintenance, scheduler, work-orders, alembic, tdd]
dependency_graph:
  requires: [04-01]
  provides: [MAINT-01-D02, MAINT-01-D03, MAINT-01-D04, MAINT-01-D06]
  affects: [backend/app/modules/workshop/service.py, backend/alembic/versions/]
tech_stack:
  added: []
  patterns:
    - "_trigger_maintenance_work_order() de-dupe pattern (plan_id + open status check)"
    - "next-cycle schedule creation with UniqueConstraint as DB-level guard"
    - "get_imminent_maintenance_alerts() or_() query with odometer + calendar thresholds"
key_files:
  created:
    - backend/alembic/versions/7b6acddf4ab0_add_plan_id_to_work_orders.py
  modified:
    - backend/app/modules/workshop/service.py
    - backend/tests/test_maintenance_scheduler.py
decisions:
  - "vehicle.plate included in WorkOrder audit log new_values to make the vehicle param non-unused and improve audit trail readability"
  - "Tenant import in evaluate_maintenance_schedule_all_tenants() kept as local import to avoid circular dependency risk"
metrics:
  duration: "~20 min"
  completed: "2026-06-05"
  tasks_completed: 2
  files_changed: 3
---

# Phase 4 Plan 02: MAINT-01 Scheduler — WorkOrder Creation + Next-Cycle Logic Summary

**One-liner:** Preventive maintenance scheduler extended to auto-create draft WorkOrders and next-cycle pending schedule records when km/date triggers fire, with open-order de-dupe guard.

---

## What Was Built

### Task 1: Alembic migration — plan_id FK on work_orders (commit `08b84b4`)

- `WorkOrder.plan_id`: `Mapped[uuid.UUID | None]` FK to `maintenance_plans.id`, indexed, nullable
- Migration `7b6acddf4ab0_add_plan_id_to_work_orders.py` — adds column, index, FK constraint
- Extends `chk_maintenance_schedule_status` check constraint to include `'pending'` status (required for D-03 next-cycle records)
- Roundtrip `downgrade -1 && upgrade head` verified clean

### Task 2: Service extension + tests (commit `e75bbe7`)

**New functions in `backend/app/modules/workshop/service.py`:**

- `_trigger_maintenance_work_order(db, tenant_id, plan, vehicle, actor_id)` — D-02/D-04: creates a `WorkOrder(status='draft')` if no open order exists for the same `plan_id + vehicle_id`; logs audit entry with plan_id, vehicle_id, vehicle_plate, wo_number
- `evaluate_maintenance_schedule()` extended — after creating `MaintenanceSchedule(status='overdue')`, now also calls `_trigger_maintenance_work_order()` and creates `MaintenanceSchedule(status='pending')` for next cycle (D-03), computing `due_km = current_km + interval_km` and `due_at = now + interval_days`
- `evaluate_maintenance_schedule_all_tenants(db)` — iterates all active tenants for ARQ daily cron (04-03)
- `get_imminent_maintenance_alerts(db, tenant_id, days_ahead=30, km_ahead=500)` — D-06: returns plans where `next_due_at <= now+30d OR current_km+500 >= next_due_km`, with `trigger_type` field

**Tests turned GREEN in `backend/tests/test_maintenance_scheduler.py`:**

| Test | Validates |
|------|-----------|
| `test_scheduler_creates_work_order_on_km_trigger` | D-02: km trigger creates WorkOrder(draft) |
| `test_scheduler_creates_work_order_on_date_trigger` | D-02: date trigger creates WorkOrder(draft) |
| `test_scheduler_skips_duplicate_work_order` | D-04: second call with open WO creates 0 new orders |
| `test_next_cycle_schedule_created_after_trigger` | D-03: pending schedule with due_km=15001 after trigger |
| `test_imminent_maintenance_alerts` | D-06: 30-day window returns 1 alert with trigger_type='calendar' |
| `test_odometer_event_enqueues_arq_task` | SKIPPED — deferred to 04-03 |

---

## Verification

```
pytest tests/test_maintenance_scheduler.py tests/test_workshop_operations_api.py -q
9 passed, 1 skipped in 4.78s
```

`ruff check app/modules/workshop/service.py tests/test_maintenance_scheduler.py` — all checks passed.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing audit context] Added vehicle.plate to WorkOrder audit log**
- **Found during:** Task 2 implementation — `vehicle` param was passed but unused (IDE hint)
- **Fix:** Included `vehicle_plate` in `record_audit_log new_values` — makes the param functional and improves audit readability
- **Files modified:** `backend/app/modules/workshop/service.py`
- **Commit:** e75bbe7

None other — plan executed as written.

---

## Known Stubs

None — all scheduler logic is fully wired. `test_odometer_event_enqueues_arq_task` is an intentionally deferred stub (04-03).

---

## Self-Check: PASSED
