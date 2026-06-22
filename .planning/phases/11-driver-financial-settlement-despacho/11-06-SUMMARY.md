---
plan: 11-06
status: done
---
# 11-06 SUMMARY — Tests

- `backend/tests/test_driver_advances.py` — 6 tests: ADV-01 issue on planned trip, ADV-02 duplicate raises 409, ADV-03 completed trip raises 409, ADV-04 void advance, ADV-05 cannot void settled, ADV-06 list filters by trip_id and status
- `backend/tests/test_trip_settlements.py` — 6 tests: SET-01 correct balance (advance−costs), SET-02 compute idempotent, SET-03 non-completed trip raises 409, SET-04 approve settlement, SET-05 reject with reason, SET-06 double-approve raises 409
- 12/12 tests GREEN
- FK fix: issued_by and approved_by are soft UUID refs (no FK constraint in DB) — matches audit_logs.user_id pattern; adv04 migration drops the FK constraints
