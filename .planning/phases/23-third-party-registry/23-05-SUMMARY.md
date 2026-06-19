---
phase: 23-third-party-registry
plan: 05
subsystem: third_party
tags: [driver-vehicle-assignments, temporal-table, rls, crud]
requires: [23-01]
provides: [driver_vehicle_assignments table, assign/unassign/list endpoints]
affects: [third_party module, alembic migrations]
tech-stack:
  added: []
  patterns: [temporal soft-delete, cross-tenant isolation guard, idempotent unassign]
key-files:
  created:
    - backend/alembic/versions/tp05_add_driver_vehicle_assignments.py
  modified:
    - backend/app/modules/third_party/models.py
    - backend/app/modules/third_party/schemas.py
    - backend/app/modules/third_party/service.py
    - backend/app/modules/third_party/router.py
decisions:
  - "Used ondelete=RESTRICT (not CASCADE) on driver_id/vehicle_id FKs to prevent accidental orphaning of assignment history when a driver or vehicle is deleted"
  - "Soft-delete via unassigned_at timestamp is idempotent: repeat DELETE returns 200 with existing state rather than 409"
  - "Deferred imports (inside function body) for Driver and Vehicle models to avoid circular imports at module load time"
  - "Assignment endpoints placed under /third-party/ prefix (not /driver-vehicle-assignments/) to keep all third-party registry routes under one router"
metrics:
  duration: ~20 minutes
  completed: 2026-06-19
  tasks: 2
  files: 5
---

# Phase 23 Plan 05: Driver-Vehicle Assignments Summary

Temporal `driver_vehicle_assignments` table with RLS, ORM model, Pydantic schemas, service CRUD, and three HTTP endpoints for cross-tenant-safe driver-vehicle pairing history.

## What Was Built

### Migration (tp05)

`backend/alembic/versions/tp05_add_driver_vehicle_assignments.py` — Alembic revision with `down_revision = "tp01b"`:

- Creates `driver_vehicle_assignments` with columns: id, tenant_id, driver_id, vehicle_id, assignment_type, assigned_at, unassigned_at, assigned_by, notes, created_at
- FKs: `drivers.id ON DELETE RESTRICT`, `vehicles.id ON DELETE RESTRICT`, `users.id ON DELETE SET NULL`
- Three indexes: `ix_dva_tenant`, `ix_dva_driver (tenant_id, driver_id)`, `ix_dva_vehicle (tenant_id, vehicle_id)`
- v2.0 mandatory RLS block: GRANT + ENABLE + FORCE + `tenant_isolation` policy

### ORM Model

`DriverVehicleAssignment` appended to `backend/app/modules/third_party/models.py`. Mirrors migration exactly — `PG_UUID`, `ForeignKey`, `DateTime(timezone=True)`, all nullable columns marked accordingly.

### Schemas

`AssignmentCreate` and `AssignmentOut` appended to `backend/app/modules/third_party/schemas.py`. `assignment_type` validated with pattern `^(primary|temporary|maintenance_only)$`.

### Service Functions

Three functions appended to `backend/app/modules/third_party/service.py`:

- `assign_driver_to_vehicle` — verifies driver.tenant_id == tenant_id and vehicle.tenant_id == tenant_id before creating; records audit log `driver_vehicle_assignment.created`
- `unassign_driver_from_vehicle` — soft-delete sets `unassigned_at = datetime.now(UTC)`; idempotent if already unassigned; records audit log `driver_vehicle_assignment.unassigned`
- `list_assignments` — filterable by driver_id, vehicle_id, current_only (unassigned_at IS NULL), with limit/offset pagination

### Router Endpoints

Three endpoints appended to `backend/app/modules/third_party/router.py` under the `/third-party` prefix:

| Method | Path | Auth | Status |
|--------|------|------|--------|
| POST | `/third-party/driver-vehicle-assignments` | WRITE_ROLES | 201 |
| GET | `/third-party/driver-vehicle-assignments` | DASHBOARD_ROLES | 200 |
| DELETE | `/third-party/driver-vehicle-assignments/{assignment_id}` | WRITE_ROLES | 200 |

## Acceptance Criteria Status

- Migration exists with RLS + GRANT: DONE
- `DriverVehicleAssignment` ORM model in models.py: DONE
- POST endpoint exists: DONE
- Cross-tenant isolation enforced in service (driver A cannot be paired with vehicle from tenant B): DONE — both `driver.tenant_id` and `vehicle.tenant_id` are verified against `tenant_id` before insert
- RLS policy name `tenant_isolation`: DONE

## Deviations from Plan

None — plan executed exactly as written. The service.py and router.py already existed (created by Plan 02 which ran first); functions were appended using Edit rather than Write, preserving all existing content.

## Known Stubs

None. All endpoints are fully wired to the service layer and ORM model.

## Self-Check: PASSED

- `backend/alembic/versions/tp05_add_driver_vehicle_assignments.py` — exists (created new)
- `DriverVehicleAssignment` in `models.py` — confirmed at line 183
- `assign_driver_to_vehicle` in `service.py` — confirmed at line 425
- `POST /driver-vehicle-assignments` in `router.py` — confirmed at line 144
- Commit `a009685` — confirmed in git log
