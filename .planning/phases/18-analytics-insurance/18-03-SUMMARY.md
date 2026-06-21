---
phase: 18-analytics-insurance
plan: "03"
subsystem: backend
tags: [insurance, vehicles, rls, cron, alerts]
key_files:
  created:
    - backend/alembic/versions/ins01_add_vehicle_insurance.py
    - backend/app/modules/vehicles/insurance_service.py
    - backend/tests/test_vehicle_insurance_api.py
  modified:
    - backend/app/modules/vehicles/models.py
    - backend/app/modules/vehicles/schemas.py
    - backend/app/modules/vehicles/router.py
    - backend/app/worker.py
metrics:
  completed_date: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 8
  tests_green: 8
---

# Phase 18 Plan 03: Vehicle Insurance CRUD + Renewal Cron — Summary

## One-liner

VehicleInsurance and InsuranceClaim tables with full CRUD API, RLS, and a daily ARQ cron that generates renewal alerts at 60/30/7-day thresholds.

## What Was Built

### Migration (ins01_add_vehicle_insurance.py)

Creates `vehicle_insurances` and `insurance_claims` tables. Both have RLS (`tenant_isolation` policy) and `GRANT SELECT,INSERT,UPDATE,DELETE ON ... TO rotas_app` per v2.0 rule.

### ORM Models (vehicles/models.py)

`VehicleInsurance`: id, tenant_id, vehicle_id, policy_number, insurer, coverage_type, premium_amount, valid_from, valid_until, notes, timestamps.

`InsuranceClaim`: id, tenant_id, vehicle_id, insurance_id, incident_id (nullable FK), claim_number, claim_date, estimated_damage, status (open|under_review|paid|rejected), resolved_at, notes, timestamps.

### Pydantic Schemas (vehicles/schemas.py)

`VehicleInsuranceCreate`, `VehicleInsuranceRead`, `InsuranceClaimCreate`, `InsuranceClaimRead`, `InsuranceClaimStatusUpdate`.

### Service (insurance_service.py)

8 functions: `create_insurance`, `list_insurances`, `get_insurance`, `update_insurance`, `delete_insurance`, `create_claim`, `list_claims`, `update_claim_status`. All audit-logged. FK violation on `incident_id` is caught and returned as 422.

### Router (vehicles/router.py)

8 new endpoints under `/vehicles/{vehicle_id}/insurance/...`:
- GET/POST insurance, GET/PATCH insurance/{id}, DELETE insurance/{id}
- GET/POST insurance/{id}/claims, PATCH insurance/{id}/claims/{id}/status

### ARQ Cron (worker.py)

`task_check_insurance_renewals` — daily at 05:00 UTC. Scans all `vehicle_insurances` rows expiring in exactly 60, 30, or 7 days. Creates `insurance_renewal` alerts (priority: medium/high/critical). Deduplicates via `request_reference = "ins_renewal:{id}:{date}:{days}d"`.

## Verification

- 8 integration tests: all GREEN
- RLS: `tenant_isolation` policy applied to both tables in pg_policies
- ruff: All checks passed
- Full suite: 412 passed, 2 skipped — zero regressions
