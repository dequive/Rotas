# Phase 23 — Third Party Registry: Context & Architecture Decisions

## Why This Phase Exists

ROTAS currently models two types of counterparties:
- **Drivers** (`drivers` table) — first-class operational entities with 8+ FK dependents
- **Clients** (`clients` table) — billing counterparties with NUIT constraint (NOT NULL, unique per tenant)

Neither covers **fuel suppliers**, **spare-parts suppliers**, or **external service providers** (tire shops, mechanics, bodywork). Today these are stored as free-text `supplier_name` fields in `fuel_purchases` and `spare_parts_inventory`. This means no deduplication, no document tracking, no audit trail, and no eligibility checking.

Phase 23 builds the **Third Party Registry** — an additive module covering entities not yet modeled. It does NOT replace or wrap `drivers` or `clients`.

---

## Scope Decision (Critical)

### What Phase 23 BUILDS (new entities):
- `third_parties` — identity registry for suppliers and service providers
- `third_party_roles` — operational roles per third party (`fuel_supplier`, `spare_parts_supplier`, `service_provider`, `transport_subcontractor`)
- `supplier_profiles` — extended data for supplier roles
- `service_provider_profiles` — extended data for service provider roles
- `driver_vehicle_assignments` — temporal table linking existing `drivers.id` to `vehicles.id`
- `operational_documents` — structured document storage for any subject type (driver, vehicle, third_party)
- Province/district reference table (Mozambique provinces — static, tenant-agnostic)

### What Phase 23 DOES NOT DO:
- Does NOT modify `drivers` table (already has `license_valid_until`, `passport_valid_until`, `bi_valid_until`, `status`)
- Does NOT modify `clients` table (different entity, billing-focused, NUIT NOT NULL)
- Does NOT modify `trips.driver_id` or `trips.vehicle_id` (direct FKs, live constraints)
- Does NOT build `sync_changes` or `sync_conflicts` tables (deferred to platform sync phase)
- Does NOT bridge `clients → third_parties` (future Phase G — clients have NUIT NOT NULL constraint, different cardinality)

---

## Key Architecture Decisions

### A. Third Party as Separate Table (Not Wrapper)

`Driver` has 8+ FK dependents (trips, fuel_logs, vehicle_refuels, sync_events, idempotency_keys, driver_devices, driver_sessions, trip_incidents). Wrapping it into a `third_parties` parent would require destructive migration across all FK chains. Decision: `third_parties` is a **sibling registry**, not a parent.

### B. PartyRef Pattern (Polymorphic Reference)

When a feature needs to reference "any subject type" (e.g., `operational_documents`), use:
```python
subject_type: str  # 'driver' | 'vehicle' | 'third_party' | 'client' | 'contract'
subject_id: UUID   # FK to the respective table — NOT a DB-level FK (polymorphic)
```
No `GenericForeignKey` or polymorphic ORM relationship — just a typed UUID pair. Validation is enforced at service layer.

### C. Supplier Name Fallback (Additive FK)

`FuelPurchase.supplier_name: String(160)` and `SparePartInventory.supplier_name: str | None` are retained as free-text snapshots. Phase 23 adds **nullable FKs**:
- `fuel_purchases.supplier_third_party_id → third_parties.id` (nullable)
- `spare_parts_inventory.supplier_third_party_id → third_parties.id` (nullable)
- `work_orders.service_provider_third_party_id → third_parties.id` (nullable)

Existing rows remain valid. New rows can link to the registry OR stay as free text.

### D. OperationalEligibilityService (Pure Read, No New Columns)

The eligibility service reads existing `Driver` fields:
- `Driver.license_valid_until` — license expiry check
- `Driver.passport_valid_until` — passport expiry check  
- `Driver.bi_valid_until` — BI expiry check
- `Driver.status` — active/inactive/suspended

No new columns on `drivers`. Service is a pure Python function: `check_driver_eligibility(driver: Driver, reference_date: date) -> EligibilityResult`.

### E. DriverVehicleAssignment Table (New, Temporal)

```sql
driver_vehicle_assignments:
  id, tenant_id, driver_id → drivers.id, vehicle_id → vehicles.id
  assigned_at, unassigned_at (nullable), assignment_type
  notes, assigned_by → users.id, created_at
```

This does NOT change `trips.driver_id`. Assignment table is for habitual pairings and maintenance history, not trip execution. The existing `uniq_active_driver_trip` partial unique index on `trips` is not affected.

### F. OperationalDocuments Table (Structured, references files.id)

```sql
operational_documents:
  id, tenant_id
  subject_type: VARCHAR(30)  -- driver|vehicle|third_party|client|contract
  subject_id: UUID            -- polymorphic, no DB FK
  document_type: VARCHAR(60)  -- license|passport|bi|insurance|inspection|contract_copy...
  file_id → files.id          -- storage delegated to existing files module
  document_number: VARCHAR(80) nullable
  issued_at: DATE nullable
  expiry_date: DATE nullable
  issuing_authority: VARCHAR(160) nullable
  verification_status: VARCHAR(30) -- pending|verified|rejected
  verified_by → users.id nullable
  verified_at: TIMESTAMP nullable
  notes: TEXT nullable
  created_at, updated_at
```

Storage is delegated to the existing `files` module — no new upload infrastructure.

### G. PartyDirectoryService (UNION ALL, Not Sequential Calls)

The "party directory" endpoint returns a unified view across entity types. Implementation is a single `UNION ALL` query:

```sql
SELECT 'driver' AS subject_type, id, name, status FROM drivers WHERE tenant_id = ?
UNION ALL
SELECT 'client' AS subject_type, id, name, status FROM clients WHERE tenant_id = ?
UNION ALL
SELECT 'third_party' AS subject_type, id, name, status FROM third_parties WHERE tenant_id = ?
```

NOT three sequential API calls. Filtered by `subject_type` query param optionally.

### H. Province Reference Table (Mozambique, Tenant-Agnostic)

11 provinces + districts pre-seeded as static reference data. Table has no `tenant_id` — it's platform-level read-only data. `third_parties` and `service_provider_profiles` reference province via `province_code VARCHAR(10)`.

### I. Alert Integration (Existing alerts Module)

Document expiry alerts use the existing `Alert` model:
- `alert_type`: `document_expiring_soon`, `document_expired`
- `entity_type`: `driver`, `third_party`, `vehicle`
- `entity_id`: subject UUID
- Alert generation via scheduled check (existing pattern)

No new alert table needed.

---

## Requirements Coverage (TP-01 through TP-11)

| ID | Requirement | Implementation |
|----|-------------|----------------|
| TP-01 | Third party identity registry | `third_parties` table |
| TP-02 | Operational roles per third party | `third_party_roles` table |
| TP-03 | Supplier profiles | `supplier_profiles` table |
| TP-04 | Service provider profiles | `service_provider_profiles` table |
| TP-05 | Mozambique province reference | `mz_provinces` table (no tenant_id) |
| TP-06 | Nullable FK from fuel/workshop to third_parties | Migrations for fuel_purchases, spare_parts_inventory, work_orders |
| TP-07 | Operational eligibility service for drivers | `OperationalEligibilityService` pure Python service |
| TP-08 | Driver-vehicle assignment table | `driver_vehicle_assignments` temporal table |
| TP-09 | Operational documents (structured) | `operational_documents` table + PartyRef pattern |
| TP-10 | Document expiry alerts | Alert generation using existing `alerts` module |
| TP-11 | Party directory unified view | `PartyDirectoryService` UNION ALL query endpoint |

---

## v2.0 Migration Rules (Mandatory)

Every new `tenant_id` table in this phase MUST include in the same CREATE TABLE migration:

```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_{table} ON {table}
    USING (tenant_id::text = current_setting('app.tenant_id', true));
GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app;
```

Tables with `tenant_id` in Phase 23: `third_parties`, `third_party_roles`, `supplier_profiles`, `service_provider_profiles`, `driver_vehicle_assignments`, `operational_documents`.

Tables WITHOUT `tenant_id` (platform-level): `mz_provinces` — no RLS needed, but still needs `GRANT SELECT ON mz_provinces TO rotas_app`.

---

## Module Registration

New module: `backend/app/modules/third_party/`
- `models.py` — all new ORM models
- `service.py` — CRUD + PartyDirectoryService + OperationalEligibilityService
- `router.py` — HTTP endpoints
- `schemas.py` — Pydantic request/response schemas

Register in:
- `backend/app/main.py` — include router
- `backend/app/database.py` — add to `MODEL_MODULES`

---

## What to Avoid

- DO NOT add `province` or `district` columns to `drivers` — eligibility is document-based, not location-based
- DO NOT make `supplier_third_party_id` NOT NULL — existing rows have no FK; additive nullable only
- DO NOT change `trips.driver_id` to reference `driver_vehicle_assignments` — trips keep direct FK to drivers
- DO NOT create a `clients_third_party_id` bridge in this phase — deferred (NUIT NOT NULL constraint, different billing cardinality)
- DO NOT seed `mz_provinces` via Alembic data migration — use a seed script or fixture; provinces are static reference data
