---
plan: 11-01
status: done
---
# 11-01 SUMMARY — Database Schema

- New table `driver_advances`: UUID PK, tenant_id (RLS), trip_id FK, driver_id FK, amount_mzn NUMERIC(10,2), status (issued/settled/voided), issued_by soft UUID ref, request_reference unique per tenant
- New table `trip_settlements`: UUID PK, tenant_id (RLS), trip_id UNIQUE FK, advance_id nullable FK, total_costs_mzn + advance_amount_mzn + balance_mzn NUMERIC(10,2), status (pending/approved/rejected), approved_by soft UUID ref, rejection_reason, pdf_file_id
- Migrations: adv01 (create tables + RLS + GRANT), adv02 (fix RLS), adv03 (rename policies to tenant_isolation), adv04 (drop user FK constraints — soft refs matching audit_logs pattern)
- SQLAlchemy models added to `backend/app/modules/drivers/models.py`
- RLS policies use `current_setting('app.tenant_id', true)` — tenant isolation enforced at DB level
