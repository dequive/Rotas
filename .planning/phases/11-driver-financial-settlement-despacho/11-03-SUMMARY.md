---
plan: 11-03
status: done
---
# 11-03 SUMMARY — Settlement Service Layer

- `backend/app/modules/drivers/settlement_service.py` created
- `compute_settlement(db, tenant_id, trip_id)` — trip must be 'completed', sums TripCost.amount, looks up latest non-voided advance, creates TripSettlement (idempotent via UNIQUE trip_id), marks advance.status='settled', balance = advance − costs
- `approve_settlement(db, tenant_id, user_id, settlement_id)` — must be pending (409 settlement_already_approved otherwise), sets approved_by/approved_at, fires audit
- `reject_settlement(db, tenant_id, user_id, settlement_id, reason)` — sets rejection_reason, fires audit
- `generate_settlement_pdf(db, tenant_id, settlement_id)` — fpdf2 + DejaVuSans (UTF-8 for Mozambican names), itemized costs table, balance summary, signature lines, stores via save_generated_file
