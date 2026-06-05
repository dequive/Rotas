---
phase: 04-production-hardening-scale-preparation
plan: "05"
subsystem: backend/models
tags: [type-safety, decimal, sqlalchemy, annotation-cleanup, no-migration]
dependency_graph:
  requires: [04-01]
  provides: [correct-Decimal-annotations-on-all-Numeric-columns]
  affects: [billing, trips, fuel, workshop, contracts, trip_orders]
tech_stack:
  added: []
  patterns: [Mapped[Decimal] on Numeric columns, from decimal import Decimal import]
key_files:
  modified:
    - backend/app/modules/billing/models.py
    - backend/app/modules/trips/models.py
    - backend/app/modules/fuel/models.py
    - backend/app/modules/workshop/models.py
    - backend/app/modules/contracts/models.py
    - backend/app/modules/trip_orders/models.py
decisions:
  - "No Alembic migration needed — annotation-only change confirmed by alembic check (D-15)"
  - "Mapped[float] on Numeric(x,y) was incorrect — SQLAlchemy returns Decimal at runtime; float annotation was misleading"
metrics:
  duration: "14m"
  completed: "2026-06-05T19:54:42Z"
  tasks: 2
  files: 6
---

# Phase 4 Plan 05: Decimal Type Annotation Cleanup Summary

**One-liner:** Replaced all `Mapped[float]` with `Mapped[Decimal]` on 38 `Numeric(x,y)` columns across 6 model files — annotation-only, zero schema drift, full test suite green.

## What Was Done

Updated Python type annotations in all six financial domain model files so that `Mapped[float]` annotations on `Numeric(x,y)` SQLAlchemy columns are replaced with `Mapped[Decimal]`. SQLAlchemy already returns `Decimal` at runtime from `Numeric` columns — this change makes the static type annotations match the actual runtime type, preventing subtle bugs where code assumes float arithmetic on monetary values.

Added `from decimal import Decimal` import to all 6 files. No schema changes were made — `alembic check` confirmed zero new upgrade operations.

## Files Modified

| File | Columns Updated |
|------|----------------|
| `billing/models.py` | subtotal, tax_amount, total_amount, quantity, unit_price, amount |
| `trips/models.py` | cargo_weight, cargo_volume, total_fuel_cost, total_expense_cost, total_transport_cost, actual_revenue, actual_margin, TripStop.cost, TripCost.amount, TripExecutionEvent.odometer_reading/fuel_level, TripIncident.financial_impact_estimate, KnownRoute.distance_km/avg_fuel_liters |
| `fuel/models.py` | FuelLog.liters/price_per_liter/total_cost/consumption_l_per_100km, FuelTank.capacity_liters/minimum_stock_liters/current_stock_liters/average_unit_cost, FuelPurchase.ordered_liters/unit_price/total_cost, FuelReceipt.received_liters, FuelMovement.liters/balance_after_liters/unit_cost/total_cost, VehicleRefuel.liters/unit_cost/total_cost, FuelStockCount.theoretical_liters/measured_liters/variance_liters |
| `workshop/models.py` | WorkOrder.estimated_cost/actual_cost, SparePartInventory.current_quantity/minimum_quantity/average_unit_cost, SparePartMovement.quantity/balance_after_quantity/unit_cost/total_cost, MaintenancePartUsed.quantity/unit_cost/total_cost |
| `contracts/models.py` | default_unit_price |
| `trip_orders/models.py` | estimated_weight, estimated_volume, cargo_value, estimated_distance_km, estimated_fuel_cost, estimated_toll_cost, estimated_revenue |

## Verification Results

- `ruff check` on all 6 files: **All checks passed**
- Model import test: **all models import OK**
- `pytest tests/ -x -q`: **83 passed, 12 skipped**
- `alembic check`: **No new upgrade operations detected**

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- All 6 model files exist and contain `from decimal import Decimal`
- Commit `4578385` (Task 1 — annotation updates) exists
- Commit `59f190b` (Task 2 — test verification) exists
- `grep "Mapped\[float" backend/app/modules/*/models.py` returns zero matches on all 6 target files
