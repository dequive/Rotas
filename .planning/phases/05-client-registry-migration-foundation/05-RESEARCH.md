# Phase 5: Client Registry + Migration Foundation — Research

**Researched:** 2026-06-19
**Domain:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL (DDL migrations, DML backfill, RLS, sequences) + Next.js 14 App Router
**Confidence:** HIGH

---

## Summary

Phase 5 introduces the `clients` table as a first-class entity and backfills existing `contracts` and `billing_documents` rows with `client_id` foreign keys — with zero data loss. The codebase is well-understood: 43 migrations, 22 routers, and 21 modules have been audited. The exact migration pattern (DDL-only file, DML-only file, separated by design) is already established and must be followed strictly.

**Important: CLI-05 (invoice sequential numbering) is already implemented.** Phase 15 (`c7d8e9f0a1b2`) fully delivered `_assign_invoice_number()` in `billing/service.py` using `SELECT nextval()` on per-tenant per-year PostgreSQL sequences. The model already has `invoice_number: Mapped[str | None]` and a `uq_billing_docs_tenant_invoice_number` unique constraint. The planner must include a stub test and validation step for CLI-05 but must NOT re-implement the sequence logic — it already works.

The primary technical risk is the backfill in migration (c): `client_name` values across `contracts` and `billing_documents` may have whitespace or case variants that would incorrectly create duplicate client records. A pre-migration audit query is mandatory before any backfill code is written. The `client_name` field is NOT dropped after backfill — it is retained as a denormalized legal snapshot on both tables.

**Primary recommendation:** Four strictly separated Alembic migrations in the order: (a) CREATE clients + RLS + GRANT, (b) ADD FKs + due_date (nullable), (c) backfill data, (d) CREATE payments table scaffold. Run the pre-migration audit query in Wave 0 before any migration file is written.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | Gestor pode criar, editar e desactivar um cliente com NUIT, nome comercial, morada, cidade, telefone e email — dentro do contexto do seu tenant | New `clients` module: model, schemas, service, router + 4 CRUD endpoints (LIST, POST, GET, PATCH) |
| CLI-02 | Cliente tem prazo de pagamento padrão configurável (30/45/60/90 dias) e limite de crédito com aviso visual quando o saldo em aberto o ultrapassa | `payment_terms_days` + `credit_limit` fields on `clients`; `outstanding_balance` computed in service; warning logic in frontend using `(outstanding_balance / credit_limit) * 100` |
| CLI-03 | Sistema migra os registos `client_name` existentes em Contratos e Faturas para referências `client_id` sem perda de dados históricos — `client_name` mantido como cache desnormalizado | Migrations (b) + (c): nullable FK add then DML backfill; `client_name` NOT dropped; pre-migration audit required |
| CLI-04 | Contrato referencia `client_id`; gestor selecciona cliente ao criar ou editar um contrato | ContractCreate/ContractPatch schemas get `client_id: UUID \| None`; `ClientCombobox` component in ContractFormModal replaces free-text `client_name`; existing `client_name` field kept as denormalized cache |
| CLI-05 | Faturas emitidas têm número sequencial por tenant sem gaps (formato `AAAA/NNNN`) gerado por PostgreSQL SEQUENCE | ALREADY IMPLEMENTED in Phase 15. `_assign_invoice_number()` in `billing/service.py` + `invoice_number` column + unique constraint all exist. Wave 0 stub test + validation only — no re-implementation. |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

### Stack
- FastAPI + Next.js + Vite/React + PostgreSQL — stack is locked, no substitutions
- SQLAlchemy 2.0 async with `AsyncSession`; Alembic for all migrations
- Python 3.11+ (actual installed: 3.13 based on `.pyc` files)
- Next.js 14 App Router; React 18; `@tanstack/react-query ^5.0.0`

### v2.0 Migration Rules (mandatory for every new `tenant_id` table)
Every CREATE TABLE migration for a table with `tenant_id` MUST include in the same file:
```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id::text = current_setting('app.tenant_id', true));
GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app;
```
The `notification_outbox` migration (`d5e6f7a8b9c0`) is the canonical example — GRANT comes before RLS block, all four statements in the `upgrade()` function after `op.create_table()`. Violation is a plan blocker.

### Multitenancy Safety
- Every query must filter by `tenant_id` — never remove this filter
- `tenant_id` extracted from JWT by `get_current_principal` — never from request body
- `_require_*` helpers must check `tenant_id` match before returning entities

### Service Layer
- Services return `dict`, never raw ORM objects
- `serialize_*()` functions decouple ORM shape from response shape
- `record_audit_log()` called within the same DB session before commit
- Services accept `db: AsyncSession` via `Depends(get_session)`

### Coding Conventions
- `ruff` linter rules: E, F, I, UP, B; `line-length = 100`; `target-version = "py311"`
- No business logic in routers — routers handle HTTP mechanics only
- Pagination via `limit/offset` query params: `Query(50, ge=1, le=200)`

### Multitenant Safety
- All queries scoped to `tenant_id` — never global cross-tenant reads in `rotas_app` role
- DDL (CREATE TABLE, ALTER TABLE) must use `ALEMBIC_DATABASE_URL` (rotas_admin role, BYPASSRLS)

---

## Standard Stack

### Core (backend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlalchemy[asyncio]` | `>=2.0` | ORM + async queries | Already in use; `Mapped[]` typed column pattern established |
| `alembic` | `>=1.13` | Migrations | 43 migrations already in this pattern |
| `asyncpg` | `>=0.29` | PostgreSQL async driver | Already in use |
| `fastapi` | `>=0.111` | HTTP API | Project stack |
| `pydantic` v2 | (bundled with FastAPI) | Schemas | All schemas use Pydantic BaseModel |

### Core (frontend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@tanstack/react-query` | `^5.0.0` | Data fetching / cache | Already installed in apps/manager |
| `shadcn/ui` | (installed) | UI primitives | Tailwind + Radix already configured |
| `lucide-react` | `^0.468.0` | Icons | Already installed |

### No New Packages Required
Phase 5 introduces no new Python packages and no new npm packages. All building blocks exist:
- RLS enforcement: `rotas_app` and `rotas_admin` roles created in Phase 9 (complete)
- PostgreSQL SEQUENCE: native PostgreSQL, no library needed
- Combobox pattern: `Popover` + `Command` (shadcn) already installed
- `Dialog`, `Input`, `Button`, `Alert`, `Skeleton`, `Badge`: all in `components/ui/`

---

## Architecture Patterns

### Module Structure (replicate contracts module exactly)

```
backend/app/modules/clients/
├── __init__.py
├── models.py        # Client SQLAlchemy model
├── schemas.py       # ClientCreate, ClientPatch, ClientResponse
├── service.py       # list_clients, create_client, get_client, patch_client, serialize_client
└── router.py        # APIRouter(prefix="/clients")
```

Register in `backend/app/database.py` MODEL_MODULES tuple (add `"clients"` after `"contracts"`).
Register router in `backend/app/main.py` with `app.include_router(clients_router, prefix=api)`.

### Pattern 1: Client Model with Outstanding Balance

`outstanding_balance` is NOT stored on the `clients` table directly. It is computed at query time via a `SELECT SUM(billing_documents.total_amount - COALESCE(paid_amount,0))` subquery or populated from Phase 6 payment data. In Phase 5, it can be computed as `SUM(billing_documents.total_amount) WHERE client_id = ? AND status = 'issued'` since no payments table exists yet.

```python
# Source: established codebase pattern (billing/service.py)
class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    trading_name: Mapped[str] = mapped_column(String(160), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    nuit: Mapped[str] = mapped_column(String(9))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

**UniqueConstraint:** `(tenant_id, nuit)` — one NUIT per tenant. This prevents duplicate client registration for the same tax ID.

### Pattern 2: Four Strictly Separated Migrations

The four migrations must follow the DDL-never-with-DML rule established in 43 prior migrations:

**Migration (a) — CREATE clients table (DDL only)**
```python
# Source: d5e6f7a8b9c0_add_notification_outbox.py — canonical v2.0 pattern
def upgrade() -> None:
    op.create_table("clients", ...)
    op.create_index(...)
    # RLS + GRANT in same migration — mandatory per v2.0 rule
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON clients TO rotas_app")
    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON clients
        USING (tenant_id::text = current_setting('app.tenant_id', true))
    """)
```

**Migration (b) — ADD nullable FKs + due_date (DDL only)**
```python
def upgrade() -> None:
    op.add_column("contracts",
        sa.Column("client_id", sa.UUID(), nullable=True))
    op.create_foreign_key(None, "contracts", "clients", ["client_id"], ["id"])
    op.create_index("ix_contracts_client_id", "contracts", ["client_id"])

    op.add_column("billing_documents",
        sa.Column("client_id", sa.UUID(), nullable=True))
    op.create_foreign_key(None, "billing_documents", "clients", ["client_id"], ["id"])
    op.create_index("ix_billing_documents_client_id", "billing_documents", ["client_id"])

    op.add_column("billing_documents",
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_billing_documents_due_date", "billing_documents", ["due_date"])
```

**Migration (c) — Backfill data (DML only — NO DDL)**
```python
# Source: established project pattern — DDL and DML never in same Alembic file
def upgrade() -> None:
    conn = op.get_bind()
    # Step 1: Get distinct (tenant_id, client_name) from contracts
    rows = conn.execute(sa.text("""
        SELECT DISTINCT
            lower(trim(client_name)) AS client_name_normalized,
            client_name,
            tenant_id
        FROM contracts
        WHERE client_name IS NOT NULL AND client_name != ''
    """)).fetchall()

    # Step 2: INSERT one client per distinct (tenant_id, client_name_normalized)
    # Step 3: UPDATE contracts.client_id WHERE lower(trim(client_name)) matches
    # Step 4: UPDATE billing_documents.client_id from their contract's client_id
    # (see Pitfall: Backfill Variant Detection below)
```

**Migration (d) — CREATE payments table scaffold (DDL only)**
```python
# Scaffolded empty table for Phase 6 — must have RLS + GRANT per v2.0 rule
def upgrade() -> None:
    op.create_table("client_payments", ...)
    op.create_table("payment_allocations", ...)
    # RLS + GRANT for both tables
```

### Pattern 3: Alembic Migration Chain

The HEAD migration as of 2026-06-19 is `c7d8e9f0a1b2` (Phase 15 fiscal columns). Each new migration sets its `down_revision` to the previous HEAD. The four Phase 5 migrations form a linear chain:

```
c7d8e9f0a1b2  →  {migration_a_id}  →  {migration_b_id}  →  {migration_c_id}  →  {migration_d_id}
(Phase 15)         (a: clients)         (b: FKs)            (c: backfill)        (d: payments)
```

Each migration file needs a unique revision ID (hex string, 12 chars).

### Pattern 4: CLI-04 Schema Changes (contracts module)

`ContractCreate` schema currently has `client_name: str` as a required field. After Phase 5:
- Add `client_id: UUID | None = None` to `ContractCreate` and `ContractPatch`
- Keep `client_name: str | None = None` (was required, now optional for backward compat during migration window)
- Service `create_contract()` must: if `client_id` is provided → look up client `trading_name` → populate `contract.client_name` from client record (maintains the denormalized snapshot)
- `list_contracts` endpoint: add `client_id: UUID | None` filter parameter

### Pattern 5: Frontend Page Structure

```
apps/manager/app/
├── clientes/
│   ├── page.tsx              # Client list (Server Component)
│   └── [id]/
│       └── page.tsx          # Client detail (Server Component)
├── components/
│   ├── ClientFormModal.tsx   # Create/edit modal
│   └── ClientCombobox.tsx    # Combobox for ContractFormModal
└── components/
    └── SidebarLayout.tsx     # Add "clientes" nav entry to Financeiro section
```

Data fetching uses `apiFetch()` from `apps/manager/app/lib/api.ts` — same pattern as all other pages.

### Anti-Patterns to Avoid

- **Never put DDL and DML in the same Alembic file.** CREATE TABLE with an inline INSERT or UPDATE will cause transaction issues on some PostgreSQL versions and violates the project's established 43-migration pattern.
- **Never use Python MAX+1 for invoice numbers.** Already implemented with `SELECT nextval()` — do not add a fallback counter.
- **Never drop `client_name` from `contracts` or `billing_documents`.** It is a legal archive field and a denormalized cache for display performance.
- **Never add `client_id NOT NULL` constraint in migration (b).** Backfill must complete (migration c) before any NOT NULL constraint can be considered — and even then, historical records without a matching client_name would fail.
- **Never use `SET app.tenant_id` (without LOCAL)** in tests or service code. Phase 9 established `SET LOCAL` to prevent connection pool contamination.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sequential invoice numbering | Python counter, MAX+1, UUIDs | PostgreSQL `CREATE SEQUENCE` + `nextval()` | Already implemented in `_assign_invoice_number()` in billing/service.py. MAX+1 has race conditions under concurrent requests. |
| Combobox with search | Custom dropdown + input | shadcn `Popover` + `Command` (cmdk) | Already installed; consistent with project's combobox pattern; keyboard accessible |
| Client form modal | Custom dialog | shadcn `Dialog` | Already installed in `components/ui/dialog.tsx` |
| Credit limit warning | Custom banner | shadcn `Alert` | Already installed; use `variant="default"` for warning, `variant="destructive"` for exceeded |
| NUIT validation | Hand-coded regex | Pydantic `Field(pattern=r'^\d{9}$')` | Pydantic validators run on schema parse; no separate validator needed |

---

## CLI-05: Already Implemented — Do Not Re-implement

This is the most important discovery. **CLI-05 is complete.** Evidence:

1. `billing/models.py` line 44: `invoice_number: Mapped[str | None] = mapped_column(String(12), nullable=True)`
2. `billing/models.py` lines 14-17: `uq_billing_docs_tenant_invoice_number` unique constraint on `(tenant_id, invoice_number)`
3. `billing/service.py` lines 28-55: `_assign_invoice_number()` uses `CREATE SEQUENCE IF NOT EXISTS` + `SELECT nextval()`, format `{year}/{seq_val:04d}`
4. Migration `c7d8e9f0a1b2`: creates sequences for all existing tenants; lazy creation handles new tenants
5. `billing/service.py` line 620: `_assign_invoice_number()` called at invoice issuance

**The planner must:** include a Wave 0 test stub in `test_clients_api.py` that verifies the `AAAA/NNNN` format is present on issued invoices, and a validation step that confirms the feature works end-to-end. No service code, no migration, no sequence creation — only frontend display (`MonoCell` in invoice table) and backend test coverage.

---

## Common Pitfalls

### Pitfall 1: Backfill Creates Duplicate Clients from Variant Spellings

**What goes wrong:** `client_name = "Cimentos de Moçambique"` in one contract and `client_name = "  Cimentos de Moçambique"` (leading space) in another — two different clients created in the backfill for the same real entity.

**Why it happens:** The `client_name` field on `Contract` was free-text entry. Real data will have whitespace variants, case variants, and typos.

**How to avoid:** Mandatory pre-migration audit query (run before writing migration (c)):
```sql
SELECT tenant_id, lower(trim(client_name)), count(*), array_agg(DISTINCT client_name)
FROM contracts
WHERE client_name IS NOT NULL AND client_name != ''
GROUP BY 1, 2
HAVING count(*) > 1
ORDER BY 1, 3 DESC;
```
Review the output. Groups with `count > 1` and different `array_agg` values are variant spellings. The backfill migration must normalize with `lower(trim())` before inserting clients, and must group by the normalized form. The `trading_name` stored on the new client record should use the most common variant (or the longest non-empty value).

**Warning signs:** The STATE.md TODO explicitly lists this: "Run pre-migration audit query before writing Phase 5 migration code."

### Pitfall 2: RLS Blocks Backfill Migration

**What goes wrong:** Migration (c) runs as `rotas_app` role. RLS is now active on `contracts` and `billing_documents`. The `SET LOCAL app.tenant_id` is not set during Alembic execution → RLS returns zero rows → backfill inserts nothing → all contracts remain with `client_id = NULL`.

**Why it happens:** Phase 9 enabled RLS on `contracts` and `billing_documents`. The backfill migration reads from these tables and must run as `rotas_admin` (BYPASSRLS).

**How to avoid:** Migration (c) must be run using `ALEMBIC_DATABASE_URL` which connects as `rotas_admin` (BYPASSRLS). The `op.get_bind()` in Alembic uses whatever connection the migration runner provides. Confirm in Railway that `ALEMBIC_DATABASE_URL` connects as `rotas_admin` before running migration (c). Document this in the Wave 3 execution instructions.

**Warning signs:** `SELECT count(*) FROM contracts WHERE client_id IS NULL` returns same count after backfill runs.

### Pitfall 3: due_date Not Added in Phase 5

**What goes wrong:** `due_date` is added in Phase 7 (AR) instead of Phase 5. Phase 7 then requires a second backfill migration to populate `due_date` for all existing issued invoices. Aging queries fail or return wrong results for historical invoices.

**Why it happens:** Phase 7 logically "owns" aging, so `due_date` seems like a Phase 7 concern.

**How to avoid:** `due_date` MUST be added in migration (b) alongside `client_id`. Add it as `nullable=True`. The backfill in migration (c) should populate `due_date` for issued documents as `issued_at + INTERVAL '{payment_terms_days} days'` (using the tenant's or contract's default). For documents without a contract link, leave `due_date = NULL` and let Phase 7 handle it.

**Warning signs:** Key Decision in STATE.md: "due_date added in Phase 5 migration (b) alongside client_id — not in Phase 7."

### Pitfall 4: Payments Table Not Scaffolded in Phase 5

**What goes wrong:** Migration (d) is skipped or deferred to Phase 6. Phase 6 then creates the `client_payments` and `payment_allocations` tables for the first time. If any payment rows have already been manually inserted, retrofitting the schema is a high-risk migration.

**Why it happens:** Phase 5 is about clients, not payments.

**How to avoid:** Migration (d) must CREATE `client_payments` and `payment_allocations` with full schema (including all Phase 6 fields) in Phase 5, even with no service code. Phase 6 only adds service layer and routes. Both tables need RLS + GRANT per v2.0 rules.

### Pitfall 5: `client_id` Composite Index Missing for Aging

**What goes wrong:** `billing_documents` table has `(tenant_id, client_id, due_date)` queried together in Phase 7 aging. If no composite index exists, aging queries scan the full `billing_documents` table per tenant.

**Why it happens:** Phase 5 only adds individual column indexes, forgetting the composite needed for Phase 7.

**How to avoid:** Add a composite index `(tenant_id, client_id, due_date)` on `billing_documents` in migration (b) — the same migration that adds these columns. This index is listed as a Phase 7 requirement in ROADMAP.md but is logically created when the columns are added.

### Pitfall 6: client_name in ContractCreate Breaks Existing API Consumers

**What goes wrong:** Changing `client_name: str` (required) to `client_name: str | None` in `ContractCreate` may silently break existing callers that rely on the required field for validation.

**Why it happens:** Schema changes to required → optional fields appear backward-compatible but change validation semantics.

**How to avoid:** Keep `client_name: str | None = None` and `client_id: UUID | None = None` both optional in `ContractCreate`. In the service layer, enforce that at least one of them is provided: `if not payload.client_name and not payload.client_id: raise ApiError(...)`. After backfill completes and gate passes, `client_id` becomes the preferred path but the free-text path remains for backward compat.

### Pitfall 7: `nuit` Uniqueness Constraint Blocks Duplicate Client Creation

**What goes wrong:** Two managers from the same company try to create a client for the same NUIT (e.g., a supplier used by both contract lines). The `UNIQUE(tenant_id, nuit)` constraint rejects the second insert with a PostgreSQL `IntegrityError`.

**Why it happens:** NUIT uniqueness per tenant is the correct design, but callers need a clear error.

**How to avoid:** Wrap `db.add(client); await db.flush()` in a `try/except IntegrityError` and re-raise as `ApiError("nuit_already_exists", "NUIT já existe neste tenant.", status_code=409)`. Same pattern as `contract_reference_exists` in `contracts/service.py`.

---

## Code Examples

### Canonical RLS + GRANT block (from `d5e6f7a8b9c0_add_notification_outbox.py`)
```python
# After op.create_table() and op.create_index() calls:
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON notification_outbox TO rotas_app")
op.execute("ALTER TABLE notification_outbox ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE notification_outbox FORCE ROW LEVEL SECURITY")
op.execute("""
    CREATE POLICY tenant_isolation ON notification_outbox
    USING (tenant_id::text = current_setting('app.tenant_id', true))
""")
```
Apply this exact pattern to `clients`, `client_payments`, and `payment_allocations`.

### serialize_client pattern (from contracts/service.py)
```python
def serialize_client(client: Client) -> dict:
    return {
        "id": client.id,
        "tenant_id": client.tenant_id,
        "trading_name": client.trading_name,
        "legal_name": client.legal_name,
        "nuit": client.nuit,
        "address": client.address,
        "city": client.city,
        "phone": client.phone,
        "email": client.email,
        "payment_terms_days": client.payment_terms_days,
        "credit_limit": client.credit_limit,
        "is_active": client.is_active,
        "created_at": client.created_at,
        "updated_at": client.updated_at,
        # outstanding_balance injected by get_client_with_balance()
    }
```

### ContractCreate schema update (contracts/schemas.py)
```python
class ContractCreate(BaseModel):
    client_id: UUID | None = None       # NEW — preferred path
    client_name: str | None = None      # KEPT — denormalized cache; also backward compat
    client_nuit: str | None = None      # already exists from Phase 15
    contract_reference: str
    # ... rest unchanged
```

### Pre-migration audit query (run before writing migration (c))
```sql
SELECT
    tenant_id,
    lower(trim(client_name)) AS normalized,
    count(*) AS occurrences,
    array_agg(DISTINCT client_name ORDER BY client_name) AS variants
FROM contracts
WHERE client_name IS NOT NULL AND client_name != ''
GROUP BY 1, 2
HAVING count(*) > 1
ORDER BY 1, 3 DESC;
```

### Outstanding balance computation (Phase 5 interim — before payments table)
```python
# In clients/service.py — until client_payments table is populated in Phase 6
from sqlalchemy import select, func
from app.modules.billing.models import BillingDocument

async def get_outstanding_balance(db: AsyncSession, client_id: UUID, tenant_id: UUID) -> Decimal:
    result = await db.scalar(
        select(func.coalesce(func.sum(BillingDocument.total_amount), 0))
        .where(
            BillingDocument.client_id == client_id,
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status == "issued",
        )
    )
    return result or Decimal("0.00")
```

### ClientCombobox pattern (from UI-SPEC + shadcn conventions)
```typescript
// apps/manager/app/components/ClientCombobox.tsx
// Uses Popover + Command pattern — same as all other comboboxes in the codebase
// Fetches GET /api/v1/clients?limit=200 on popover open
// Displays trading_name primary, NUIT secondary in IBM Plex Mono 11px
// Stores client_id UUID on select
```

---

## Runtime State Inventory

This phase modifies existing tables (`contracts`, `billing_documents`) and introduces new entities. No rename/refactor operations — this section covers the live data migration risk.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `contracts.client_name` in production: unknown count, may have whitespace/case variants | Pre-migration audit query required (STATE.md TODO); review results before writing migration (c) |
| Stored data | `billing_documents.client_name`: populated from contract at billing time; same variant risk | Include in backfill audit — join billing_documents to contracts to backfill via contract.client_id |
| Live service config | None — no external service stores client entity data | No action required |
| OS-registered state | None | No action required |
| Secrets/env vars | `ALEMBIC_DATABASE_URL` must connect as `rotas_admin` (BYPASSRLS) for migration (c) to read RLS-protected tables | Verify in Railway before migration (c) runs; configured in Phase 9 |
| Build artifacts | None | No action required |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | All 4 migrations | Assumed (Railway) | 16 | — |
| `rotas_admin` DB role | Migration (c) backfill | Created in Phase 9 (complete) | — | None — Phase 9 is complete |
| `ALEMBIC_DATABASE_URL` env var | Migration (c) | Must be configured in Railway | — | None — required for RLS bypass |
| shadcn `Command`, `Popover`, `Dialog`, `Alert` | Frontend components | Installed (Phase 3/4.1) | shadcn@2.3.0 | — |
| `Building2` icon | Sidebar nav | In lucide-react 0.468.0 | 0.468.0 | — |
| `apiFetch()` | All frontend pages | `apps/manager/app/lib/api.ts` | Exists | — |

**Missing dependencies with no fallback:**
- `ALEMBIC_DATABASE_URL` configured as `rotas_admin` role in Railway — executor must verify before running migration (c)

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio 0.23 (`asyncio_mode = "auto"`) |
| Config file | `backend/pyproject.toml` |
| Quick run command | `cd backend && python -m pytest tests/test_clients_api.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | Create client with NUIT, trading_name, city, phone; GET returns same data; PATCH deactivates | integration | `pytest tests/test_clients_api.py::test_create_client -x` | ❌ Wave 0 |
| CLI-01 | Duplicate NUIT within same tenant returns HTTP 409 | integration | `pytest tests/test_clients_api.py::test_create_client_duplicate_nuit -x` | ❌ Wave 0 |
| CLI-01 | Cross-tenant isolation: client created in tenant A not visible in tenant B | integration | `pytest tests/test_clients_api.py::test_client_cross_tenant_isolation -x` | ❌ Wave 0 |
| CLI-02 | Client with credit_limit=50000 and outstanding_balance=45000 → warning; >50000 → exceeded | integration | `pytest tests/test_clients_api.py::test_credit_limit_warning_thresholds -x` | ❌ Wave 0 |
| CLI-03 | After migration (c): `SELECT count(*) FROM contracts WHERE client_id IS NULL = 0` | smoke | `pytest tests/test_clients_api.py::test_backfill_zero_null_client_ids -x` | ❌ Wave 0 |
| CLI-04 | POST /contracts with client_id populates client_name from client.trading_name | integration | `pytest tests/test_clients_api.py::test_contract_create_with_client_id -x` | ❌ Wave 0 |
| CLI-05 | Issued billing document has invoice_number in AAAA/NNNN format; second issue increments | integration | `pytest tests/test_fiscal_compliance.py::test_invoice_sequential_number` — ALREADY EXISTS | ✅ |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_clients_api.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green + `SELECT count(*) FROM contracts WHERE client_id IS NULL` = 0 before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_clients_api.py` — covers CLI-01 through CLI-04 (7 test stubs, all `pytest.mark.skip`)
- [ ] `backend/app/modules/clients/__init__.py` — empty init file
- [ ] `backend/app/modules/clients/models.py` — Client model stub
- [ ] CLI-05 already covered by `test_fiscal_compliance.py::test_invoice_sequential_number` — no new stub needed

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Free-text `client_name` on contracts | FK to `clients` table | Phase 5 | Enables client registry, search, credit tracking |
| No `due_date` on `billing_documents` | `due_date` added nullable | Phase 5 | Required for Phase 7 aging buckets from day one |
| `invoice_number` = None until issued | `invoice_number` assigned via PG SEQUENCE at issuance | Phase 15 | Already complete — `AAAA/NNNN` format works |

---

## Open Questions

1. **Pre-migration audit results (data quality)**
   - What we know: `contracts.client_name` is a free-text field with no validation
   - What's unclear: How many distinct `client_name` variants exist in production data; whether there are encoding issues with Mozambican names
   - Recommendation: Executor must run audit query in Wave 0 against the actual production database (or a dump) before writing migration (c). The query is documented in STATE.md TODOs.

2. **outstanding_balance in Phase 5 (before payments)**
   - What we know: Phase 6 creates `client_payments` table; outstanding balance is correctly computed only after Phase 6
   - What's unclear: Whether the Phase 5 interim computation (`SUM(billing_documents.total_amount) WHERE status='issued'`) is acceptable for the credit warning UI or must show MZN 0 until Phase 6 completes
   - Recommendation: Use the interim sum for the credit warning (it overestimates — all issued invoices counted as unpaid); document in API response as `"outstanding_balance_estimate": true` until Phase 6 completes.

3. **client_id NOT NULL enforcement timing**
   - What we know: The gate condition from ROADMAP.md is `count(*) = 0` for NULL client_ids before Phase 6 starts
   - What's unclear: Whether to add an `ALTER TABLE contracts ALTER COLUMN client_id SET NOT NULL` constraint after backfill, or leave nullable forever
   - Recommendation: Leave `client_id` nullable after Phase 5. The gate check is application-level (`count(*) = 0`), not a DB constraint. Adding NOT NULL would break any contract created via legacy path during the migration window. Phase 6 can enforce at the service layer.

---

## Sources

### Primary (HIGH confidence)
- `backend/alembic/versions/d5e6f7a8b9c0_add_notification_outbox.py` — canonical v2.0 RLS+GRANT pattern
- `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` — RLS policy syntax verified
- `backend/alembic/versions/c7d8e9f0a1b2_phase15_fiscal_load_columns.py` — invoice sequence implementation confirmed
- `backend/app/modules/billing/service.py` — `_assign_invoice_number()` implementation confirmed
- `backend/app/modules/billing/models.py` — `invoice_number` column and unique constraint confirmed
- `backend/app/modules/contracts/models.py` — source model for backfill (has `client_name`, lacks `client_id`)
- `backend/app/modules/contracts/schemas.py` — current `ContractCreate` schema (needs `client_id` added)
- `backend/app/modules/contracts/service.py` — service pattern to replicate in `clients/service.py`
- `backend/app/database.py` — MODEL_MODULES registration pattern
- `backend/app/main.py` — router registration pattern
- `.planning/phases/05-client-registry-migration-foundation/05-UI-SPEC.md` — UI contract
- `.planning/STATE.md` — Key Decisions table, Todos list
- `.planning/ROADMAP.md` — Phase 5 architecture constraints
- CLAUDE.md — v2.0 Migration Rules

### Secondary (MEDIUM confidence)
- `backend/tests/conftest.py` — test fixture pattern for new test file
- `backend/tests/test_fiscal_compliance.py` — confirms CLI-05 already has test coverage

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all building blocks verified present
- Architecture: HIGH — 43 prior migrations audited; pattern is unambiguous
- Migration (c) backfill: MEDIUM — exact variant distribution in production data unknown until audit query runs
- CLI-05 completeness: HIGH — code, model, and migration all verified present
- Pitfalls: HIGH — derived from STATE.md Key Decisions (all explicitly documented for Phase 5)

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (stable domain — Python/PostgreSQL patterns do not change)
