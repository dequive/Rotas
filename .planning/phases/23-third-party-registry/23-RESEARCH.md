# Phase 23: Third Party Registry — Research

**Researched:** 2026-06-19
**Domain:** FastAPI service/router/model patterns, PostgreSQL RLS migrations, alert integration, files module FK pattern
**Confidence:** HIGH — all findings derived directly from codebase inspection, no external sources required

---

## Summary

Phase 23 adds a third-party registry module (`backend/app/modules/third_party/`) to ROTAS. All design decisions are settled in CONTEXT.md. This research documents the exact patterns to replicate from existing modules so the planner can produce tasks with zero ambiguity.

The codebase is highly consistent. Every module follows the same service/router/schemas triad with a `serialize_*`, `_require_*`, and `record_audit_log` inside the same DB transaction. The migration pattern is identical across all post-v2.0 tables: RLS + GRANT in the same `CREATE TABLE` block. The alert module exposes a synchronous `create_alert()` that accepts a typed `AlertCreate` schema — document-expiry alert generation calls it directly from a service function.

**Primary recommendation:** Copy the clients module structure wholesale. It is the most recent clean example of a tenant-owned table with proper RLS, no legacy debt, and a clear NUIT uniqueness pattern that parallels the NUIT field on `third_parties`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
1. `third_parties` table — identity registry (name, trade_name, legal_type, nuit, contact_email, contact_phone, province_code, address, status, is_verified)
2. `third_party_roles` table — roles per third party (role_type enum: fuel_supplier|spare_parts_supplier|service_provider|transport_subcontractor, is_active, certified_at, certification_ref)
3. `supplier_profiles` table — extended supplier data (payment_terms, preferred_currency, credit_limit, account_number, bank_name)
4. `service_provider_profiles` table — extended service provider data (service_categories: JSON array, coverage_province_codes: JSON array, response_time_hours, rate_per_hour)
5. `mz_provinces` static reference table — 11 Mozambique provinces, NO tenant_id, NO RLS
6. Additive nullable FKs: `fuel_purchases.supplier_third_party_id`, `spare_parts_inventory.supplier_third_party_id`, `work_orders.service_provider_third_party_id`
7. `OperationalEligibilityService` — reads existing Driver fields (`license_valid_until`, `passport_valid_until`, `bi_valid_until`, `status`), no new Driver columns
8. `driver_vehicle_assignments` temporal table — (tenant_id, driver_id→drivers.id, vehicle_id→vehicles.id, assigned_at, unassigned_at, assignment_type, assigned_by→users.id)
9. `operational_documents` table — PartyRef pattern: (subject_type VARCHAR(30), subject_id UUID, document_type, file_id→files.id, expiry_date, verification_status, verified_by→users.id)
10. `PartyDirectoryService` — single UNION ALL query across drivers/clients/third_parties, NOT three API calls
11. Alert integration uses existing `alerts` module and Alert model

### Claude's Discretion
Not specified in CONTEXT.md — all major decisions are locked.

### Deferred Ideas (OUT OF SCOPE)
- Modifying `drivers` table columns
- Modifying `clients` table
- Modifying `trips.driver_id` or `trips.vehicle_id`
- `sync_changes` / `sync_conflicts` tables
- `clients → third_parties` bridge (Phase G)
- Province/district column on drivers
- Seeding `mz_provinces` via Alembic data migration
</user_constraints>

---

## 1. Service Layer Pattern

Source: `backend/app/modules/drivers/service.py` and `backend/app/modules/clients/` (direct inspection)

### Core idioms — replicate exactly

**serialize_ function** — plain dict, never raw ORM:
```python
def serialize_third_party(tp: ThirdParty) -> dict:
    return {
        "id": tp.id,
        "tenant_id": tp.tenant_id,
        "name": tp.name,
        # ... all fields
        "created_at": tp.created_at,
        "updated_at": tp.updated_at,
    }
```

**_require_ guard** — tenant isolation enforced in every read:
```python
async def _require_third_party(db: AsyncSession, tenant_id: UUID, tp_id: UUID) -> ThirdParty:
    tp = await db.get(ThirdParty, tp_id)
    if not tp or tp.tenant_id != tenant_id:
        raise ApiError("third_party_not_found", "Third party not found.", status_code=404)
    return tp
```

**Create pattern** — flush before audit log, commit after, refresh before return:
```python
async def create_third_party(
    db: AsyncSession,
    tenant_id: UUID,
    payload: ThirdPartyCreate,
    *,
    actor_id: UUID | None = None,
) -> dict:
    tp = ThirdParty(tenant_id=tenant_id, **payload.model_dump())
    db.add(tp)
    await db.flush()          # generates id, triggers DB constraints
    await db.refresh(tp)      # ensures id is populated
    await record_audit_log(
        db,
        tenant_id=tenant_id,
        user_id=actor_id,
        action="third_party.created",
        entity_type="third_party",
        entity_id=tp.id,
        new_values=serialize_third_party(tp),
    )
    await db.commit()         # audit log in same transaction
    await db.refresh(tp)
    return serialize_third_party(tp)
```

**Patch pattern** — capture old_values before mutation, record both:
```python
old_values = serialize_third_party(tp)
# apply mutations
await db.flush()
await db.refresh(tp)
await record_audit_log(
    db, ..., action="third_party.updated",
    old_values=old_values, new_values=serialize_third_party(tp),
)
await db.commit()
await db.refresh(tp)
```

**record_audit_log signature** (from `backend/app/modules/audit/service.py`):
```python
await record_audit_log(
    db,
    tenant_id=tenant_id,
    user_id=actor_id,           # UUID | None
    action="third_party.created",
    entity_type="third_party",
    entity_id=tp.id,
    old_values=None,            # dict | None
    new_values=serialize_third_party(tp),  # dict | None
)
```
Note: `record_audit_log` does NOT call `db.add()` internally — it creates an `AuditLog` and calls `db.add(audit_log)` inside itself. It does NOT commit. The caller commits.

**Uniqueness check pattern** (like `_phone_exists` for drivers, `uq_clients_tenant_nuit` for clients):
```python
async def _nuit_exists(
    db: AsyncSession, tenant_id: UUID, nuit: str, *, exclude_id: UUID | None = None
) -> bool:
    query = select(ThirdParty.id).where(
        ThirdParty.tenant_id == tenant_id, ThirdParty.nuit == nuit
    )
    if exclude_id:
        query = query.where(ThirdParty.id != exclude_id)
    return await db.scalar(query) is not None
```

**List pattern** — always filter by tenant_id first, then optional filters, then order + limit + offset:
```python
query = select(ThirdParty).where(ThirdParty.tenant_id == tenant_id)
if status_filter:
    query = query.where(ThirdParty.status == status_filter)
result = await db.execute(query.order_by(ThirdParty.name.asc()).limit(limit).offset(offset))
return [serialize_third_party(tp) for tp in result.scalars()]
```

**Imports** — every service uses:
```python
from app.core.errors import ApiError
from app.modules.audit.service import record_audit_log
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
```

---

## 2. Alert Generation Pattern

Source: `backend/app/modules/alerts/service.py`, `backend/app/modules/alerts/models.py`, `backend/app/modules/alerts/schemas.py`

### How to call alert creation

`create_alert()` is a plain async service function. Call it from within a document-expiry check function passing the same `db` session:

```python
from app.modules.alerts.schemas import AlertCreate
from app.modules.alerts.service import create_alert

async def generate_document_expiry_alerts(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[dict]:
    # ... query operational_documents with expiry_date approaching
    for doc in expiring_docs:
        days_remaining = (doc.expiry_date - date.today()).days
        priority = "critical" if days_remaining <= 7 else "high"
        alert_type = "document_expired" if days_remaining <= 0 else "document_expiring_soon"
        payload = AlertCreate(
            request_reference=f"doc_expiry:{doc.id}:{doc.expiry_date.isoformat()}",
            alert_type=alert_type,
            priority=priority,
            entity_type=doc.subject_type,   # 'driver' | 'third_party' | 'vehicle'
            entity_id=doc.subject_id,
            title=f"Document expiring: {doc.document_type}",
            message=f"Document {doc.document_type} expires in {days_remaining} days.",
            channel="dashboard",
        )
        await create_alert(db, tenant_id, payload)
```

### Key Alert model fields (from `backend/app/modules/alerts/models.py`)
- `request_reference: String(120)` — **unique per tenant** (`uq_alerts_tenant_request_reference`). Use a deterministic key like `f"doc_expiry:{doc_id}:{expiry_date}"` to make alert generation idempotent (duplicate call returns existing alert, doesn't 409 unless fields changed).
- `alert_type: String(60)` — free-text, no DB enum. Use: `document_expiring_soon`, `document_expired`
- `priority: String(20)` — validated against set `{"low", "medium", "high", "critical"}` inside `create_alert()`
- `entity_type: String(80)` — `"driver"`, `"third_party"`, `"vehicle"`, etc.
- `entity_id: UUID | None` — the specific entity UUID
- `channel: String(30)` — validated against `{"dashboard", "whatsapp", "email", "sms"}`, default `"dashboard"`
- `status: String(30)` — auto-set to `"pending"` on creation

### Idempotency in create_alert
`create_alert()` already handles duplicate `request_reference`:
- Same key + same payload values → returns existing alert silently
- Same key + different values → raises 409 `alert_request_reference_reused`

So document expiry check functions can be run repeatedly (e.g., from a scheduled ARQ job) without creating duplicate alerts, as long as the `request_reference` is deterministic.

### No new alert tables needed
Alert generation for Phase 23 requires zero schema changes to the alerts module.

---

## 3. Migration RLS Boilerplate

Source: `backend/alembic/versions/a2b3c4d5e6f7_add_clients_table.py` (canonical reference)

### Exact boilerplate for every tenant-owned table

```python
def upgrade() -> None:
    op.create_table(
        "{table_name}",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        # ... other columns ...
    )
    op.create_index("ix_{table}_tenant_id", "{table_name}", ["tenant_id"])

    # v2.0 Migration Rules — RLS + GRANT in same CREATE TABLE migration (MANDATORY)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO rotas_app")
    op.execute("ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON {table_name}
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON {table_name}")
    op.drop_index("ix_{table}_tenant_id", table_name="{table_name}")
    op.drop_table("{table_name}")
```

**Policy name convention:** `tenant_isolation` (not `rls_{table}` — the clients migration uses `tenant_isolation`; use that consistently).

### Tables needing RLS in Phase 23
All six tenant-scoped tables: `third_parties`, `third_party_roles`, `supplier_profiles`, `service_provider_profiles`, `driver_vehicle_assignments`, `operational_documents`.

### mz_provinces (NO RLS, platform-level)
```python
op.execute("GRANT SELECT ON mz_provinces TO rotas_app")
# NO RLS — no tenant_id column
```

### Downgrade for nullable FK additions
For the three nullable FK additions (`fuel_purchases`, `spare_parts_inventory`, `work_orders`):
```python
def upgrade() -> None:
    op.add_column("fuel_purchases", sa.Column(
        "supplier_third_party_id", UUID(as_uuid=True),
        sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
        nullable=True,
    ))

def downgrade() -> None:
    op.drop_column("fuel_purchases", "supplier_third_party_id")
```

---

## 4. Router Registration

Source: `backend/app/main.py` (lines 25-50 import block, lines 250-276 include_router block), `backend/app/database.py` (lines 95-118 MODEL_MODULES)

### main.py — add one import and one include_router

**Import to add** (after existing module imports, alphabetical by module name — between `tenants` and `trip_orders`):
```python
from app.modules.third_party.router import router as third_party_router
```

**include_router to add** (after `workshop_router`, before `control_tower_router`):
```python
app.include_router(third_party_router, prefix=api)
```

The full registration block currently ends at line 276 with `analytics_router`. Suggested placement between `workshop_router` (line 271) and `control_tower_router` (line 272).

### database.py — add to MODEL_MODULES tuple

Add `"third_party"` to the `MODEL_MODULES` tuple (lines 95-118). Insert alphabetically between `"tenants"` and `"trips"`:
```python
MODEL_MODULES = (
    "auth",
    "tenants",
    "third_party",   # ADD HERE
    "contracts",
    # ...
)
```

Current MODEL_MODULES list (for reference):
```
"auth", "tenants", "contracts", "clients", "users", "drivers", "vehicles",
"files", "checklists", "fuel", "trip_orders", "trips", "cargo", "billing",
"operations", "operational_exceptions", "workshop", "control_tower",
"alerts", "notifications", "sync", "audit"
```

Note: `"analytics"` and `"availability"` are registered as routers in `main.py` but are NOT in `MODEL_MODULES` — presumably they have no ORM models. The `third_party` module will have models, so it MUST be in `MODEL_MODULES`.

---

## 5. Files Module Reference

Source: `backend/app/modules/files/models.py`, `backend/app/modules/files/service.py`, `backend/app/modules/files/router.py`

### File model key fields
```python
class File(Base):
    __tablename__ = "files"
    id: UUID                        # primary key
    tenant_id: UUID                 # FK to tenants.id (RLS enforced)
    entity_type: str | None         # e.g. "driver_document", "operational_document"
    entity_id: UUID | None          # set to the subject's id after upload
    file_type: str                  # e.g. "pdf", "image_jpeg"
    original_name: str
    storage_key: str                # unique, path within storage provider
    storage_provider: str           # "local_stub" | "local" | (future S3)
    mime_type: str
    size_bytes: int
    sha256_hash: str
    uploaded_by_user_id: UUID | None
    uploaded_by_driver_id: UUID | None
    uploaded_at: datetime
    confirmed_at: datetime | None   # set when upload confirmed
```

### How operational_documents references files.id

In the `operational_documents` ORM model:
```python
file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
```

In the migration:
```python
sa.Column("file_id", UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True)
```

### Upload flow for operational_documents

1. Client calls `POST /api/v1/files/upload` (multipart form) — gets back a `File` record with an `id`
2. Client calls `POST /api/v1/files/confirm` with `{"file_id": "..."}` — sets `confirmed_at`
3. Client calls `POST /api/v1/third-party/documents` with `{"file_id": "...", "subject_type": "...", ...}`

Alternatively the presign flow: `POST /files/presign` → upload to storage → `POST /files/confirm`.

### Validating file_id in operational_documents service

Follow the exact pattern from `drivers/service.py` (renew_driver_document):
```python
if payload.file_id is not None:
    file = await db.get(File, payload.file_id)
    if not file or file.tenant_id != tenant_id:
        raise ApiError("file_not_found", "File not found.", status_code=404)
    # Optionally backlink:
    file.entity_type = "operational_document"
    file.entity_id = doc.id
```

### MAX_UPLOAD_BYTES and MIME types (from files/service.py)
- Max size: `8 * 1024 * 1024` (8 MB)
- Allowed MIME types: `application/pdf`, `image/jpeg`, `image/png`, `image/webp`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

No changes needed to the files module — `operational_documents.file_id` is just an FK reference.

---

## 6. Existing FKs in Fuel and Workshop (Three Nullable FK Additions)

Source: `backend/app/modules/fuel/models.py`, `backend/app/modules/workshop/models.py`

### 6a. FuelPurchase — add `supplier_third_party_id`

**Current model definition** (`fuel/models.py`, lines 92-115):
```python
class FuelPurchase(Base):
    __tablename__ = "fuel_purchases"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "purchase_reference",
            name="uq_fuel_purchases_tenant_reference",
        ),
    )
    id: Mapped[uuid.UUID] = ...
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    supplier_name: Mapped[str] = mapped_column(String(160))   # KEEP — free-text snapshot
    purchase_reference: Mapped[str] = ...
    # ... (no supplier FK currently)
```

**Column to add** in `models.py`:
```python
supplier_third_party_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True, index=True
)
```

**Migration column addition**:
```python
op.add_column("fuel_purchases", sa.Column(
    "supplier_third_party_id", UUID(as_uuid=True),
    sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
    nullable=True,
))
op.create_index("ix_fuel_purchases_supplier_tp", "fuel_purchases", ["supplier_third_party_id"])
```

### 6b. SparePartInventory — add `supplier_third_party_id`

**Current model definition** (`workshop/models.py`, lines 106-129):
```python
class SparePartInventory(Base):
    __tablename__ = "spare_parts_inventory"
    # ...
    supplier_name: Mapped[str | None] = mapped_column(String(160), nullable=True)  # KEEP
    # No supplier FK currently
```

**Column to add** in `models.py`:
```python
supplier_third_party_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True, index=True
)
```

**Migration column addition**:
```python
op.add_column("spare_parts_inventory", sa.Column(
    "supplier_third_party_id", UUID(as_uuid=True),
    sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
    nullable=True,
))
op.create_index("ix_spare_parts_supplier_tp", "spare_parts_inventory", ["supplier_third_party_id"])
```

### 6c. WorkOrder — add `service_provider_third_party_id`

**Current model definition** (`workshop/models.py`, lines 50-80):
```python
class WorkOrder(Base):
    __tablename__ = "work_orders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "work_order_number", name="uq_work_orders_tenant_number"),
    )
    # Fields include: id, tenant_id, maintenance_request_id, plan_id, vehicle_id,
    # work_order_number, diagnosis, planned_work, estimated_cost, actual_cost,
    # status, approved_by, approved_at, closed_by, closed_at, close_notes,
    # labor_cost, created_at, updated_at
    # No service_provider FK currently
```

**Column to add** in `models.py`:
```python
service_provider_third_party_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("third_parties.id", ondelete="SET NULL"), nullable=True, index=True
)
```

**Migration column addition**:
```python
op.add_column("work_orders", sa.Column(
    "service_provider_third_party_id", UUID(as_uuid=True),
    sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
    nullable=True,
))
op.create_index("ix_work_orders_service_provider_tp", "work_orders", ["service_provider_third_party_id"])
```

### serialize_ function updates required
When these FK columns are added to ORM models, the corresponding `serialize_*` functions in `fuel/service.py` and `workshop/service.py` must include the new field:
- `serialize_fuel_log` does NOT serialize FuelPurchase — a separate `serialize_fuel_purchase` exists (not shown, but pattern is identical)
- `serialize_work_order` in `workshop/service.py` (line 85) must add `"service_provider_third_party_id": item.service_provider_third_party_id`

---

## 7. Existing Composite Indexes — No Conflicts Expected

Source: `backend/alembic/versions/b19ec4f5d607_add_composite_indexes.py`

### Indexes already defined (must not duplicate)
| Table | Index name | Columns |
|-------|-----------|---------|
| `trips` | `ix_trips_tenant_status` | (tenant_id, status) |
| `trips` | `ix_trips_tenant_driver_status` | (tenant_id, driver_id, status) |
| `trips` | `ix_trips_tenant_vehicle_status` | (tenant_id, vehicle_id, status) |
| `trips` | `ix_trips_tenant_actual_departure` | (tenant_id, actual_departure) |
| `fuel_logs` | `ix_fuel_logs_tenant_vehicle` | (tenant_id, vehicle_id) |
| `fuel_logs` | `ix_fuel_logs_tenant_created_at` | (tenant_id, created_at) |
| `maintenance_plans` | `ix_maintenance_plans_tenant_status_km` | (tenant_id, status, next_due_km) |
| `maintenance_schedule` | `ix_maintenance_schedule_tenant_status` | (tenant_id, status) |
| `sync_events` | `ix_sync_events_tenant_driver` | (tenant_id, driver_id) |
| `trip_stops` | `ix_trip_stops_tenant_trip` | (tenant_id, trip_id) |

None of these overlap with Phase 23's new tables. New indexes Phase 23 should create:
- `ix_third_parties_tenant_id` on `third_parties`
- `ix_third_parties_tenant_status` on `third_parties(tenant_id, status)` — supports list filtering
- `ix_third_party_roles_third_party_id` on `third_party_roles(third_party_id)`
- `ix_third_party_roles_tenant_role_type` on `third_party_roles(tenant_id, role_type)` — supports role-type lookup
- `ix_operational_documents_tenant_subject` on `operational_documents(tenant_id, subject_type, subject_id)` — supports expiry queries
- `ix_operational_documents_expiry_date` on `operational_documents(expiry_date)` — supports expiry alert scan
- `ix_driver_vehicle_assignments_tenant_driver` on `driver_vehicle_assignments(tenant_id, driver_id)`
- `ix_fuel_purchases_supplier_tp` on `fuel_purchases(supplier_third_party_id)` — if not NULL
- `ix_spare_parts_supplier_tp` on `spare_parts_inventory(supplier_third_party_id)`
- `ix_work_orders_service_provider_tp` on `work_orders(service_provider_third_party_id)`

---

## 8. Architecture Patterns

### Module structure to create
```
backend/app/modules/third_party/
├── models.py       # ThirdParty, ThirdPartyRole, SupplierProfile, ServiceProviderProfile,
│                   # MzProvince, DriverVehicleAssignment, OperationalDocument
├── service.py      # CRUD services + PartyDirectoryService + OperationalEligibilityService
│                   # + generate_document_expiry_alerts
├── router.py       # APIRouter(prefix="/third-party", tags=["third-party"])
└── schemas.py      # Pydantic Create/Patch/Read schemas
```

### Router prefix convention
Existing modules use singular nouns: `/drivers`, `/vehicles`, `/clients`. Use `/third-party` (hyphenated, matches multi-word convention used by `/trip-orders`, `/known-routes`, `/operational-exceptions`).

### PartyDirectoryService UNION ALL pattern

Following the exact UNION ALL pattern established in `drivers/service.py` (`list_driver_history`):
```python
from sqlalchemy import func, literal, union_all

_drivers = select(
    Driver.id.label("subject_id"),
    literal("driver").label("subject_type"),
    Driver.full_name.label("name"),
    Driver.status.label("status"),
).where(Driver.tenant_id == tenant_id)

_clients = select(
    Client.id.label("subject_id"),
    literal("client").label("subject_type"),
    Client.trading_name.label("name"),
    func.cast(Client.is_active, String).label("status"),
).where(Client.tenant_id == tenant_id)

_third_parties = select(
    ThirdParty.id.label("subject_id"),
    literal("third_party").label("subject_type"),
    ThirdParty.name.label("name"),
    ThirdParty.status.label("status"),
).where(ThirdParty.tenant_id == tenant_id)

stmt = union_all(_drivers, _clients, _third_parties).order_by(text("name ASC")).limit(limit).offset(offset)
```

### OperationalEligibilityService — pure Python, no DB writes

```python
from dataclasses import dataclass
from datetime import date
from app.modules.drivers.models import Driver

@dataclass
class EligibilityResult:
    is_eligible: bool
    blocking_reasons: list[str]
    warnings: list[str]

def check_driver_eligibility(driver: Driver, reference_date: date) -> EligibilityResult:
    blocking = []
    warnings = []
    if driver.status != "active":
        blocking.append(f"Driver status is '{driver.status}'")
    if driver.license_valid_until and driver.license_valid_until < reference_date:
        blocking.append("Driving license expired")
    # ... etc
    return EligibilityResult(is_eligible=not blocking, blocking_reasons=blocking, warnings=warnings)
```

---

## 9. Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Idempotent mutations | Custom dedup logic | `execute_http_idempotent()` from `app.core.idempotency` |
| Audit trail | Custom logging | `record_audit_log()` from `app.modules.audit.service` |
| Alert deduplication | Custom alert dedup | `create_alert()` with deterministic `request_reference` — already idempotent |
| File upload/storage | New upload infrastructure | Existing `files` module — just store `file_id` FK |
| Tenant isolation | Custom WHERE clause checks | `_require_third_party()` guard + RLS at DB layer |
| Province data structure | Hardcoded Python dict | `mz_provinces` table — queryable, extensible |

---

## 10. Common Pitfalls

### Pitfall 1: Missing RLS on a new tenant_id table
**What goes wrong:** Table is created, rows are inserted, but a different tenant can read them because `current_setting('app.tenant_id', true)` has no policy to enforce.
**Why it happens:** RLS added in a separate follow-up migration runs after the table exists but BEFORE rows are inserted — gap between creation and policy.
**How to avoid:** RLS + GRANT in the same `CREATE TABLE` migration. Never split them. The clients migration (`a2b3c4d5e6f7`) is the canonical example.
**Warning signs:** `test_cross_tenant_isolation_*` test passes at create time but fails at list time.

### Pitfall 2: NOT NULL on nullable FK columns
**What goes wrong:** `supplier_third_party_id NOT NULL` constraint fails on all existing `fuel_purchases` rows.
**Why it happens:** Alembic `add_column` with `nullable=False` and no `server_default` fails with constraint violation.
**How to avoid:** All three FK additions (`fuel_purchases`, `spare_parts_inventory`, `work_orders`) MUST be `nullable=True`. CONTEXT.md decision C explicitly states this.

### Pitfall 3: mz_provinces with tenant_id column
**What goes wrong:** Adding `tenant_id` to `mz_provinces` would require RLS and make it tenant-specific, defeating its purpose as a platform reference table.
**How to avoid:** `mz_provinces` has no `tenant_id`. Grant `SELECT` only (not INSERT/UPDATE/DELETE) to `rotas_app`.

### Pitfall 4: Forgetting to add module to MODEL_MODULES
**What goes wrong:** SQLAlchemy metadata doesn't know about `ThirdParty` model at startup. Alembic autogenerate sees the table as "extra" and tries to drop it. FK references from other models fail with mapper errors.
**How to avoid:** Add `"third_party"` to `MODEL_MODULES` in `database.py` in the same task as creating `models.py`.

### Pitfall 5: PartyDirectoryService using sequential queries
**What goes wrong:** Three separate `SELECT` queries return data separately, requiring Python-level merge and sort — incorrect pagination, N+1 latency.
**How to avoid:** Single `UNION ALL` query. Follow the `list_driver_history` pattern from `drivers/service.py`.

### Pitfall 6: Alert request_reference collisions
**What goes wrong:** Two different documents with same expiry date generate alerts with the same `request_reference`. If their payloads differ (different `entity_id`), `create_alert()` raises 409.
**How to avoid:** Include `doc.id` (the operational_document UUID) in the `request_reference`, not just `expiry_date`. e.g., `f"doc_expiry:{doc.id}:{doc.expiry_date.isoformat()}"`.

---

## 11. Validation Architecture

`nyquist_validation` is enabled in `.planning/config.json`.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio 0.23 |
| Config file | `backend/pytest.ini` or `backend/pyproject.toml [tool.pytest]` |
| Quick run command | `cd backend && pytest tests/test_third_party.py -x -q` |
| Full suite command | `cd backend && pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| TP-01 | Create/read/patch third_party, tenant isolation | unit/integration | `pytest tests/test_third_party.py::test_create_third_party -x` |
| TP-02 | Assign/revoke roles, role_type enum enforcement | unit/integration | `pytest tests/test_third_party.py::test_third_party_roles -x` |
| TP-03 | Supplier profile CRUD, FK to third_party | unit | `pytest tests/test_third_party.py::test_supplier_profile -x` |
| TP-04 | Service provider profile CRUD, JSON arrays | unit | `pytest tests/test_third_party.py::test_service_provider_profile -x` |
| TP-05 | mz_provinces list, no tenant filter | unit | `pytest tests/test_third_party.py::test_mz_provinces -x` |
| TP-06 | Nullable FK on fuel_purchases/spare_parts/work_orders | migration/unit | `pytest tests/test_third_party.py::test_nullable_fk_additions -x` |
| TP-07 | EligibilityService returns blocking/warning per driver field | unit | `pytest tests/test_third_party.py::test_eligibility_service -x` |
| TP-08 | DriverVehicleAssignment create/unassign/history | unit | `pytest tests/test_third_party.py::test_driver_vehicle_assignment -x` |
| TP-09 | OperationalDocument create, file_id validation, PartyRef | unit | `pytest tests/test_third_party.py::test_operational_documents -x` |
| TP-10 | Document expiry alert generation, deduplication | unit | `pytest tests/test_third_party.py::test_doc_expiry_alerts -x` |
| TP-11 | PartyDirectoryService UNION ALL, subject_type filter | unit | `pytest tests/test_third_party.py::test_party_directory -x` |

### Wave 0 Gaps
- [ ] `backend/tests/test_third_party.py` — covers all TP-01 through TP-11
- Existing `backend/tests/conftest.py` provides shared fixtures (db session, tenant, user) — no new conftest needed

---

## Sources

### Primary (HIGH confidence)
All findings are from direct file inspection of the current codebase. No external sources consulted.

| File | What was verified |
|------|------------------|
| `backend/app/modules/drivers/service.py` | serialize_, _require_, record_audit_log placement, create/patch pattern |
| `backend/app/modules/drivers/router.py` | Router structure, Depends(get_session), require_roles, idempotency wrapping |
| `backend/app/modules/drivers/schemas.py` | Pydantic BaseModel with optional fields, no Config class needed |
| `backend/app/modules/alerts/service.py` | create_alert() signature, idempotency behavior, priority/channel validation |
| `backend/app/modules/alerts/models.py` | Alert field types and lengths |
| `backend/app/modules/alerts/schemas.py` | AlertCreate fields |
| `backend/app/modules/audit/service.py` | record_audit_log() exact signature |
| `backend/alembic/versions/a2b3c4d5e6f7_add_clients_table.py` | Canonical RLS+GRANT boilerplate |
| `backend/alembic/versions/b19ec4f5d607_add_composite_indexes.py` | Existing indexes to avoid duplicating |
| `backend/app/modules/fuel/models.py` | FuelPurchase.supplier_name current declaration |
| `backend/app/modules/workshop/models.py` | WorkOrder and SparePartInventory current declarations |
| `backend/app/modules/files/models.py` | File model fields |
| `backend/app/modules/files/service.py` | _require_file pattern, MAX_UPLOAD_BYTES |
| `backend/app/modules/files/router.py` | Upload/confirm/presign endpoint structure |
| `backend/app/main.py` | Router registration pattern and import order |
| `backend/app/database.py` | MODEL_MODULES tuple |
| `.planning/phases/23-third-party-registry/23-CONTEXT.md` | All locked decisions |

---

## Metadata

**Confidence breakdown:**
- Service layer pattern: HIGH — copied directly from existing module code
- Alert generation pattern: HIGH — AlertCreate schema and create_alert() read directly
- Migration RLS boilerplate: HIGH — exact SQL from canonical clients migration
- Router registration: HIGH — main.py and database.py read directly
- Files module reference: HIGH — File model and service read directly
- Existing FK declarations: HIGH — models.py read directly
- Index conflict check: HIGH — composite index migration read directly

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (stable codebase, 30-day horizon)
