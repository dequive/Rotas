---
phase: 23-third-party-registry
plan: "03"
subsystem: database / fuel / workshop
tags: [migration, orm, serializer, third-party, nullable-fk]
dependency_graph:
  requires: [23-01]
  provides: [fuel_purchases.supplier_third_party_id, spare_parts_inventory.supplier_third_party_id, work_orders.service_provider_third_party_id]
  affects: [fuel/operations.py, workshop/service.py]
tech_stack:
  added: []
  patterns: [additive nullable FK, ON DELETE SET NULL, ORM mapped_column]
key_files:
  created:
    - backend/alembic/versions/tp03_add_third_party_fks.py
  modified:
    - backend/app/modules/fuel/models.py
    - backend/app/modules/workshop/models.py
    - backend/app/modules/fuel/operations.py
    - backend/app/modules/workshop/service.py
decisions:
  - "serialize_purchase lives in fuel/operations.py (not fuel/service.py) — updated there instead of service.py"
  - "Added supplier_name to serialize_spare_part dict since it was missing despite being on the model"
metrics:
  duration: "~10 minutes"
  completed: "2026-06-19"
  tasks_completed: 2
  files_modified: 5
---

# Phase 23 Plan 03: Database — Additive Nullable FKs Summary

**One-liner:** Three nullable UUID FKs linking fuel_purchases, spare_parts_inventory, and work_orders to third_parties.id via ON DELETE SET NULL, with matching ORM columns and serializer fields.

## What Was Built

### Task 1 — Alembic Migration

`backend/alembic/versions/tp03_add_third_party_fks.py` (revision `tp03`, down_revision `tp01b`) adds:

- `fuel_purchases.supplier_third_party_id UUID nullable FK → third_parties.id` + index `ix_fuel_purchases_supplier_tp`
- `spare_parts_inventory.supplier_third_party_id UUID nullable FK → third_parties.id` + index `ix_spare_parts_supplier_tp`
- `work_orders.service_provider_third_party_id UUID nullable FK → third_parties.id` + index `ix_work_orders_service_provider_tp`

All three are ON DELETE SET NULL. Downgrade drops indexes then columns in reverse order.

### Task 2 — ORM Models and Serializers

**`FuelPurchase`** — `supplier_third_party_id` added after `supplier_name`. Free-text `supplier_name` retained for historical rows.

**`SparePartInventory`** — `supplier_third_party_id` added after `supplier_name`.

**`WorkOrder`** — `service_provider_third_party_id` added after `close_notes`.

**`serialize_purchase`** (in `fuel/operations.py`) — new field included in returned dict.

**`serialize_spare_part`** (in `workshop/service.py`) — new field included; also added `supplier_name` which was on the model but missing from the serializer dict (Rule 2 auto-fix).

**`serialize_work_order`** (in `workshop/service.py`) — `service_provider_third_party_id` added between `close_notes` and `created_at`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Field] serialize_spare_part was not exposing supplier_name**
- **Found during:** Task 2 — serializer update
- **Issue:** `SparePartInventory.supplier_name` existed on the model but was absent from `serialize_spare_part`'s returned dict. Adding only the FK without the name field would leave the name invisible to API consumers.
- **Fix:** Added `"supplier_name": item.supplier_name` alongside `"supplier_third_party_id"` in the same edit.
- **Files modified:** `backend/app/modules/workshop/service.py`
- **Commit:** f5e2ada

**2. [Rule 1 - Wrong Location] serialize_purchase is in fuel/operations.py, not fuel/service.py**
- **Found during:** Task 2 — searching for serialize_fuel_purchase
- **Issue:** Plan referenced `fuel/service.py` but the actual purchase serializer (`serialize_purchase`) lives in `fuel/operations.py`.
- **Fix:** Updated `fuel/operations.py` instead of `fuel/service.py`.
- **Files modified:** `backend/app/modules/fuel/operations.py`
- **Commit:** f5e2ada

## Commits

| Hash | Message |
|------|---------|
| f5e2ada | feat(23-03): add nullable third_party FKs to fuel/workshop tables |

## Known Stubs

None. All new FK columns are nullable and default to NULL — no stubs or placeholder values.

## Self-Check: PASSED

- `backend/alembic/versions/tp03_add_third_party_fks.py` — exists (created)
- `backend/app/modules/fuel/models.py` — `supplier_third_party_id` present in `FuelPurchase`
- `backend/app/modules/workshop/models.py` — `supplier_third_party_id` in `SparePartInventory`, `service_provider_third_party_id` in `WorkOrder`
- `backend/app/modules/fuel/operations.py` — `serialize_purchase` includes new field
- `backend/app/modules/workshop/service.py` — `serialize_work_order` and `serialize_spare_part` include new fields
- Commit f5e2ada verified in git log
