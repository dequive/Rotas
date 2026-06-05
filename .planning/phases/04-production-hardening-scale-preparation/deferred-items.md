# Deferred Items — Phase 04

## Pre-existing test failures (out of scope)

**File:** `backend/tests/test_workshop_operations_api.py`

Two tests fail on the baseline (before any 04-03 changes) due to control tower aggregation returning 0 for `tool_checkouts_overdue` and `maintenance_overdue` fields:

- `test_tool_checkout_return_and_critical_calibration_controls` — asserts `tower.json()["summary"]["tool_checkouts_overdue"] == 1` but gets 0
- `test_preventive_maintenance_evaluation_is_idempotent` — asserts `tower.json()["summary"]["maintenance_overdue"] == 1` but gets 0

**Root cause:** Control tower summary aggregation queries do not include these counters or return stale/zero values.
**Discovered during:** 04-03 plan execution (verification step)
**Not introduced by:** 04-03 changes (confirmed by git stash test)
**Resolution:** Needs investigation in control tower aggregation module — candidate for 04-07 or CT-01/CT-02 work.
