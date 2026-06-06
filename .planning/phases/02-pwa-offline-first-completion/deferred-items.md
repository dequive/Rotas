# Phase 2 — Deferred Items

Items discovered during Phase 2 execution that are out-of-scope (pre-existing, unrelated files).

---

## Pre-existing Test Failure

**File:** `backend/tests/test_workshop_operations_api.py`
**Test:** `test_tool_checkout_return_and_critical_calibration_controls`
**Failure:** `assert tower.json()["summary"]["tool_checkouts_overdue"] == 1` fails — returns 0 instead of 1
**Discovered during:** Plan 02-08 pre-flight
**Root cause:** Control tower `tool_checkouts_overdue` aggregation in the workshop module does not count the expired checkout that was rejected (409). The test creates an expired tool, gets a 409 on checkout attempt, then expects the control tower to count it as overdue — but the checkout was never created (it was blocked), so there's nothing to count as overdue.
**Phase introduced:** Pre-dates Phase 2 (workshop module from earlier phase)
**Action required:** Fix workshop control tower aggregation logic to match test expectations. Assign to Phase 3 or Phase 4 workshop module work.
