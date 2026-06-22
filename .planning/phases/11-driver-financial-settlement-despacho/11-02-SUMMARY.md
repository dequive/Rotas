---
plan: 11-02
status: done
---
# 11-02 SUMMARY — Advance Service Layer

- `backend/app/modules/drivers/advance_service.py` created
- `issue_advance(db, tenant_id, user_id, trip_id, driver_id, amount_mzn, notes, request_reference)` — validates trip exists + status in planned/in_progress, enforces one-advance-per-trip (409), creates DriverAdvance, fires audit log `driver_advance.issued`
- `void_advance(db, tenant_id, user_id, advance_id)` — rejects settled (409 advance_already_settled) and already-voided (409 advance_already_voided), fires `driver_advance.voided`
- `list_advances(db, tenant_id, trip_id, driver_id, status_filter, limit, offset)` — filterable query
- `serialize_advance()` — decouples ORM shape from response, Decimal → str for JSON safety
