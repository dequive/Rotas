---
phase: 23-third-party-registry
plan: 01
subsystem: database
tags: [third-party, migrations, orm, rls, seed]
completed: 2026-06-19
commits:
  - 0634345
  - 15f081d
  - 0e9c608
---

# Phase 23 Plan 01: Database — Core Third Party Tables Summary

**One-liner:** mz_provinces + four tenant-scoped third-party tables via chained Alembic migrations, SQLAlchemy 2 ORM models registered in MODEL_MODULES, and an idempotent province seed script using ISO 3166-2:MZ codes.

## What Was Created

### Migrations

**`tp01a_add_mz_provinces.py`** (chains from `acfa8ae500c0`):
- Creates `mz_provinces(code PK, name, name_local, region)` — platform-level, no tenant_id
- `GRANT SELECT ON mz_provinces TO rotas_app` — no RLS (correct: no tenant scoping needed)

**`tp01b_add_third_party_tables.py`** (chains from `tp01a`):
- Creates `third_parties` — identity registry with NUIT uniqueness per tenant, verified_by FK to users
- Creates `third_party_roles` — operational roles (fuel_supplier, spare_parts_supplier, service_provider, transport_subcontractor) with unique constraint per (third_party_id, role_type)
- Creates `supplier_profiles` — 1:1 extension (unique third_party_id), payment_terms, credit_limit (Numeric 14,2), bank details
- Creates `service_provider_profiles` — 1:1 extension, JSONB service_categories + coverage_province_codes, rate_per_hour
- All four tenant-scoped tables include RLS block in the same migration (v2.0 rule): GRANT + ENABLE RLS + FORCE RLS + tenant_isolation policy

### ORM Models (`backend/app/modules/third_party/models.py`)

- `MzProvince` — code PK, name, name_local, region
- `ThirdParty` — full identity fields + UniqueConstraint(tenant_id, nuit) + verified_by FK
- `ThirdPartyRole` — UniqueConstraint(third_party_id, role_type), CASCADE DELETE from third_parties
- `SupplierProfile` — unique third_party_id (1:1), Numeric(14,2) credit_limit
- `ServiceProviderProfile` — unique third_party_id (1:1), JSONB columns, Numeric(10,2) rate_per_hour

All models use SQLAlchemy 2 `Mapped[type]` / `mapped_column(...)` style consistent with `drivers/models.py`.

### Module Registration

`backend/app/database.py` MODEL_MODULES now includes `"third_party"` (inserted at position 2, after `"tenants"`).

### Seed Script (`backend/scripts/seed_mz_provinces.py`)

Inserts all 11 Mozambique provinces using ISO 3166-2:MZ codes with `ON CONFLICT (code) DO NOTHING` for idempotency. Includes name_local (Portuguese) and region classification (Sul/Centro/Norte).

## Deviations from Plan

**1. [Rule 2 - Enhancement] Added `name_local` and `region` columns to `mz_provinces`**
- The prompt spec listed `name_local VARCHAR(80)` in the schema definition but the plan body's Task 1 code showed only `name` and `region`. I included both `name_local` (for Portuguese local names) and `region` in the migration and ORM model, matching the full schema spec in the prompt header. This ensures the seed script can store both the English name and the local Portuguese name as designed.

**2. [Rule 2 - Enhancement] Added `verified_at` and `verified_by` to ThirdParty model**
- The full table schema in the prompt included `verified_at TIMESTAMPTZ` and `verified_by UUID REFERENCES users(id)`. These were included in the migration and ORM model for completeness and correctness.

**3. ISO 3166-2:MZ province codes used in seed script**
- Plan Task 4 body showed short codes (CD, MP, GZ…). The prompt header's "Tables to create" section specified ISO codes (MZ-MPM, MZ-L, MZ-G…). ISO codes were used in the seed script as they match the standard and provide better interoperability.

## Known Stubs

None. This plan creates pure database infrastructure. No stubs exist — all columns are fully defined and functional.

## Acceptance Criteria Status

- [x] `backend/app/modules/third_party/models.py` exists with all 5 ORM model classes
- [x] `backend/app/database.py` MODEL_MODULES includes `"third_party"`
- [x] `tp01a_add_mz_provinces.py` exists with GRANT SELECT, no RLS
- [x] `tp01b_add_third_party_tables.py` exists with RLS blocks for all 4 tenant-scoped tables
- [x] `backend/scripts/seed_mz_provinces.py` exists and uses ON CONFLICT DO NOTHING (idempotent)
- [ ] `alembic upgrade head` — requires running DB (manual verification)
- [ ] `python scripts/seed_mz_provinces.py` twice — requires running DB (manual verification)
