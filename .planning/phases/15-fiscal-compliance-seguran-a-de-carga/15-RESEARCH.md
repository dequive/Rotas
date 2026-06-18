# Phase 15: Fiscal Compliance + Segurança de Carga — Research

**Researched:** 2026-06-18
**Domain:** PostgreSQL SEQUENCE, fiscal invoice numbering, IVA Mozambique, cargo weight validation, hazmat declarations
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FISC-01 | Numeração sequencial de faturas sem gaps por tenant — PostgreSQL SEQUENCE `invoice_seq_{tenant_id}`, formato `AAAA/NNNN` | Alembic `op.execute()` for raw DDL; `SELECT nextval()` in service; UNIQUE constraint on `(tenant_id, invoice_number)` |
| FISC-02 | Cálculo de IVA Moçambique — taxa padrão 17%, reduzida 5%, zero; campos `iva_rate` e `iva_amount` em `billing_items` e `billing_documents`; breakdown no PDF | New columns on existing models; update `_render_pdf` and `_render_xlsx` in `exporters.py` |
| FISC-03 | Exportação de relatório de compliance XLSX mensal com NUIT do cliente | New ARQ task `task_export_compliance_report`; `ExportJob` reuse; requires `client_nuit` sourced from Contract.client_name or new nuit field |
| LOAD-01 | Validação de peso vs capacidade do veículo — `cargo_weight > vehicle.max_payload_kg` → HTTP 409 | Add `max_payload_kg NUMERIC(10,2)` to `Vehicle`; guard in `create_trip()` and `start_trip()` |
| LOAD-02 | Suporte hazmat — `is_hazmat`, `hazmat_class`, `un_number`, `hazmat_label` em `trips` e `cargo_manifests`; guard em `create_load_permit()` | New columns on `trips` and `cargo_manifests`; guard in `create_load_permit()` |
</phase_requirements>

---

## Summary

Phase 15 adds fiscal compliance infrastructure and cargo safety enforcement to the existing billing and trip modules. The work is entirely backend-heavy with three distinct concerns: (1) deterministic invoice sequencing via PostgreSQL native SEQUENCEs per tenant, (2) IVA tax fields and PDF/XLSX layout updates, and (3) two cargo validation guards.

The codebase is in a mature state after Phases 9-14. The billing module (`exporters.py`, `service.py`, `models.py`) is well-structured and extensible. The ARQ worker pattern in `worker.py` is established and must be extended with `task_export_compliance_report`. The trip service has clear `create_trip()` and `start_trip()` functions that need guard injection. No new modules need to be created — all changes land in existing modules.

The primary technical risk is FISC-01: per-tenant PostgreSQL SEQUENCEs require raw DDL that Alembic does not natively abstract, and existing tenants need sequences backfilled in the same migration. The secondary risk is FISC-03: `client_nuit` is not yet a first-class field in any model — the compliance report requires a NUIT source that must be resolved before planning finalises the data model change.

**Primary recommendation:** Implement in this wave order: (a) migrations + model fields, (b) cargo guards (LOAD-01, LOAD-02 — lowest risk, pure validation), (c) IVA fields and PDF/XLSX update (FISC-02), (d) invoice sequence generation (FISC-01 — highest concurrency risk), (e) compliance report ARQ job (FISC-03).

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy 2 async | >=2.0 (in use) | ORM + async query | Already in use |
| Alembic | >=1.13 (in use) | Migrations + raw DDL via `op.execute()` | Only migration tool in project |
| fpdf2 | >=2.8.7 (in use) | PDF generation with DejaVuSans | Established in Phase 3 |
| openpyxl | in use | XLSX generation | Established in Phase 3 |
| arq | in use | Background job queue | Established in Phase 3/4 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PostgreSQL SEQUENCE | native | Tenant-scoped gapless counters | FISC-01 only |

**Installation:** No new packages required. All dependencies are already in `backend/pyproject.toml`.

**Version verification:** All packages are already installed and in active use. No version changes needed.

---

## Architecture Patterns

### Recommended Project Structure (Phase 15 changes)

```
backend/app/
├── modules/billing/
│   ├── models.py          # ADD: invoice_number, iva_rate, iva_amount to BillingDocument + BillingItem
│   ├── service.py         # ADD: invoice_number generation logic in create_document()/issue_document()
│   │                      # ADD: create_compliance_report_job()
│   └── exporters.py       # UPDATE: _render_pdf() and _render_xlsx() to include IVA rows
├── modules/trips/
│   └── service.py         # ADD: payload weight guard in create_trip() and start_trip()
│   └── models.py          # ADD: is_hazmat, hazmat_class, un_number, hazmat_label
├── modules/vehicles/
│   └── models.py          # ADD: max_payload_kg
├── modules/cargo/
│   ├── models.py          # ADD: is_hazmat, hazmat_class, un_number, hazmat_label to CargoManifest
│   └── service.py         # ADD: hazmat guard in create_load_permit()
├── worker.py              # ADD: task_export_compliance_report() function + WorkerSettings
└── alembic/versions/
    └── XXXX_phase15_fiscal_load.py   # ONE migration for all schema changes
```

### Pattern 1: PostgreSQL SEQUENCE for Invoice Numbering (FISC-01)

**What:** One sequence per tenant, created at tenant registration and backfilled for existing tenants.
**When to use:** Every call to `issue_document()` when `invoice_number` is null.

The sequence name encodes the tenant UUID with underscores replacing hyphens:
`invoice_seq_{tenant_id_no_hyphens}` — e.g., `invoice_seq_550e8400e29b41d4a716446655440000`.

**Sequence creation DDL (used in migration AND in tenant registration):**
```sql
-- Source: PostgreSQL 16 documentation + established Alembic op.execute() pattern
CREATE SEQUENCE IF NOT EXISTS "invoice_seq_{tenant_id_sanitized}"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;
```

**Retrieval and formatting in service layer:**
```python
# Source: SQLAlchemy 2 text() for raw SQL in async sessions
from sqlalchemy import text

async def _next_invoice_number(db: AsyncSession, tenant_id: UUID, year: int) -> str:
    seq_name = f"invoice_seq_{str(tenant_id).replace('-', '_')}"
    result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
    seq_val = result.scalar_one()
    return f"{year}/{seq_val:04d}"
```

**UNIQUE constraint** on `(tenant_id, invoice_number)` on `billing_documents` prevents any double-assignment. Retry on `IntegrityError` is added as a safety net (practically impossible with SEQUENCE, but required by spec).

**Migration strategy for existing tenants:**

```python
# In Alembic upgrade():
# 1. Add column
op.add_column("billing_documents", sa.Column("invoice_number", sa.String(12), nullable=True))
op.create_unique_constraint("uq_billing_documents_tenant_invoice", "billing_documents",
    ["tenant_id", "invoice_number"])

# 2. Create sequences for ALL existing tenants
conn = op.get_bind()
tenant_ids = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
for (tid,) in tenant_ids:
    seq_name = f"invoice_seq_{str(tid).replace('-', '_')}"
    conn.execute(sa.text(f'CREATE SEQUENCE IF NOT EXISTS "{seq_name}" START 1 INCREMENT 1 CACHE 1'))
```

**CRITICAL NOTE ON ALEMBIC TRANSACTION HANDLING:** PostgreSQL DDL (`CREATE SEQUENCE`) is transactional in PG16. However, it cannot run inside the same transaction as other DDL that already acquired a lock. The Alembic migration must use `op.get_bind()` (not `op.execute()` directly) and may need to run `CREATE SEQUENCE` outside the migration transaction block. The safest approach:

```python
def upgrade() -> None:
    # DDL changes in normal migration transaction
    op.add_column(...)
    
    # Sequence creation: execute directly to avoid transaction interference
    # op.execute() works for CREATE SEQUENCE in PG16 since sequences are transactional DDL
    conn = op.get_bind()
    for (tid,) in conn.execute(sa.text("SELECT id FROM tenants")).fetchall():
        seq = f"invoice_seq_{str(tid).replace('-', '_')}"
        conn.execute(sa.text(f'CREATE SEQUENCE IF NOT EXISTS "{seq}"'))
```

**PITFALL:** Alembic's default `--autogenerate` does NOT detect sequences. The migration MUST be hand-written. Autogenerate will not produce the sequence DDL.

### Pattern 2: IVA Tax Fields (FISC-02)

**What:** Add `iva_rate NUMERIC(5,4)` and `iva_amount NUMERIC(10,2)` to both `billing_items` and `billing_documents`. The `billing_documents.tax_amount` column already exists — it becomes the canonical IVA total, calculated as `SUM(billing_items.iva_amount)`.

**IVA rates (Mozambique AT — authoritative as of 2026):**
- Standard: `0.1700` (17%) — applies to most transport services
- Reduced: `0.0500` (5%) — food staples, per Lei n.º 17/2013
- Zero: `0.0000` (0%) — exports and exempt services

**IVA calculation pattern:**
```python
# In create_document() / update item totals
item.iva_rate = payload.iva_rate  # validated: one of {0.1700, 0.0500, 0.0000}
item.iva_amount = (item.amount * item.iva_rate).quantize(Decimal("0.01"))
# Document level
document.tax_amount = sum(item.iva_amount for item in items)
document.subtotal = sum(item.amount for item in items)
document.total_amount = document.subtotal + document.tax_amount
```

**PDF update to `_render_pdf` in `exporters.py`:**
The existing totals block renders only `TOTAL A PAGAR`. It needs to be extended with three lines: SUBTOTAL, IVA (rate + amount), TOTAL COM IVA. The `_RotasPDF` class and `_render_pdf` function accept `BillingDocument` which will now have `subtotal`, `tax_amount`, `total_amount` all populated.

**XLSX update:** The existing total row (`A{total_row}:G{total_row}` merged) needs three rows: subtotal, IVA, total.

### Pattern 3: Compliance Report ARQ Job (FISC-03)

**What:** New ARQ task `task_export_compliance_report(ctx, job_id, month, tenant_id)` following the exact same pattern as `generate_billing_export`.

```python
# Pattern from worker.py generate_billing_export — confirmed working
async def task_export_compliance_report(ctx: dict, job_id: str, month: str, tenant_id: str) -> dict:
    async with ctx["db_factory"]() as db:
        job = await db.scalar(select(ExportJob).where(ExportJob.id == UUID(job_id)))
        job.status = "processing"
        await db.commit()
        try:
            # Query billing_documents for month + join to get client_nuit
            # Generate XLSX via openpyxl
            # Save via save_generated_file()
            job.status = "done"
            job.file_id = file_obj.id
            await db.commit()
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)[:500]
            await db.commit()
```

The `ExportJob.job_type` for compliance report: `"compliance_report"`. No new table needed — `ExportJob` already has `entity_id` (nullable) which can store the month as a hash or be left null.

**NUIT data source issue (see Open Questions):** `client_nuit` must come from somewhere. The `contracts` table has only `client_name` — no NUIT field. The `billing_documents` table has `client_name` but no NUIT. The compliance report XLSX column `client_nuit` will be empty until either (a) a `nuit` field is added to `Contract`, or (b) it falls back to the `clients` table (Phase 5, not yet implemented). The plan must decide: add `client_nuit` to `Contract` now, or emit empty/N/A in the column.

### Pattern 4: Cargo Weight Guard (LOAD-01)

**What:** Validation check inside `create_trip()` and `start_trip()` in `trips/service.py`.

The guard runs after the vehicle is retrieved:
```python
async def create_trip(db, tenant_id, payload, *, actor_id=None):
    # Existing: require_vehicle_and_driver_available(...)
    
    # NEW: LOAD-01 payload guard
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if (
        vehicle
        and vehicle.max_payload_kg is not None
        and payload.cargo_weight is not None
        and payload.cargo_weight > vehicle.max_payload_kg
    ):
        excess_kg = float(payload.cargo_weight - vehicle.max_payload_kg)
        raise ApiError(
            "payload_exceeded",
            f"Cargo weight exceeds vehicle max payload by {excess_kg:.2f} kg.",
            status_code=409,
            details={
                "cargo_weight_kg": float(payload.cargo_weight),
                "max_payload_kg": float(vehicle.max_payload_kg),
                "excess_kg": excess_kg,
            },
        )
```

**Admin override:** A `payload_override_reason: str | None` field on `TripCreate` schema. When present AND the requesting user has `admin` or `owner` role, the guard is bypassed and the override reason is written to audit log.

**start_trip() guard:** Same check, using `trip.cargo_weight` vs `vehicle.max_payload_kg`. The vehicle is loaded from `trip.vehicle_id`.

### Pattern 5: Hazmat Declaration (LOAD-02)

**What:** Guard inside `create_load_permit()` in `cargo/service.py`.

```python
async def create_load_permit(db, tenant_id, trip_id, payload, *, actor_id=None):
    trip = await _require_trip(db, tenant_id, trip_id)
    
    # NEW: LOAD-02 hazmat guard
    if trip.is_hazmat:
        if not trip.hazmat_class or not trip.hazmat_class.strip():
            raise ApiError(
                "hazmat_declaration_required",
                "Trip is marked hazmat — hazmat_class and un_number must be declared before Load Permit.",
                status_code=422,
                details={"trip_id": str(trip_id), "is_hazmat": True},
            )
    # ... rest of existing logic
```

**Alert on hazmat `in_progress`:** When `start_trip()` sets `trip.status = "in_progress"` and `trip.is_hazmat = True`, call the alerts module to create an alert of type `hazmat_active`. The alerts module already exists (`backend/app/modules/alerts/`).

### Anti-Patterns to Avoid

- **Python MAX+1 counter for invoice numbers:** Race condition under concurrency. SEQUENCE is the only correct approach.
- **Storing `iva_rate` as a float:** Floating-point rounding errors on tax calculations. Must be `NUMERIC(5,4)`.
- **Placing compliance XLSX generation inline in the HTTP handler:** Blocks response for multi-hundred-row datasets. Must be ARQ job.
- **DDL+DML in same Alembic migration file:** Violates established project convention (see STATE.md Key Decisions). Sequences are DDL; any data backfill is DML — if a data migration for `invoice_number` on existing docs is needed, it goes in a separate migration.
- **Running `CREATE SEQUENCE` via `op.execute()` inside autogenerate-managed migrations:** Autogenerate will drop them on next `--autogenerate`. Hand-written migration only.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Gapless sequential counters | Python MAX+1 counter | PostgreSQL SEQUENCE | SEQUENCE is atomic; MAX+1 has TOCTOU race under concurrent inserts |
| IVA rounding | Custom float arithmetic | `Decimal.quantize("0.01")` | Float loses precision at centésimo level |
| PDF IVA section | New PDF class | Extend `_render_pdf()` in existing `exporters.py` | Avoids font/layout duplication |
| XLSX compliance report | New XLSX library | `openpyxl` (already in use) | Established pattern |
| Background export | Synchronous HTTP generation | ARQ `task_export_compliance_report` | Same pattern as `generate_billing_export` — already in `WorkerSettings.functions` |

---

## Common Pitfalls

### Pitfall 1: PostgreSQL SEQUENCE and Schema Qualification
**What goes wrong:** Sequence created without schema prefix may conflict across PostgreSQL schemas or fail in Railway's public schema.
**Why it happens:** PostgreSQL sequence names are schema-qualified. The `CREATE SEQUENCE` without schema prefix creates in the current search_path schema.
**How to avoid:** Always use the public schema explicitly or rely on the default search_path (`public`). `CREATE SEQUENCE IF NOT EXISTS "invoice_seq_{uuid}"` — the `IF NOT EXISTS` clause is mandatory to make the migration idempotent.
**Warning signs:** Migration fails on re-run; duplicate sequences.

### Pitfall 2: Sequence Name Length
**What goes wrong:** UUID has 36 chars (32 hex + 4 hyphens). With prefix `invoice_seq_` (12 chars) + UUID with hyphens replaced by underscores (36 chars) = 48 chars total. PostgreSQL identifier limit is 63 bytes.
**Why it happens:** PostgreSQL silently truncates identifiers longer than 63 bytes, causing two sequences to share a name.
**How to avoid:** 48 characters is well within 63-byte limit. Use `str(tenant_id).replace('-', '_')` — produces 32 hex chars + 4 underscores = 36 chars + 12-char prefix = 48 chars total. Safe.
**Warning signs:** Two tenants whose UUIDs differ only in later characters share a sequence.

### Pitfall 3: Alembic Autogenerate Deletes Sequences
**What goes wrong:** A subsequent `alembic revision --autogenerate` generates a migration that drops the sequences since autogenerate does not understand them.
**Why it happens:** Alembic's metadata comparison does not track raw sequences created via `op.execute()`.
**How to avoid:** Add `include_object` filter in `alembic/env.py` to exclude sequence objects, OR simply never use `--autogenerate` for these migrations (hand-written only). The project already hand-writes all migrations.
**Warning signs:** New autogenerate migration contains `DROP SEQUENCE` statements.

### Pitfall 4: `invoice_number` Generated at `create_document()` vs `issue_document()`
**What goes wrong:** Generating the invoice number at draft creation means drafts consume sequence numbers, producing gaps when drafts are deleted.
**Why it happens:** Confusion between document creation (draft) and document issuance.
**How to avoid:** Generate `invoice_number` only inside `issue_document()`, not `create_document()`. The `invoice_number` column on `billing_documents` is nullable; it is populated exactly once at issue time. FISC-01 success criterion confirms this: "Um tenant ao emitir a sua primeira fatura recebe número `2026/0001`".
**Warning signs:** Draft documents with non-null `invoice_number` in the database.

### Pitfall 5: `iva_rate` on `billing_documents` vs `billing_items`
**What goes wrong:** Setting a single `iva_rate` on the document when items can have different rates.
**Why it happens:** Simplification that loses the per-item breakdown required for AT submission.
**How to avoid:** `iva_rate` lives on `billing_items` (per item), and `iva_amount` also lives on each item. The document-level `iva_rate` field is a convenience summary — set to the most common rate or NULL if items have mixed rates. The document `tax_amount` = SUM of item `iva_amount` is the authoritative figure.
**Warning signs:** XLSX compliance report shows a single IVA rate for all items in a mixed-rate document.

### Pitfall 6: Hazmat Alert Fires Synchronously in HTTP Handler
**What goes wrong:** Creating an alert in `start_trip()` blocks if the alert creation fails.
**Why it happens:** Calling `alerts.create_alert()` inline in the trip service.
**How to avoid:** The alert creation for hazmat should be best-effort. Wrap in `try/except` and log errors rather than raising. Trip start must succeed even if the alert fails to create.
**Warning signs:** 500 errors on `start_trip` for hazmat trips; alert table rollback cascades to trip status.

### Pitfall 7: RLS Missing on No New Tables
**What goes wrong:** Phase 15 adds columns to existing tables — no new tables. But if a new table is accidentally introduced (e.g., for compliance report metadata), it needs RLS.
**Why it happens:** Developer adds a new table without reading v2.0 Migration Rules.
**How to avoid:** Phase 15 adds NO new tables. All changes are `ADD COLUMN` on existing RLS-covered tables. If requirements change and a new table is introduced, the v2.0 Migration Rules (CLAUDE.md) require RLS + GRANT in the same CREATE TABLE migration.
**Warning signs:** New table in migration file without `ENABLE ROW LEVEL SECURITY` DDL.

### Pitfall 8: `start_trip()` Loads Vehicle Twice
**What goes wrong:** `start_trip()` currently takes a `trip_id` and retrieves the trip but not the vehicle. Adding the payload guard requires loading the vehicle by `trip.vehicle_id` — must not duplicate the DB call.
**Why it happens:** `start_trip()` signature is `(db, tenant_id, trip_id, payload)` — it does not accept a vehicle.
**How to avoid:** Inside `start_trip()`, load vehicle with `db.get(Vehicle, trip.vehicle_id)` once. This is a single indexed PK lookup, not a query.

---

## Existing Codebase State (Critical Findings)

### `billing_documents` table — current columns
Fields present: `id`, `tenant_id`, `contract_id`, `client_name`, `contract_reference`, `billing_period_start`, `billing_period_end`, `currency`, `subtotal`, `tax_amount`, `total_amount`, `status`, `issued_at`, `paid_at`, `overdue_since_at`, `cancellation_reason`, `file_id`, `created_at`, `updated_at`.

**MISSING for Phase 15:**
- `invoice_number VARCHAR(12)` (FISC-01)
- `iva_rate NUMERIC(5,4)` — document-level convenience (FISC-02)
- `iva_amount NUMERIC(10,2)` — same as `tax_amount` but renamed; see note below

**NOTE on `tax_amount`:** The column `tax_amount NUMERIC(12,2)` already exists. For FISC-02, this column becomes the IVA total. The plan can either (a) add `iva_amount` as a new column (duplicating `tax_amount` with a clearer name) or (b) keep `tax_amount` as the IVA total and document this in code. Approach (b) is less disruptive — `tax_amount` is already used in `serialize_billing_document()` and in the PDF exporter. Recommendation: use `tax_amount` as `iva_amount`, add an `iva_rate` document-level summary field only.

### `billing_items` table — current columns
Fields present: `id`, `tenant_id`, `contract_id`, `billing_document_id`, `trip_id`, `load_permit_id`, `cargo_manifest_id`, `transport_document_id`, `delivery_proof_id`, `client_reference`, `origin`, `destination`, `district`, `cargo_description`, `cargo_class`, `load_state`, `loaded_at`, `delivered_at`, `quantity`, `unit_price`, `amount`, `status`, `created_at`.

**MISSING for Phase 15:**
- `iva_rate NUMERIC(5,4)` (FISC-02)
- `iva_amount NUMERIC(10,2)` (FISC-02)

### `vehicles` table — current columns
Fields present: `id`, `tenant_id`, `plate`, `chassis`, `brand`, `model`, `year`, `color`, `category`, `status`, `current_km`, `fuel_type`, `documents`, `qr_code_hash`, `photo_file_id`, `avg_consumption_target`, `fuel_limit_daily`, `created_at`, `updated_at`.

**MISSING for Phase 15:**
- `max_payload_kg NUMERIC(10,2)` — nullable (LOAD-01)

### `trips` table — current columns
`cargo_weight NUMERIC(12,2)` already exists. No `is_hazmat`, `hazmat_class`, `un_number`, `hazmat_label`.

**MISSING for Phase 15:**
- `is_hazmat BOOLEAN DEFAULT FALSE` (LOAD-02)
- `hazmat_class VARCHAR(10)` (LOAD-02)
- `un_number VARCHAR(10)` (LOAD-02)
- `hazmat_label VARCHAR(50)` (LOAD-02)

### `cargo_manifests` table — current columns
Has `cargo_type`, `cargo_class`, `cargo_description`. No hazmat fields.

**MISSING for Phase 15:**
- `is_hazmat BOOLEAN DEFAULT FALSE` (LOAD-02)
- `hazmat_class VARCHAR(10)` (LOAD-02)
- `un_number VARCHAR(10)` (LOAD-02)
- `hazmat_label VARCHAR(50)` (LOAD-02)

Note: `gross_weight` is typed as `Mapped[float | None]` using `Numeric(12,2)` — this is an inconsistency from before Phase 4 cleanup. Phase 15 migration may correct this to `Mapped[Decimal | None]` while adding hazmat columns.

### `contracts` table — NUIT field
No `client_nuit` field exists on `Contract`. The compliance report (FISC-03) requires NUIT per invoice. This is a data gap. Resolution options:
1. Add `client_nuit VARCHAR(20)` to `contracts` table (minimal change, can be populated manually).
2. Defer NUIT to Phase 5 `clients` table (deferred to future work).
3. Generate compliance report with `client_nuit` as `NULL`/`"N/A"` and mark column as `[a preencher]`.

**Recommendation:** Add `client_nuit VARCHAR(20) NULLABLE` to `contracts` in the Phase 15 migration. Service layer reads `contract.client_nuit` for the compliance report. Null values render as empty string in XLSX — AT submission can be done manually for the first report cycle until Phase 5 populates it from the clients table.

### `tenants` table — NUIT field
`Tenant` model has no NUIT field. The compliance report header should show the tenant's NUIT (issuer). Add `nuit VARCHAR(20) NULLABLE` to `tenants` in the Phase 15 migration.

### `create_trip()` and `start_trip()` in trips/service.py
- `create_trip()` (line 472): Already calls `require_vehicle_and_driver_available()`. The vehicle object is **not** loaded — it must be explicitly fetched for the payload guard.
- `start_trip()` (line 544): Also does not load the vehicle. A `db.get(Vehicle, trip.vehicle_id)` must be added.

### ARQ worker pattern (established in `worker.py`)
The compliance report task follows the same structure as `generate_billing_export`:
1. Retrieve `ExportJob` record → set `status = "processing"` → commit
2. Run XLSX generation with openpyxl
3. Save via `save_generated_file()` → `job.file_id = file_obj.id` → `job.status = "done"` → commit
4. Exception handler: `job.status = "failed"` → `job.error_message = str(exc)[:500]`
5. Add task to `WorkerSettings.functions` list

The `enqueue_export_job()` function in `billing/service.py` needs a new call path for compliance reports — or a new `enqueue_compliance_report_job()` function that sets `job_type = "compliance_report"` and `entity_id = None` (no specific billing document).

### ExportJob.job_type values in use
- `"billing_pdf"` — existing
- `"billing_xlsx"` — existing
- `"compliance_report"` — new for FISC-03

---

## Code Examples

### FISC-01: Invoice Number Generation

```python
# Source: PostgreSQL documentation for SEQUENCE + SQLAlchemy text()
from sqlalchemy import text
from decimal import Decimal

async def _assign_invoice_number(
    db: AsyncSession,
    document: BillingDocument,
    tenant_id: UUID,
) -> str:
    """Generate and assign invoice_number to a BillingDocument at issue time.

    Idempotent: if invoice_number is already set, return it unchanged.
    Sequence name: invoice_seq_{tenant_id_no_hyphens}
    Format: YYYY/NNNN (e.g., 2026/0001)
    """
    if document.invoice_number:
        return document.invoice_number

    seq_name = f"invoice_seq_{str(tenant_id).replace('-', '_')}"
    year = datetime.now(UTC).year
    try:
        result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
        seq_val = result.scalar_one()
        invoice_number = f"{year}/{seq_val:04d}"
        document.invoice_number = invoice_number
        return invoice_number
    except Exception as exc:
        # Sequence may not exist for tenants registered before this migration
        # This should not happen after migration backfills all tenants
        raise ApiError(
            "invoice_sequence_unavailable",
            f"Invoice sequence not found for tenant. Contact support.",
            status_code=500,
        ) from exc
```

### FISC-01: Sequence Creation in Alembic Migration

```python
# Source: Alembic documentation + PostgreSQL CREATE SEQUENCE syntax
import sqlalchemy as sa
from alembic import op

def upgrade() -> None:
    # 1. Add invoice_number column to billing_documents
    op.add_column(
        "billing_documents",
        sa.Column("invoice_number", sa.String(12), nullable=True),
    )
    op.create_unique_constraint(
        "uq_billing_docs_tenant_invoice_number",
        "billing_documents",
        ["tenant_id", "invoice_number"],
    )

    # 2. Add iva_rate and iva_amount to billing_items
    op.add_column("billing_items", sa.Column("iva_rate", sa.Numeric(5, 4), nullable=True))
    op.add_column("billing_items", sa.Column("iva_amount", sa.Numeric(10, 2), nullable=True))

    # 3. Add iva_rate to billing_documents (document-level summary)
    op.add_column("billing_documents", sa.Column("iva_rate", sa.Numeric(5, 4), nullable=True))

    # 4. Add max_payload_kg to vehicles
    op.add_column("vehicles", sa.Column("max_payload_kg", sa.Numeric(10, 2), nullable=True))

    # 5. Add hazmat fields to trips
    op.add_column("trips", sa.Column("is_hazmat", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("trips", sa.Column("hazmat_class", sa.String(10), nullable=True))
    op.add_column("trips", sa.Column("un_number", sa.String(10), nullable=True))
    op.add_column("trips", sa.Column("hazmat_label", sa.String(50), nullable=True))

    # 6. Add hazmat fields to cargo_manifests
    op.add_column("cargo_manifests", sa.Column("is_hazmat", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("cargo_manifests", sa.Column("hazmat_class", sa.String(10), nullable=True))
    op.add_column("cargo_manifests", sa.Column("un_number", sa.String(10), nullable=True))
    op.add_column("cargo_manifests", sa.Column("hazmat_label", sa.String(50), nullable=True))

    # 7. Add client_nuit to contracts
    op.add_column("contracts", sa.Column("client_nuit", sa.String(20), nullable=True))

    # 8. Add nuit to tenants
    op.add_column("tenants", sa.Column("nuit", sa.String(20), nullable=True))

    # 9. Create per-tenant invoice sequences for ALL existing tenants
    conn = op.get_bind()
    tenant_ids = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tid,) in tenant_ids:
        seq_name = f"invoice_seq_{str(tid).replace('-', '_')}"
        conn.execute(sa.text(f'CREATE SEQUENCE IF NOT EXISTS "{seq_name}" START 1 INCREMENT 1 CACHE 1'))
```

### LOAD-01: Payload Guard

```python
# Source: derived from existing create_trip() structure in trips/service.py
async def create_trip(db: AsyncSession, tenant_id: UUID, payload: TripCreate, *, actor_id=None):
    await require_vehicle_and_driver_available(db, tenant_id,
        vehicle_id=payload.vehicle_id, driver_id=payload.driver_id)

    # LOAD-01: Payload weight guard
    vehicle = await db.get(Vehicle, payload.vehicle_id)
    if (
        vehicle
        and vehicle.max_payload_kg is not None
        and payload.cargo_weight is not None
        and payload.cargo_weight > vehicle.max_payload_kg
        and not payload.payload_override_reason  # admin override
    ):
        raise ApiError(
            "payload_exceeded",
            "Cargo weight exceeds vehicle max payload capacity.",
            status_code=409,
            details={
                "cargo_weight_kg": float(payload.cargo_weight),
                "max_payload_kg": float(vehicle.max_payload_kg),
                "excess_kg": float(payload.cargo_weight - vehicle.max_payload_kg),
            },
        )
    if payload.payload_override_reason:
        # Record override in audit log — will happen after trip creation below
        pass  # handled in audit log call
    # ... rest of existing create_trip() logic unchanged
```

### LOAD-02: Hazmat Guard in create_load_permit()

```python
# Source: derived from existing create_load_permit() structure in cargo/service.py
async def create_load_permit(db, tenant_id, trip_id, payload, *, actor_id=None):
    trip = await _require_trip(db, tenant_id, trip_id)

    # LOAD-02: Hazmat declaration guard
    if trip.is_hazmat and (not trip.hazmat_class or not trip.hazmat_class.strip()):
        raise ApiError(
            "hazmat_declaration_required",
            "Trip is marked as hazmat — hazmat_class must be declared before creating Load Permit.",
            status_code=422,
            details={"trip_id": str(trip_id), "is_hazmat": True},
        )

    permit = LoadPermit(tenant_id=tenant_id, trip_id=trip_id, **payload.model_dump())
    # ... rest unchanged
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Python MAX+1 for sequential IDs | PostgreSQL SEQUENCE | Before Phase 5 (decision in ROADMAP Phase 5 notes) | Eliminates race condition under concurrency |
| `float` for monetary values | `Decimal` / `NUMERIC(10,2)` | Phase 4 (04-05-PLAN) | No floating-point rounding errors |
| Single worker.py for all ARQ tasks | Same worker.py extended per phase | Established in Phase 3 | All tasks registered in `WorkerSettings.functions` |
| Tax amount as single blob | Separate `iva_rate` and `iva_amount` per item | Phase 15 (new) | Enables line-item AT reporting |

---

## Open Questions

1. **NUIT source for compliance report (FISC-03)**
   - What we know: `Contract.client_nuit` does not exist yet; `Tenant.nuit` does not exist yet
   - What's unclear: Should NUIT be on `Contract`, on a `clients` table (Phase 5), or both?
   - Recommendation: Add `client_nuit VARCHAR(20) NULLABLE` to `contracts` in Phase 15 migration. Phase 5 will add a `clients` table; when that lands, the compliance report service can JOIN through `clients` instead. For Phase 15 reports, NUIT = `contract.client_nuit` (may be null for existing contracts).

2. **Invoice number reset per year**
   - What we know: Format is `AAAA/NNNN` — e.g., `2026/0001`. ROADMAP says `SELECT nextval('invoice_seq_{tenant_id}')` formatted as `f"{year}/{seq:04d}"`.
   - What's unclear: Does the sequence reset at year boundary? (i.e., should `2027/0001` restart from 1?) Mozambique AT typically expects annual reset.
   - Recommendation: Create ONE sequence per tenant per year: `invoice_seq_{tenant_id}_{year}`. The service checks `current_year` and creates the sequence lazily if it doesn't exist (for new year transitions). Alternatively, use a single sequence and embed the year in the number only for display — gaps at year boundary are acceptable under this approach. **The lazily-created-per-year approach is cleaner for AT compliance but adds complexity.** Planner must decide.

3. **`iva_rate` defaults on existing `billing_items`**
   - What we know: Existing billing items have `iva_rate = NULL` after migration.
   - What's unclear: Should the API reject item creation without `iva_rate`, or default to 0.17?
   - Recommendation: Default `iva_rate` to `0.1700` (standard rate) when not supplied. Add a validator in `BillingItemCreate` schema. Existing null items produce `iva_amount = 0` — no retroactive recalculation needed.

4. **`payload_override_reason` — which roles can override?**
   - What we know: ROADMAP says "Override por admin/owner com campo `payload_override_reason`".
   - What's unclear: RBAC enforcement point — should the router check the role, or the service?
   - Recommendation: Service layer checks `actor_role` parameter (same as `RBAC` pattern in other endpoints). Router injects the user's role via `get_current_principal()`.

---

## Environment Availability

Step 2.6: SKIPPED — Phase 15 is purely code/config/migration changes. No new external dependencies. PostgreSQL SEQUENCE is a native PG16 feature. All existing packages (fpdf2, openpyxl, arq, sqlalchemy) are already installed and active.

---

## Validation Architecture

`workflow.nyquist_validation` is `true` in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio (asyncio_mode=auto) |
| Config file | `backend/pyproject.toml` (tool.pytest.ini_options) |
| Quick run command | `cd backend && python -m pytest tests/test_fiscal_compliance.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FISC-01 | First invoice gets `2026/0001`, second `2026/0002` | unit | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_first_two -x` | Wave 0 |
| FISC-01 | Concurrent issue of two documents produces unique numbers | unit (asyncio) | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_concurrent -x` | Wave 0 |
| FISC-01 | Tenant A and Tenant B sequences are independent | unit | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_cross_tenant -x` | Wave 0 |
| FISC-01 | `IntegrityError` retry does not cause 500 | unit (mock) | `pytest tests/test_fiscal_compliance.py::test_invoice_sequence_integrity_error_retry -x` | Wave 0 |
| FISC-02 | `billing_items` with `iva_rate=0.17` produces correct `iva_amount` | unit | `pytest tests/test_fiscal_compliance.py::test_iva_calculation_standard -x` | Wave 0 |
| FISC-02 | PDF output contains IVA line with rate and amount | unit | `pytest tests/test_billing_export.py::test_pdf_contains_iva_section -x` | Wave 0 (extend existing) |
| FISC-02 | XLSX output has subtotal, IVA, and total rows | unit | `pytest tests/test_billing_export.py::test_xlsx_iva_rows -x` | Wave 0 (extend existing) |
| FISC-02 | Mixed IVA rates across items produce correct document total | unit | `pytest tests/test_fiscal_compliance.py::test_iva_mixed_rates -x` | Wave 0 |
| FISC-03 | Compliance report XLSX has correct columns including `client_nuit` | unit | `pytest tests/test_fiscal_compliance.py::test_compliance_report_xlsx_columns -x` | Wave 0 |
| FISC-03 | ARQ job transitions: `queued → processing → done` | unit (mock arq) | `pytest tests/test_fiscal_compliance.py::test_compliance_report_job_lifecycle -x` | Wave 0 |
| LOAD-01 | `cargo_weight > max_payload_kg` returns HTTP 409 `payload_exceeded` | integration | `pytest tests/test_fiscal_compliance.py::test_payload_exceeded_create_trip -x` | Wave 0 |
| LOAD-01 | `cargo_weight <= max_payload_kg` succeeds | integration | `pytest tests/test_fiscal_compliance.py::test_payload_within_limit -x` | Wave 0 |
| LOAD-01 | `max_payload_kg = NULL` skips the guard (backwards compat) | unit | `pytest tests/test_fiscal_compliance.py::test_payload_guard_null_vehicle_limit -x` | Wave 0 |
| LOAD-01 | Admin override with `payload_override_reason` bypasses guard | integration | `pytest tests/test_fiscal_compliance.py::test_payload_override_admin -x` | Wave 0 |
| LOAD-01 | Start trip also enforces payload guard | integration | `pytest tests/test_fiscal_compliance.py::test_payload_exceeded_start_trip -x` | Wave 0 |
| LOAD-02 | Hazmat trip without `hazmat_class` raises 422 on Load Permit | integration | `pytest tests/test_fiscal_compliance.py::test_hazmat_load_permit_missing_class -x` | Wave 0 |
| LOAD-02 | Hazmat trip with `hazmat_class` creates Load Permit successfully | integration | `pytest tests/test_fiscal_compliance.py::test_hazmat_load_permit_with_class -x` | Wave 0 |
| LOAD-02 | Non-hazmat trip creates Load Permit without hazmat fields | integration | `pytest tests/test_fiscal_compliance.py::test_non_hazmat_load_permit -x` | Wave 0 |
| LOAD-02 | Starting a hazmat trip creates `hazmat_active` alert | integration | `pytest tests/test_fiscal_compliance.py::test_hazmat_alert_on_start_trip -x` | Wave 0 |

### Critical Test Scenarios (Concurrency)

**FISC-01 concurrent invoice generation** — this is the highest-risk test:

```python
# Conceptual test — two concurrent issue_document() calls must produce unique numbers
import asyncio

async def test_invoice_sequence_concurrent(db, tenant_id):
    """Two concurrent issue_document() calls must produce sequential, distinct invoice numbers."""
    doc1 = await create_billing_document(db, tenant_id, ...)
    doc2 = await create_billing_document(db, tenant_id, ...)

    # Issue both concurrently — PostgreSQL SEQUENCE guarantees distinct values
    results = await asyncio.gather(
        issue_document(db, tenant_id, doc1.id, ...),
        issue_document(db, tenant_id, doc2.id, ...),
    )
    numbers = {r["invoice_number"] for r in results}
    assert len(numbers) == 2  # distinct
    # Both should be current year
    year = datetime.now(UTC).year
    assert all(n.startswith(f"{year}/") for n in numbers)
```

Note: Full concurrency testing with real asyncio.gather against a single test DB connection may need separate sessions. The test fixture must use two distinct `AsyncSession` objects. Alternatively, this is a manual verification against a dev database under load. The unit test with mocked `nextval` is sufficient for Wave 0; the concurrency test is a Wave 3 human verification checkpoint.

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_fiscal_compliance.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_fiscal_compliance.py` — covers all 19 Phase 15 test cases above
- [ ] Extend `backend/tests/test_billing_export.py` — add IVA section tests (PDF + XLSX)
- [ ] No new framework needed — pytest + pytest-asyncio already configured

---

## Project Constraints (from CLAUDE.md)

| Constraint | How it applies to Phase 15 |
|-----------|---------------------------|
| FastAPI + Next.js + PostgreSQL — no stack change | No new frameworks. All changes in existing Python backend. |
| Dexie.js 4 schema compatibility | Phase 15 has no driver PWA changes — no Dexie schema bump needed |
| Monetary columns use `Numeric(10,2)` not `float` | `iva_rate NUMERIC(5,4)`, `iva_amount NUMERIC(10,2)`, `max_payload_kg NUMERIC(10,2)` |
| UTF-8 in all PDF/XLSX outputs | No change needed — DejaVuSans already in use |
| Every query filters by `tenant_id` | Compliance report query: `WHERE billing_documents.tenant_id = :tenant_id` |
| New tables with `tenant_id` need RLS in CREATE TABLE migration | Phase 15 adds NO new tables — only `ADD COLUMN` |
| Services return plain dict, never raw ORM | `serialize_billing_document()` updated to include `invoice_number`, `iva_rate` |
| fpdf2 + DejaVuSans for PDF | `exporters.py` already uses this — extend `_render_pdf()` only |
| openpyxl for XLSX | `exporters.py` already uses this — extend `_render_xlsx()` and new compliance XLSX |
| ARQ for background jobs | `task_export_compliance_report` follows `generate_billing_export` pattern exactly |
| GSD workflow — no direct edits outside GSD commands | Enforced by developer workflow, not by this research |
| DESIGN.md for all UI changes | Phase 15 UI changes (vehicle form `max_payload_kg` field, hazmat fields on trip form) must follow DESIGN.md tokens |

---

## Sources

### Primary (HIGH confidence)
- PostgreSQL 16 documentation on CREATE SEQUENCE — serial semantics, transactional guarantees, `IF NOT EXISTS` clause
- SQLAlchemy 2 docs — `text()` for raw SQL, `op.get_bind()` in Alembic context
- Direct code reading: `backend/app/modules/billing/models.py` — confirmed BillingDocument/BillingItem column set
- Direct code reading: `backend/app/modules/billing/service.py` — confirmed `create_document()`, `issue_document()`, `enqueue_export_job()` patterns
- Direct code reading: `backend/app/modules/billing/exporters.py` — confirmed `_render_pdf()` and `_render_xlsx()` structure
- Direct code reading: `backend/app/modules/trips/service.py` (lines 472-587) — confirmed `create_trip()` and `start_trip()` signatures
- Direct code reading: `backend/app/modules/trips/models.py` — confirmed `cargo_weight` exists, no hazmat fields
- Direct code reading: `backend/app/modules/vehicles/models.py` — confirmed no `max_payload_kg` field
- Direct code reading: `backend/app/modules/cargo/models.py` — confirmed `CargoManifest` has no hazmat fields
- Direct code reading: `backend/app/modules/cargo/service.py` — confirmed `create_load_permit()` signature
- Direct code reading: `backend/app/worker.py` — confirmed ARQ task pattern, `WorkerSettings.functions`, `generate_billing_export` structure
- Direct code reading: `backend/app/modules/tenants/models.py` — confirmed no `nuit` field on Tenant
- Direct code reading: `backend/app/modules/contracts/models.py` — confirmed no `client_nuit` on Contract
- Direct code reading: `backend/tests/conftest.py` — confirmed pytest fixture structure
- Direct code reading: `backend/app/config.py` — confirmed no fiscal-specific settings

### Secondary (MEDIUM confidence)
- Mozambique AT (Autoridade Tributária) IVA rates: standard 17%, reduced 5% (food staples per Lei n.º 17/2013), zero (exports). Rates are well-established in regional tax practice. No direct AT web verification performed.
- PostgreSQL SEQUENCE identifier length limit (63 bytes): documented in PostgreSQL source; 48-char sequence names are safe.

### Tertiary (LOW confidence)
- Annual sequence reset requirement for Mozambique AT: inferred from "AAAA/NNNN" format convention. No official AT regulation text confirmed. Annual reset recommended as safer for AT compliance but not verified against current AT regulation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all packages already in use, no new dependencies
- Architecture: HIGH — code directly read, all patterns verified against existing implementations
- Pitfalls: HIGH — derived from direct code analysis and established project patterns
- Mozambique IVA rates: MEDIUM — well-known in regional practice, not verified against live AT documentation
- Annual SEQUENCE reset: LOW — recommended but not AT-verified

**Research date:** 2026-06-18
**Valid until:** 2026-08-18 (stable domain — PostgreSQL, fpdf2, openpyxl APIs do not change rapidly)
