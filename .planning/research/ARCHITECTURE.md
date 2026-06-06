# Architecture: Client Entity + Accounts Receivable Integration

**Researched:** 2026-06-06
**Scope:** How to add Client as a first-class entity to the existing billing module, migrate contract.client_name to contract.client_id, add Payments, and build accounts-receivable / aging.
**Confidence:** HIGH — all findings derived from direct codebase inspection of billing/models.py, billing/service.py, contracts/models.py, and the full Alembic migration history.

---

## Existing Baseline (What We're Integrating Into)

### Current billing module state

`BillingDocument` has:

- `contract_id UUID FK contracts.id NULLABLE`
- `client_name VARCHAR(160)` — denormalized string copied from `contract.client_name` at document creation time (see `billing/service.py:create_document` line 377)
- `paid_at TIMESTAMPTZ NULLABLE` — single timestamp, binary "paid/not paid", no partial payment support
- No FK to a `clients` table (does not exist yet)

`Contract` has:

- `client_name VARCHAR(160)` — free-text string, no FK
- No FK to a `clients` table

`BillingItem` has:

- `contract_id UUID FK contracts.id NULLABLE`
- No client FK

`billing/service.py:create_document` explicitly copies `contract.client_name` onto the new `BillingDocument` at creation. This is the denormalization point that must evolve to use `client_id`.

### What does NOT exist yet

- No `clients` table anywhere in the codebase
- No `payments` table
- No aging / statement view or endpoint
- No multi-contract invoice (each `BillingDocument` today has exactly one `contract_id`)

---

## Component Boundaries

### New Module: `backend/app/modules/clients/`

Client is a domain entity with its own lifecycle (CRUD, status, credit limit, payment terms). It belongs in a dedicated module, not inside `billing/` or `contracts/`. Pattern is identical to every other module in the codebase.

Files needed:

```
backend/app/modules/clients/
  __init__.py
  models.py        — Client model
  schemas.py       — ClientCreate, ClientUpdate, ClientResponse
  service.py       — CRUD + _require_client() guard
  router.py        — /api/v1/clients endpoints
```

### Modified Module: `backend/app/modules/contracts/`

`Contract` model gets a new nullable FK `client_id → clients.id`. `client_name` stays on the model as a computed-or-denormalized fallback column during migration (see Migration Strategy section).

### Modified Module: `backend/app/modules/billing/`

- `BillingDocument` gets `client_id UUID FK clients.id NULLABLE` — nullable initially, populated by migration
- `BillingDocument.paid_at` is deprecated in favour of the `payments` table (keep column, stop writing to it after payments module ships)
- `billing/service.py:create_document` must be updated to resolve `client_id` from the contract

### New Sub-module: `backend/app/modules/billing/payments.py`

Payment is tightly coupled to billing lifecycle, not to clients. It lives inside the `billing` module as a sub-service, the same way `despacho.py` lives inside `trips/`. A separate top-level `payments` module would require importing from `billing` anyway.

### New Table in billing module: `payments`

Added via a new migration; its model class lives in `billing/models.py` (consistent with `ExportJob` also living there).

---

## Data Model

### `clients` table

```
clients
  id                  UUID PK default gen_random_uuid()
  tenant_id           UUID FK tenants.id NOT NULL (indexed)
  name                VARCHAR(200) NOT NULL
  trading_name        VARCHAR(200) NULLABLE  -- nome comercial / nome abreviado
  nuit                VARCHAR(20) NULLABLE   -- Número Único de Identificação Tributária
  address             TEXT NULLABLE
  city                VARCHAR(100) NULLABLE
  country             VARCHAR(3) DEFAULT 'MZ'
  phone               VARCHAR(30) NULLABLE
  email               VARCHAR(255) NULLABLE
  payment_terms_days  SMALLINT DEFAULT 30    -- net-30, net-60, net-90
  credit_limit        NUMERIC(14, 2) NULLABLE -- NULL = unlimited
  currency            VARCHAR(3) DEFAULT 'MZN'
  status              VARCHAR(30) DEFAULT 'active'  -- active | suspended | inactive
  notes               TEXT NULLABLE
  created_at          TIMESTAMPTZ server_default now()
  updated_at          TIMESTAMPTZ server_default now() onupdate now()

  Indexes:
    (tenant_id)                           -- standard isolation index
    (tenant_id, name)                     -- lookup by name
    (tenant_id, nuit) WHERE nuit IS NOT NULL  -- unique NUIT per tenant (partial unique)
```

SQLAlchemy model annotation: all monetary columns `Mapped[Decimal]` on `Numeric(14, 2)`, consistent with the Decimal annotation cleanup already done across the codebase.

### `contracts` table changes

```sql
ALTER TABLE contracts
  ADD COLUMN client_id UUID REFERENCES clients(id) NULLABLE;

CREATE INDEX ix_contracts_tenant_client ON contracts (tenant_id, client_id);
```

`client_name` column is kept. After migration auto-creates `Client` records, `client_name` becomes redundant but is preserved for backward compatibility until explicitly removed in a later phase. Do not drop it now — it is referenced in `billing/service.py`, `billing/domain.py` (BillableTripCandidate.client_name), and several serializers.

### `billing_documents` table changes

```sql
ALTER TABLE billing_documents
  ADD COLUMN client_id UUID REFERENCES clients(id) NULLABLE;

CREATE INDEX ix_billing_documents_tenant_client ON billing_documents (tenant_id, client_id);
```

`client_name` column is kept for the same reason. The migration populates `client_id` from the newly created `Client` records (see Migration Strategy).

### `payments` table (new)

```
payments
  id                  UUID PK default gen_random_uuid()
  tenant_id           UUID FK tenants.id NOT NULL (indexed)
  client_id           UUID FK clients.id NOT NULL (indexed)
  billing_document_id UUID FK billing_documents.id NULLABLE (indexed)
                       -- NULLABLE: advance payments before invoice is issued
  payment_date        DATE NOT NULL     -- data valor (value date, not booking date)
  amount              NUMERIC(12, 2) NOT NULL
  currency            VARCHAR(3) DEFAULT 'MZN'
  payment_method      VARCHAR(40) NULLABLE  -- 'bank_transfer' | 'cash' | 'cheque' | 'mpesa'
  reference           VARCHAR(120) NULLABLE -- external ref (bank slip, mpesa confirmation)
  notes               TEXT NULLABLE
  recorded_by         UUID FK users.id NOT NULL  -- who registered the payment
  created_at          TIMESTAMPTZ server_default now()
  updated_at          TIMESTAMPTZ server_default now()

  Indexes:
    (tenant_id, client_id)                       -- client statement queries
    (tenant_id, billing_document_id)             -- document balance queries
    (tenant_id, payment_date DESC)               -- period-based reporting
```

Key design decision: `billing_document_id` is nullable because advance payments and unallocated deposits exist in practice for Mozambican logistics clients. The aging calculation uses `payment_date` (not `created_at`) because value date is what matters for DSO computation.

---

## Migration Strategy: client_name to client_id

This is the highest-risk component of the milestone. Two approaches exist:

### Option A: Auto-create Client records from unique client_names (RECOMMENDED)

The migration script (run as a Python Alembic data migration) does:

1. `SELECT DISTINCT tenant_id, client_name FROM contracts ORDER BY tenant_id, client_name`
2. For each `(tenant_id, client_name)` pair, insert one row into `clients` with `name = client_name` and auto-generated UUID
3. `UPDATE contracts SET client_id = <new_client.id> WHERE tenant_id = ? AND client_name = ?`
4. `UPDATE billing_documents SET client_id = <new_client.id> WHERE tenant_id = ? AND client_name = ?`

Safety properties:

- The migration is wrapped in a transaction — if any step fails, the whole migration rolls back
- The migration is idempotent when re-run: check `WHERE client_id IS NULL` before inserting
- Duplicate `client_name` strings within the same tenant correctly produce ONE `Client` record (the SELECT DISTINCT guarantees this)
- Different `client_name` strings that represent the same company (e.g. "VALE S.A." vs "Vale Mozambique") each produce separate `Client` records — this is correct and expected. Merging clients is a user action post-migration via the manager UI
- Cross-tenant: same `client_name` in tenant A and tenant B produce two separate `Client` records, each scoped to their tenant. The `(tenant_id, name)` index is not unique — two tenants can legitimately have a "Shoprite" client

Why not Option B (require manual mapping): Option B requires building a migration UI before any other work can proceed, adds user friction, and blocks deployment. Auto-creation is safe and reversible (users can merge/rename clients after the fact). The risk of incorrect client grouping is low because the `DISTINCT (tenant_id, client_name)` query already groups contracts by exact string match.

### Alembic migration file structure

Four migration files in sequence:

#### Migration 1: create clients table

```python
# e.g. a1b2_add_clients_table.py
# Creates clients table with all columns, indexes, and RLS policy
```

#### Migration 2: add client_id FKs to contracts and billing_documents

```python
# e.g. b2c3_add_client_id_to_contracts_billing.py
# ADD COLUMN client_id NULLABLE (no data migration here — keeps the migration fast)
# Adds indexes
# Adds RLS-compatible entries for the new tables
```

#### Migration 3: data migration — populate client_id

```python
# e.g. c3d4_backfill_client_id.py
# Runs the SELECT DISTINCT / INSERT INTO clients / UPDATE contracts logic
# Uses op.execute() with raw SQL for performance — avoid ORM in data migrations
# Wrapped in a single transaction via op.get_bind()
```

Splitting schema changes from data changes is the established Alembic pattern in this codebase (observed across the 28 existing migrations). Never mix DDL and DML in the same migration file.

#### Migration 4: create payments table

```python
# e.g. d4e5_add_payments_table.py
# Can be in the same PR as migrations 1-3 but a separate file
# Adds RLS policy on payments table
```

### RLS policy for new tables

The existing RLS migration (`4b0a7802dc3c_add_rls_policies.py`) defines the pattern. New tables need a follow-up migration that applies the same policy. The `TENANT_SCOPED_TABLES` list in that migration must be extended or a new migration must run:

```python
for table in ["clients", "payments"]:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY rls_{table} ON {table}
        AS PERMISSIVE FOR ALL TO rotas_app
        USING (tenant_id::text = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))
    """)
```

---

## Aging Calculation: Endpoint vs View vs Materialized View

Three approaches evaluated against the codebase constraints:

### Option A: Computed endpoint (service layer SQL) — RECOMMENDED

```python
# billing/service.py — new function
async def get_client_aging(db: AsyncSession, tenant_id: UUID, client_id: UUID,
                           as_of: date) -> dict:
    # One query: SUM billing_documents.total_amount grouped by age bucket
    # Less one query: SUM payments.amount for the client
    # Derive outstanding per document, bucket into 0-30 / 31-60 / 61-90 / >90 days
```

Why this is the right approach for ROTAS:

- The existing control_tower and billing services use the same pattern (aggregate queries in service.py, no views)
- PostgreSQL materialized views require `REFRESH MATERIALIZED VIEW` scheduling (an ARQ cron) and drift detection — this is complexity without payoff at current tenant scale (tens of clients per tenant, not thousands)
- Regular PostgreSQL views work but execute the full aggregation on every request — same cost as the endpoint query
- Redis cache (already provisioned, not used) can cache aging results per `(tenant_id, client_id, as_of_date)` with a 5-minute TTL if the query proves slow. This is easier to add later than to remove a materialized view

Aging bucket definition:

- The `as_of` date parameter is critical — aging is always relative to a specific date (end of month for reporting, today for real-time). Make it explicit, not implicitly `now()`.
- Bucket boundaries: `(as_of - issued_at) <= 30` = current, `31-60` = 30 days overdue, `61-90` = 60 days overdue, `>90` = 90+ days overdue
- Outstanding amount per document = `billing_documents.total_amount - SUM(payments.amount WHERE payments.billing_document_id = document.id)`
- Documents in `draft` status are NOT included in aging — only `issued` documents create receivables

### Option B: PostgreSQL view

```sql
CREATE VIEW client_aging_view AS
SELECT
    bd.tenant_id,
    bd.client_id,
    SUM(CASE WHEN age_days <= 30 THEN outstanding ELSE 0 END) AS current_0_30,
    ...
```

Rejected because: views do not support parameters (can't pass `as_of` date), the `CURRENT_DATE` built-in would produce stale results if reports are generated for past months, and RLS on views requires additional `SECURITY INVOKER` configuration that introduces complexity.

### Option C: Materialized view

Rejected for MVP. Requires scheduled refresh (ARQ cron), handles stale data poorly for real-time dashboards, and adds operational overhead. Consider if aging query exceeds 500ms at 10K+ documents per tenant.

---

## Endpoint Design

### New endpoints (clients module)

```
POST   /api/v1/clients                          — create client
GET    /api/v1/clients                          — list clients (paginated)
GET    /api/v1/clients/{client_id}              — get client detail
PATCH  /api/v1/clients/{client_id}              — update client
DELETE /api/v1/clients/{client_id}              — soft-delete (status='inactive')
GET    /api/v1/clients/{client_id}/statement    — client statement: invoices + payments
GET    /api/v1/clients/{client_id}/aging        — aging breakdown with as_of param
```

### New endpoints (payments, inside billing module)

```
POST   /api/v1/billing/payments                 — record payment (idempotency-key required)
GET    /api/v1/billing/payments                 — list payments (filterable by client_id, period)
GET    /api/v1/billing/payments/{payment_id}    — get payment detail
PATCH  /api/v1/billing/payments/{payment_id}    — correct payment (admin only, audit logged)
DELETE /api/v1/billing/payments/{payment_id}    — void payment (admin only, status='voided')
```

### Modified endpoints (billing module)

`GET /api/v1/billing/documents` — add `client_id` filter parameter alongside existing `status` and period filters. The existing `client_name` filter remains but now queries `clients.name` via JOIN.

`GET /api/v1/billing/billable-trips` — the existing `client_name` filter in `list_billable_trips()` should also accept `client_id` for precision filtering.

### New accounts-receivable dashboard endpoint

```
GET /api/v1/billing/ar-summary?as_of=YYYY-MM-DD
```

Returns tenant-wide AR KPIs: total outstanding, total current, total 30/60/90+ days overdue, per-client breakdown. Used by the manager dashboard AR panel.

---

## Data Flow

### Creating a billing document after client migration

```
Manager creates billing document
  POST /api/v1/billing/documents
  payload: { contract_id, billing_period_start, billing_period_end, trip_ids[] }

billing/service.py:create_document()
  → db.get(Contract, payload.contract_id)
  → assert contract.client_id IS NOT NULL  (enforced post-migration)
  → db.get(Client, contract.client_id)
  → BillingDocument(
       client_id=contract.client_id,
       client_name=client.name,   # keep denormalized for display/PDF without JOIN
       contract_id=contract.id,
       ...
    )
```

The `client_name` field on `BillingDocument` continues to be populated (from `client.name` now, not `contract.client_name` directly) to preserve PDF generation and existing serializers without requiring a JOIN on every document read.

### Recording a payment

```
Manager records payment
  POST /api/v1/billing/payments
  Idempotency-Key: <key>
  payload: { client_id, billing_document_id, payment_date, amount, payment_method, reference }

billing/payments.py:record_payment()
  → _require_client(db, tenant_id, client_id)
  → if billing_document_id: _require_billing_document(db, tenant_id, billing_document_id)
  → assert billing_document.client_id == client_id  (mismatch = 409)
  → INSERT payments(...)
  → record_audit_log(action="payment.recorded", ...)
  → if billing_document fully paid: UPDATE billing_documents SET status='paid', paid_at=payment_date
  → commit
```

"Fully paid" detection: `SUM(payments.amount WHERE billing_document_id=?) >= billing_document.total_amount`. Use `>=` not `==` to handle overpayments gracefully (excess tracked as credit, not an error).

### Aging query structure

```python
# Pseudo-SQL for get_client_aging
SELECT
    bd.id,
    bd.total_amount,
    COALESCE(p.paid, 0) AS paid,
    bd.total_amount - COALESCE(p.paid, 0) AS outstanding,
    (as_of - bd.issued_at::date) AS age_days
FROM billing_documents bd
LEFT JOIN (
    SELECT billing_document_id, SUM(amount) AS paid
    FROM payments
    WHERE tenant_id = :tenant_id
      AND billing_document_id IS NOT NULL
    GROUP BY billing_document_id
) p ON p.billing_document_id = bd.id
WHERE bd.tenant_id = :tenant_id
  AND bd.client_id = :client_id
  AND bd.status = 'issued'
  AND bd.total_amount - COALESCE(p.paid, 0) > 0
```

Group the result in Python into buckets `<= 30`, `31-60`, `61-90`, `> 90`. The bucketing logic is trivial (4 comparisons) and does not need to live in SQL.

---

## New vs Modified Components

### New components

| Component | Type | Purpose |
|-----------|------|---------|
| `backend/app/modules/clients/__init__.py` | New file | Module marker |
| `backend/app/modules/clients/models.py` | New file | `Client` SQLAlchemy model |
| `backend/app/modules/clients/schemas.py` | New file | Pydantic schemas for Client CRUD |
| `backend/app/modules/clients/service.py` | New file | Client CRUD service, `_require_client()` |
| `backend/app/modules/clients/router.py` | New file | Client CRUD endpoints + statement + aging |
| `backend/app/modules/billing/payments.py` | New file | Payment service: record, list, void |
| Alembic migration: add_clients_table | New migration | `clients` table + indexes + RLS |
| Alembic migration: add_client_id_to_contracts_billing | New migration | Nullable FK columns + indexes |
| Alembic migration: backfill_client_id | New migration | Data migration from client_name |
| Alembic migration: add_payments_table | New migration | `payments` table + indexes + RLS |

### Modified components

| Component | Change | Risk |
|-----------|--------|------|
| `backend/app/modules/contracts/models.py` | Add `client_id: Mapped[UUID]` (nullable FK) | LOW — additive, nullable |
| `backend/app/modules/billing/models.py` | Add `client_id: Mapped[UUID]` (nullable FK) to `BillingDocument`; add `Payment` model class | LOW — additive |
| `backend/app/modules/billing/schemas.py` | Add `client_id` to `BillingDocumentCreate`; add `PaymentCreate`, `PaymentResponse` | LOW |
| `backend/app/modules/billing/service.py` | `create_document()` resolves `client_id` from contract; `list_documents()` accepts `client_id` filter; `list_billable_trips()` accepts `client_id` filter | MEDIUM — core billing path |
| `backend/app/modules/billing/router.py` | Add payment endpoints; add `client_id` query params | LOW |
| `backend/app/main.py` | Register `clients_router` | LOW |
| `backend/app/database.py` | Add `"clients"` to `MODEL_MODULES` | LOW |
| `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` | No change — a follow-up migration handles RLS for new tables | None |

---

## Build Order (Phase Dependencies)

The dependency graph determines sequencing:

```
Phase 1 — Client model + migration (no other dependencies)
  a. Alembic: clients table
  b. Alembic: client_id FK on contracts + billing_documents (nullable)
  c. Alembic: data migration backfill client_id
  d. clients/ module: model, schema, service, router
  e. main.py + database.py: register module

Phase 2 — Payments (depends on Phase 1: requires clients to exist)
  a. Alembic: payments table
  b. billing/payments.py: service
  c. billing/router.py: payment endpoints
  d. billing/service.py: update create_document to use client_id

Phase 3 — Aging + AR dashboard (depends on Phase 2: requires payments to compute balances)
  a. clients/service.py: get_client_aging(), get_client_statement()
  b. clients/router.py: /statement and /aging endpoints
  c. billing/service.py: get_ar_summary() endpoint
  d. Manager UI: AR dashboard panel

Phase 4 — Cleanup (depends on Phase 1-3 stable)
  a. Make contract.client_id NOT NULL (ALTER TABLE, after verifying backfill complete)
  b. Make billing_document.client_id NOT NULL
  c. Remove client_name from BillingDocumentCreate schema (client_name stays on model for PDF display)
```

Why this order:

1. Client entity must exist before payments can reference it (FK constraint)
2. The backfill migration must run before making `client_id NOT NULL` — split into separate phases so the application can run with nullable columns during the transition window
3. The AR summary endpoint requires both invoices (Phase 1) and payments (Phase 2) to be meaningful; building it in Phase 3 avoids building an endpoint that returns incomplete data
4. Phase 4 cleanup (NOT NULL enforcement) should be a separate deployment to allow verification that no `client_id IS NULL` rows remain before adding the constraint

---

## Multitenant Safety

Every new table follows the existing pattern:

- `tenant_id UUID FK tenants.id NOT NULL` on every new table
- RLS policy using `current_setting('app.tenant_id', true)` applied via Alembic migration
- All service functions accept `tenant_id: UUID` and filter every query with `WHERE tenant_id = :tenant_id`
- `_require_client()` guard function in `clients/service.py` checks `client.tenant_id != tenant_id` before any mutation — same pattern as `_require_vehicle()` in vehicles

Critical cross-table safety check in `record_payment()`: the payment service must verify that `billing_document.client_id == payment.client_id` AND `billing_document.tenant_id == tenant_id` before recording. A manager cannot record a payment against a billing document belonging to a different client (even within the same tenant) — this would corrupt the statement.

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|------------|-------|
| Client model design | HIGH | Inspected contracts/models.py and billing/models.py; NUIT/payment_terms are domain-standard |
| Migration strategy (auto-create from client_name) | HIGH | Inspected create_document() logic — client_name IS copied from contract at creation; DISTINCT grouping is safe |
| Payment model design | HIGH | billing_document.paid_at inspected; partial payment requirement is standard AR pattern |
| Aging endpoint approach | HIGH | Control tower and billing service patterns confirmed; Redis cache already available for optimization |
| Build order | HIGH | FK dependencies are deterministic; nullable-first then NOT NULL is the established migration pattern |
| RLS coverage | HIGH | 4b0a7802dc3c migration inspected; new tables just need a follow-up migration |
| NOT NULL enforcement timing | MEDIUM | Depends on verifying zero NULL rows before alter — risk is manageable with explicit pre-check migration step |

---

## Gaps to Resolve in Phase Research

1. **Multi-contract billing document:** PROJECT.md mentions "faturas por cliente agregando múltiplos contratos no mesmo período". The current `BillingDocument` has a single `contract_id`. Supporting multiple contracts per document requires either removing `contract_id` from `BillingDocument` (breaking change) or keeping one document per contract and introducing a `ClientInvoice` aggregate. This architectural choice should be resolved before Phase 3 starts.

2. **Credit limit enforcement:** `Client.credit_limit` field is defined, but where enforcement happens is unclear. Options: (a) warn on billing document creation when outstanding + new document > credit_limit, (b) block document creation, (c) warn only on the UI. The enforcement policy must be decided before implementing the clients service.

3. **Voided payments:** The `payments` table design needs a `status` column (`active` or `voided`) if void-without-delete is required for audit integrity. The current design uses hard delete via `DELETE`. A voided payment that remains in the table with `status='voided'` is better for audit trails. Decide before writing the migration.

4. **Payment allocation:** The current design allows `billing_document_id NULLABLE` for advance/unallocated payments. If advance payments need to be later allocated to a specific invoice, a payment-allocation link table is needed. This is scope creep for the first version — clearly mark it as out-of-scope in phase planning.
