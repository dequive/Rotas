# Phase 26: Gestão de Terceiros — Backend Unification - Research

**Researched:** 2026-06-21
**Domain:** SQLAlchemy 2 async + Alembic migration authoring + FastAPI service layer (find-or-create pattern)
**Confidence:** HIGH — all findings verified directly from codebase files

---

## Summary

Phase 26 performs a purely additive backend unification: it bridges the existing `clients` module (2 213 records, all with valid NUITs, zero duplicates, zero overlap with `third_parties`) into the `third_parties` entity graph. The deliverables are four Alembic migrations and one service-layer change — no new endpoints, no frontend work.

The audit from quick task 260621-uvf confirmed the data is clean: 100% NUIT coverage, zero tenant-scoped duplicates, zero cross-table overlap. This means all DDL constraints can be created without a pre-constraint cleanup pass. The backfill is mechanical: 2 213 rows × 4 writes per row (third_party + role + client_profile + clients.third_party_id UPDATE), executed in 5 batches of 500 with individual BEGIN/COMMIT.

The single architectural complexity is the Alembic head situation: the codebase currently has multiple live heads. The new migrations must select one coherent `down_revision` chain and, if necessary, introduce a merge migration to unify the branches before proceeding.

**Primary recommendation:** Four migrations (DDL-A, DDL-B, DML-backfill, service patch) + one service.py rewrite of `create_client`. Constraint `UNIQUE (tenant_id, nuit)` goes on `third_parties` in DDL-A — before the backfill runs.

---

<user_constraints>
## User Constraints (from architectural decisions — treat as locked)

### Locked Decisions

1. `client_profiles` table symmetric to `supplier_profiles`
   - Columns: `id UUID PK`, `tenant_id UUID FK → tenants.id`, `third_party_id UUID FK UNIQUE → third_parties.id`, `payment_terms_days INT DEFAULT 30`, `credit_limit NUMERIC(14,2)`, `preferred_currency VARCHAR(3) DEFAULT 'MZN'`, `billing_email VARCHAR(200)`, `created_at`, `updated_at`
   - Same RLS + GRANT pattern as all other v2.0 tables

2. `clients.third_party_id UUID NULLABLE` FK → `third_parties.id`
   - Nullable during migration window; populated by backfill
   - NOT a hard FK migration (nullable to avoid locking)

3. `UNIQUE (tenant_id, nuit)` constraint on `third_parties`
   - Audit confirmed 0 duplicates — safe to add directly
   - Must be added BEFORE the backfill migration runs

4. Backfill: 2 213 client records → create third_party + third_party_role(client) + client_profile per client
   - Batches of 500 with individual BEGIN/COMMIT
   - role_type value: 'client'

5. POST /api/v1/clients → find-or-create against third_parties by (tenant_id, nuit)
   - If third_party exists with same NUIT → reuse third_party_id, create client_profile if missing
   - If not → create third_party + role + client_profile atomically, then create client

6. Risk classification: MÉDIO

7. NO API endpoint changes in this phase
8. NO frontend changes in this phase
9. Alembic migration chain must connect to current Alembic head
10. `contract_direction` field is NOT part of this phase

### Claude's Discretion

- Migration revision ID strings (must be fresh, not collide with existing 80+ migrations)
- Whether to introduce a merge migration to unify multi-head state before these migrations
- Exact transaction boundary approach for the backfill (raw SQL via `op.execute` vs Python loop)
- Order of operations within the service layer find-or-create

### Deferred Ideas (OUT OF SCOPE)

- API endpoint aliases or new /terceiros/* endpoints (Phase 27)
- Frontend changes (Phase 27+)
- `contract_direction` field (Phase G / contracts expansion)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GT-01 | `client_profiles` table with RLS + GRANT in same migration | supplier_profiles model is the template; ins01 migration shows exact RLS pattern |
| GT-02 | `clients.third_party_id UUID NULLABLE` FK column | ALTER TABLE via `op.add_column` with nullable=True; no locking risk |
| GT-03 | `UNIQUE (tenant_id, nuit)` on `third_parties` | ThirdParty model already has the constraint defined in ORM (uq_third_parties_tenant_nuit) but it was NOT created in tp01b migration — must verify; audit confirms 0 conflicts |
| GT-04 | Backfill 2 213 client records in batches of 500 | DML migration with raw SQL loop; `op.get_bind()` pattern confirmed from existing migrations |
| GT-05 | POST /clients → find-or-create against third_parties by (tenant_id, nuit) | Current `create_client` in service.py is a simple INSERT; needs full rewrite |
</phase_requirements>

---

## Standard Stack

### Core (verified from codebase)

| Component | Version/Pattern | Purpose |
|-----------|----------------|---------|
| `alembic` | >=1.13 (existing) | Migration authoring |
| `sqlalchemy[asyncio]` | >=2.0 (existing) | ORM models + async queries |
| `asyncpg` | >=0.29 (existing) | PostgreSQL driver |
| `op.execute(text(...))` | Alembic built-in | Raw SQL for backfill DML |
| `op.add_column` | Alembic built-in | Add nullable FK column to clients |
| `op.create_table` | Alembic built-in | Create client_profiles |
| `op.create_unique_constraint` | Alembic built-in | Add UNIQUE (tenant_id, nuit) to third_parties |

**No new packages required.** All dependencies already installed.

---

## Architecture Patterns

### Verified RLS + GRANT Pattern (from ins01_add_vehicle_insurance.py — most recent table creation)

```python
# Source: backend/alembic/versions/ins01_add_vehicle_insurance.py
op.execute("ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
op.execute(
    "CREATE POLICY rls_{table} ON {table} "
    "USING (tenant_id::text = current_setting('app.tenant_id', true))"
)
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app")
```

Policy name convention: `rls_{table_name}` (confirmed from ins01 and gap01 migrations).

### client_profiles — Template from supplier_profiles (backend/app/modules/third_party/models.py)

The existing `SupplierProfile` model (lines 109-141) is the direct template. Key differences for `client_profiles`:

```python
class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False)
    third_party_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("third_parties.id", ondelete="CASCADE"), unique=True, nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30")
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    preferred_currency: Mapped[str | None] = mapped_column(String(3), nullable=True, server_default="MZN")
    billing_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

Note: `SupplierProfile.credit_limit` uses `float | None` annotation on `Numeric(14,2)` — this is a known codebase convention gap. For `ClientProfile`, use `Decimal | None` (consistent with `Client.credit_limit` which correctly uses `Mapped[Decimal | None]`).

### third_party_roles.role_type — No Enum, Plain String

Confirmed in `models.py` line 98: `role_type: Mapped[str] = mapped_column(String(40), nullable=False)`. Comment on line 99 lists current valid values as `fuel_supplier | spare_parts_supplier | service_provider | transport_subcontractor`. The value `'client'` is NOT listed but the column is an unconstrained String — no DDL change required to insert `role_type = 'client'`. This is a code-only addition.

### UNIQUE (tenant_id, nuit) on third_parties — Status Check Required

The ORM model `ThirdParty.__table_args__` (line 36) already declares:
```python
UniqueConstraint("tenant_id", "nuit", name="uq_third_parties_tenant_nuit")
```

However, migration `tp01b_add_third_party_tables.py` must be checked to see if this constraint was actually applied. The migration creates the table but the `__table_args__` on the ORM model does not guarantee the migration includes it. **The planner must verify by reading tp01b in full.** If absent from the migration, GT-03 adds it via `op.create_unique_constraint`.

Verification approach:
```python
# In the migration that adds it:
op.create_unique_constraint(
    "uq_third_parties_tenant_nuit",
    "third_parties",
    ["tenant_id", "nuit"]
)
```

### Backfill Pattern — Batched Raw SQL

The existing codebase uses `op.get_bind()` for DML migrations. Pattern from `f6a7b8c9d0e1_backfill_client_ids.py` (present in versions directory). Backfill approach for Phase 26:

```python
# In upgrade():
bind = op.get_bind()

# Step 1: fetch all clients without third_party_id (in batches)
offset = 0
batch_size = 500
while True:
    rows = bind.execute(text(
        "SELECT id, tenant_id, trading_name, legal_name, nuit, email, payment_terms_days, credit_limit "
        "FROM clients ORDER BY id LIMIT :limit OFFSET :offset"
    ), {"limit": batch_size, "offset": offset}).fetchall()
    if not rows:
        break
    for row in rows:
        # INSERT third_party
        tp_id = bind.execute(text("""
            INSERT INTO third_parties (id, tenant_id, name, nuit, status, created_at, updated_at)
            VALUES (gen_random_uuid(), :tenant_id, :name, :nuit, 'active', now(), now())
            RETURNING id
        """), {"tenant_id": row.tenant_id, "name": row.trading_name, "nuit": row.nuit}).scalar()
        # INSERT third_party_role
        bind.execute(text("""
            INSERT INTO third_party_roles (id, tenant_id, third_party_id, role_type, is_active, created_at)
            VALUES (gen_random_uuid(), :tenant_id, :tp_id, 'client', true, now())
        """), {"tenant_id": row.tenant_id, "tp_id": tp_id})
        # INSERT client_profile
        bind.execute(text("""
            INSERT INTO client_profiles (id, tenant_id, third_party_id, payment_terms_days, credit_limit, preferred_currency, created_at, updated_at)
            VALUES (gen_random_uuid(), :tenant_id, :tp_id, :pt, :cl, 'MZN', now(), now())
        """), {"tenant_id": row.tenant_id, "tp_id": tp_id, "pt": row.payment_terms_days, "cl": row.credit_limit})
        # UPDATE clients.third_party_id
        bind.execute(text(
            "UPDATE clients SET third_party_id = :tp_id WHERE id = :client_id"
        ), {"tp_id": tp_id, "client_id": row.id})
    offset += batch_size
```

Note: Alembic DML migrations run in the Alembic transaction context. "Batches of 500 with individual BEGIN/COMMIT" means the DML migration should use `connection.commit()` after each batch to reduce lock hold time. Use `op.get_bind()` then `connection = bind` for raw execution.

### find-or-create Pattern for create_client (service.py rewrite)

Current `create_client` (lines 103-116) is a simple INSERT. The rewrite must:

1. Try `SELECT id FROM third_parties WHERE tenant_id=:t AND nuit=:n`
2. If found: `third_party_id = existing.id`; check if `client_profiles` row exists for that `third_party_id`; if not, INSERT client_profile
3. If not found: INSERT third_party + role + client_profile atomically inside the same `db` session (before flush)
4. INSERT client with `third_party_id` populated
5. On `IntegrityError` from UNIQUE (tenant_id, nuit) on either `third_parties` or `clients`: re-raise as `ApiError("nuit_already_exists", ..., 409)` (existing error code, keep for backward compat)

The session pattern is async (`AsyncSession`), so use `await db.execute(select(...).where(...))` for the lookup.

### Migration Chain — Current Alembic Heads

Verified by tracing all `down_revision` references in the 80+ migration files. Current heads (revisions with no successor):

| Head | File |
|------|------|
| `adv01` | adv01_add_driver_advances_and_settlements.py |
| `9a3cc9a059814` | 9a3cc9a059814_add_is_international_to_trips.py |
| `a2b3c4d5e6f7` | a2b3c4d5e6f7_add_clients_table.py |
| `b9c8d7e6f5a4` | b9c8d7e6f5a4_sm03_sm04_states.py |
| `e1a2b3c4d5f6` | e1a2b3c4d5f6_add_platform_users_and_audit_logs.py |
| `tp03` | tp03_add_third_party_fks.py |
| `tp05` | tp05_add_driver_vehicle_assignments.py |
| `tp06` | tp06_add_operational_documents.py |
| `tp09` | tp09_add_supplier_evaluations.py |

Note: `tp09` is NOT the final tp chain head. The chain goes: tp09 → tp10 → tp11 → ins01 → e66352d728cd (merge) → b8a041cfa791 (merge) → fisc01 → iva01a1b2c3d4 → **adv01** (head).

The tp03, tp05, tp06 branches are separate parallel branches (not merged into the main chain). This is the codebase's existing multi-head state.

**For Phase 26 migrations:** The Phase 26 DDL-A migration should use `down_revision = "adv01"` as its base (the most recent single-line head that includes the full tp, ins01, fisc01, iva01 chain). The planner must decide whether to introduce a merge migration first to unify all orphan heads (tp03, tp05, tp06, 9a3cc9a059814, a2b3c4d5e6f7, b9c8d7e6f5a4, e1a2b3c4d5f6) or simply chain off `adv01` and leave the other branches as parallel (acceptable if alembic is configured to allow multiple heads).

**Recommended approach:** Chain off `adv01` without a merge. The other orphan heads are from older feature branches and don't conflict with the Phase 26 DDL. A merge migration can be a separate plan if desired.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| UNIQUE constraint enforcement | Application-level nuit dedup check | DB-level `UNIQUE (tenant_id, nuit)` constraint | Concurrent writes would race past any app-level check |
| Batch commit | Python `asyncio` chunking | Alembic sync `op.get_bind()` + `connection.commit()` | DML migrations run in sync context via `psycopg[binary]`; asyncio not available in migration context |
| find-or-create race condition | SELECT then INSERT | Let IntegrityError on INSERT be the guard; re-SELECT on conflict | PostgreSQL UNIQUE constraint is the atomic guard; SELECT-then-INSERT has a TOCTOU gap |

---

## Common Pitfalls

### Pitfall 1: UNIQUE Constraint on third_parties May Already Exist in DB

**What goes wrong:** tp01b migration created `third_parties` table. ORM model declares `uq_third_parties_tenant_nuit`. If the migration included `op.create_unique_constraint(...)` then GT-03's migration will fail with "constraint already exists".

**How to avoid:** Read tp01b in full before writing GT-03 migration. If the constraint was created in tp01b, GT-03 is a no-op DDL migration (empty upgrade) or can be skipped entirely. The planner must check.

**Investigation command:**
```sql
SELECT conname FROM pg_constraint
WHERE conname = 'uq_third_parties_tenant_nuit';
```
Or read `tp01b_add_third_party_tables.py` lines 80+ to see if `UniqueConstraint` was declared in `op.create_table`.

### Pitfall 2: RLS Blocks Backfill Migration

**What goes wrong:** The backfill DML migration runs under `ALEMBIC_DATABASE_URL` (rotas_admin role, BYPASSRLS). If the migration accidentally uses `DATABASE_URL` (rotas_app with RLS), the backfill will insert rows but `client_profiles` and `third_party_roles` won't be visible to subsequent reads within the same session (RLS filters by `app.tenant_id` which is not set in migrations).

**How to avoid:** Confirm ALEMBIC_DATABASE_URL uses the `rotas_admin` role. This is the established pattern from Phase 9. The backfill migration uses raw `op.get_bind()` which inherits the Alembic connection — as long as Alembic is invoked with the admin URL, this is safe.

### Pitfall 3: Backfill Partial Failure Leaves Inconsistent State

**What goes wrong:** If the backfill batch fails mid-row (e.g., after INSERT third_party but before UPDATE clients.third_party_id), the `third_party` record exists but `clients.third_party_id` is still NULL. Rerunning the migration would try to create a duplicate `third_party` for the same NUIT, hitting the UNIQUE constraint.

**How to avoid:** The backfill migration must be written as idempotent. Pattern:
```sql
-- Only insert third_party if clients.third_party_id is still NULL for this client
WHERE clients.third_party_id IS NULL

-- On third_party insert, use ON CONFLICT DO NOTHING and retrieve existing id:
INSERT INTO third_parties (...) VALUES (...) ON CONFLICT (tenant_id, nuit) DO NOTHING;
SELECT id FROM third_parties WHERE tenant_id=:t AND nuit=:n;
```
This way rerunning the migration skips already-migrated rows.

### Pitfall 4: client_profiles.credit_limit Type Annotation

**What goes wrong:** `SupplierProfile.credit_limit` uses `float | None` annotation (line 130 of third_party/models.py) despite the column being `Numeric(14,2)`. Copying this directly for `ClientProfile` perpetuates the incorrect type annotation.

**How to avoid:** Use `Decimal | None` annotation (matching `Client.credit_limit` at line 40 of clients/models.py). The database column is `Numeric(14,2)` in both cases.

### Pitfall 5: find-or-create Race Condition in service.py

**What goes wrong:** Two concurrent POST /clients requests with the same (tenant_id, nuit) both pass the "third_party not found" SELECT check, then both try to INSERT into third_parties — the second one hits the UNIQUE constraint.

**How to avoid:** Catch `IntegrityError` on the third_party INSERT in the find-or-create flow and re-SELECT to get the existing record. This is the standard "upsert" pattern:
```python
try:
    await db.flush()  # flush the third_party insert
except IntegrityError:
    await db.rollback()
    # re-select the existing third_party
    result = await db.execute(select(ThirdParty).where(...))
    third_party = result.scalar_one()
```

### Pitfall 6: Migration Chain Breaks Existing Alembic Multi-Head State

**What goes wrong:** If the Phase 26 migration uses `down_revision = "adv01"`, `alembic upgrade head` will succeed only if the DB is already at `adv01`. If the DB is at a different head (e.g., tp03), the command applies tp03 migrations independently. Multi-head state is not necessarily a problem but must be intentional.

**How to avoid:** The planner should document that Phase 26 migrations chain off `adv01` specifically. Deployment instructions for this phase should include verifying `alembic current` shows `adv01` in the applied set before running `alembic upgrade gt01` (or whatever the Phase 26 head is named).

---

## Code Examples

### Current create_client (service.py lines 103-116)

```python
# Source: backend/app/modules/clients/service.py
async def create_client(db: AsyncSession, tenant_id: UUID, payload: ClientCreate) -> dict:
    client = Client(tenant_id=tenant_id, **payload.model_dump())
    db.add(client)
    try:
        await db.flush()
    except IntegrityError as exc:
        raise ApiError(
            "nuit_already_exists",
            "NUIT já existe neste tenant.",
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    await db.commit()
    await db.refresh(client)
    return serialize_client(client)
```

This is what GT-05 must rewrite.

### RLS Pattern (exact, from ins01_add_vehicle_insurance.py)

```python
# Source: backend/alembic/versions/ins01_add_vehicle_insurance.py
op.execute("ALTER TABLE vehicle_insurances ENABLE ROW LEVEL SECURITY")
op.execute("ALTER TABLE vehicle_insurances FORCE ROW LEVEL SECURITY")
op.execute(
    "CREATE POLICY rls_vehicle_insurances ON vehicle_insurances "
    "USING (tenant_id::text = current_setting('app.tenant_id', true))"
)
op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON vehicle_insurances TO rotas_app")
```

Apply same pattern for `client_profiles` in GT-01 migration.

### SupplierProfile model structure (template for ClientProfile)

```python
# Source: backend/app/modules/third_party/models.py lines 109-141
class SupplierProfile(Base):
    __tablename__ = "supplier_profiles"
    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("tenants.id"), index=True, nullable=False)
    third_party_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("third_parties.id", ondelete="CASCADE"), unique=True, nullable=False)
    payment_terms: Mapped[str | None] = mapped_column(String(60), nullable=True)
    preferred_currency: Mapped[str | None] = mapped_column(String(3), nullable=True, server_default="MZN")
    credit_limit: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)  # NOTE: use Decimal for ClientProfile
    ...
```

### ThirdParty model (with existing constraint)

```python
# Source: backend/app/modules/third_party/models.py lines 34-75
class ThirdParty(Base):
    __tablename__ = "third_parties"
    __table_args__ = (UniqueConstraint("tenant_id", "nuit", name="uq_third_parties_tenant_nuit"),)
    # nuit is Mapped[str | None] — nullable in ThirdParty but NOT NULL in clients
    nuit: Mapped[str | None] = mapped_column(String(9), nullable=True)
```

Important: `ThirdParty.nuit` is nullable (String(9), nullable=True) while `Client.nuit` is NOT NULL. When creating a ThirdParty from a Client row, the nuit value from clients is guaranteed non-null (audit: 0 null NUITs).

### ThirdPartyRole — role_type is unconstrained String(40)

```python
# Source: backend/app/modules/third_party/models.py lines 78-106
class ThirdPartyRole(Base):
    __tablename__ = "third_party_roles"
    __table_args__ = (
        UniqueConstraint("third_party_id", "role_type", name="uq_third_party_roles_tp_role"),
    )
    role_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # Valid role_type values: fuel_supplier | spare_parts_supplier | service_provider
    # | transport_subcontractor
    # 'client' is NOT listed but column is unconstrained — no DDL change needed
```

---

## Migration Plan Summary

The planner should structure Phase 26 as 4 migrations in a linear chain:

| Migration # | Revision ID (suggested) | down_revision | Content |
|-------------|------------------------|---------------|---------|
| gt01_ddl_a | `gt01` | `adv01` | CREATE TABLE client_profiles (+ RLS + GRANT); ADD COLUMN clients.third_party_id NULLABLE; ADD UNIQUE (tenant_id,nuit) on third_parties IF NOT EXISTS |
| gt02_backfill | `gt02` | `gt01` | DML backfill: 2213 clients → third_party + role + profile + clients.third_party_id; idempotent via ON CONFLICT DO NOTHING |
| (service patch) | — | — | No migration; pure service.py code change |

Alternative: split DDL-A into two migrations (gt01 = client_profiles + RLS; gt02 = clients column + constraint) to keep each migration focused. This codebase has a pattern of separating concerns across migrations (see Phase 5 decision: "DDL and DML never in same file").

**Minimum viable plan: 3 migrations** (DDL-A, DDL-B for constraint if needed, DML backfill) + 1 service.py change.

---

## Environment Availability

Step 2.6: Confirmed no new external tools required. All dependencies (PostgreSQL 16, asyncpg, SQLAlchemy 2, Alembic) are already installed and running. The PostgreSQL instance at `localhost:55432` was used by the Phase 0 audit and is confirmed reachable.

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|---------|
| PostgreSQL 16 | Migrations + backfill | Yes | 16 (port 55432) | — |
| Alembic | Migration chain | Yes | >=1.13 | — |
| asyncpg | Service layer | Yes | >=0.29 | — |
| psycopg[binary] | Alembic sync context | Yes | >=3.1 | — |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio 0.23 |
| Config file | backend/pyproject.toml (`asyncio_mode = "auto"`) |
| Quick run command | `pytest backend/tests/test_clients.py -x -q` |
| Full suite command | `pytest backend/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GT-01 | client_profiles table created with correct schema + RLS | Integration (migration verify) | `pytest backend/tests/test_third_party_unification.py::test_client_profiles_table_exists -x` | Wave 0 |
| GT-02 | clients.third_party_id column nullable, FK to third_parties | Integration | `pytest backend/tests/test_third_party_unification.py::test_clients_third_party_fk -x` | Wave 0 |
| GT-03 | UNIQUE (tenant_id, nuit) on third_parties blocks duplicate | Integration | `pytest backend/tests/test_third_party_unification.py::test_third_parties_nuit_unique -x` | Wave 0 |
| GT-04 | Backfill: all clients have third_party_id populated | Integration | `pytest backend/tests/test_third_party_unification.py::test_backfill_all_clients_have_tp -x` | Wave 0 |
| GT-05 | POST /clients find-or-create: reuses existing third_party by NUIT | Integration | `pytest backend/tests/test_third_party_unification.py::test_create_client_find_or_create -x` | Wave 0 |
| GT-05 | POST /clients find-or-create: cross-tenant isolation (same NUIT different tenant → two third_parties) | Integration | `pytest backend/tests/test_third_party_unification.py::test_create_client_cross_tenant_isolation -x` | Wave 0 |

### Wave 0 Gaps

- [ ] `backend/tests/test_third_party_unification.py` — new test file covering GT-01 through GT-05
- [ ] Fixtures: two test tenants, seed clients with NUITs, test `ThirdParty` + `ClientProfile` models

*(Existing `backend/tests/test_clients.py` may already exist — planner should check before creating duplicate)*

---

## Open Questions

1. **Does the UNIQUE constraint already exist on third_parties in the database?**
   - What we know: ORM model declares `UniqueConstraint("tenant_id", "nuit", ...)`. Migration tp01b creates the table.
   - What's unclear: Whether tp01b included the `UniqueConstraint` in `op.create_table` args. The partial read of tp01b (80 lines) did not reach the table args section.
   - Recommendation: Planner must read tp01b in full (lines 80+) before writing GT-03 migration. If constraint already exists, GT-03 skips it or uses `IF NOT EXISTS` pattern.

2. **Multi-head strategy for Phase 26 migrations**
   - What we know: There are 9 current heads. `adv01` is the main chain head. tp03/tp05/tp06/others are orphan branches.
   - What's unclear: Whether deployment tooling (`alembic upgrade head`) handles multi-head gracefully or requires `--allow-multiple-heads`.
   - Recommendation: Chain Phase 26 off `adv01` only. Document in plan that `alembic upgrade gt02` (naming the final Phase 26 head explicitly) is safer than `alembic upgrade head` in multi-head environments.

3. **Whether `test_clients.py` already exists**
   - What we know: Phase 5 created a clients module. Tests were written.
   - What's unclear: Exact filename — could be `test_clients.py` or `test_clients_module.py`.
   - Recommendation: Planner reads `backend/tests/` directory listing before naming the Wave 0 gap file.

---

## Sources

### Primary (HIGH confidence — read directly from codebase)

- `backend/app/modules/third_party/models.py` — ThirdParty, ThirdPartyRole, SupplierProfile, ServiceProviderProfile model definitions
- `backend/app/modules/clients/models.py` — Client model definition; confirms nuit is NOT NULL, third_party_id not yet present
- `backend/app/modules/clients/service.py` — current create_client implementation (lines 103-116); full service layer
- `backend/alembic/versions/ins01_add_vehicle_insurance.py` — canonical RLS + GRANT pattern (most recent table creation)
- `backend/alembic/versions/tp01b_add_third_party_tables.py` — third_parties table creation (partial read, lines 1-80)
- `.planning/quick/260621-uvf-fase-0-auditoria-dados-clients-third-par/260621-uvf-REPORT.md` — data audit results confirming 2213 clients, 0 null NUITs, 0 duplicates, 0 overlap
- `.planning/REQUIREMENTS.md` — GT-01 through GT-05 requirement definitions
- Alembic version directory listing — confirmed 80+ migration files; identified adv01 as primary chain head

### Secondary (MEDIUM confidence)

- Multi-head analysis via Python script — traced down_revision chains across all migrations; identified 9 heads including adv01 as the main chain terminus

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing
- Architecture patterns: HIGH — RLS pattern read directly from ins01; service.py read in full
- Migration chain: HIGH — traced programmatically from all migration files
- Backfill batch approach: HIGH — confirmed from existing f6a7b8c9d0e1_backfill_client_ids.py precedent in versions dir
- Pitfalls: HIGH — based on direct codebase reading + Phase 9 RLS established patterns

**Research date:** 2026-06-21
**Valid until:** 2026-07-21 (stable codebase; migration chain only changes if new migrations are added)
