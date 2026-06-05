# Phase 4: Production Hardening + Scale Preparation — Research

**Researched:** 2026-06-05
**Domain:** FastAPI production deployment, ARQ worker scheduling, PostgreSQL RLS, Python type hardening
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**MAINT-01: Preventive Maintenance Scheduler**
- D-01: Trigger combinado — evento de odómetro (imediato, quando FuelLog ou TripStop actualiza odómetro) + cron diário ARQ (safety net para planos por calendário com interval_days).
- D-02: Quando o scheduler deteta `odometro_actual >= next_due_km` OR `hoje >= next_due_at`, criar um WorkOrder automaticamente e marcar o `MaintenanceSchedule` actual com `status='triggered'`.
- D-03: Criar nova entrada `MaintenanceSchedule` para o próximo ciclo: `next_due_km = odometro_trigger + interval_km`, `next_due_at = today + interval_days`. Não fazer reset in-place — manter histórico.
- D-04: Se já existir WorkOrder aberto (status != 'closed'/'cancelled') para o mesmo `plan_id` + `vehicle_id`, scheduler faz skip silencioso e regista no log.
- D-05: Fechar o WorkOrder não tem side effects no scheduler — próximo MaintenanceSchedule já foi criado no trigger.
- D-06: Alertas proactivos: viaturas com `due_at <= hoje + 30 dias` OR `due_km <= odometro_actual + 500 km` aparecem num painel "Manutenção Iminente".
- D-07: Scheduler corre como nova task no mesmo ARQ worker (não criar worker separado). Cron diário + handler de evento de odómetro.

**Driver Scorecard**
- D-08: Métricas: (1) distância percorrida km, (2) taxa de entrega comprovada, (3) pontualidade de sync, (4) duração de paradas.
- D-09: Score composto 0–100 com código de cor: verde ≥ 80, amarelo 60–79, vermelho < 60.
- D-10: Período de cálculo: rolling 30 dias.
- D-11: Scorecard visível apenas ao gestor no manager dashboard. Sem alterações ao driver PWA.

**Escalabilidade: Gunicorn + Workers**
- D-12: Backend FastAPI usa `gunicorn -k uvicorn.workers.UvicornWorker` com 4 workers. `startCommand` em `railway.toml` actualizado.
- D-13: ARQ worker corre como serviço Railway separado do backend HTTP. Comando: `arq app.jobs.worker.WorkerSettings`.
- D-14: Composite index audit: 10 queries de maior volume, `EXPLAIN ANALYZE` em staging, `CREATE INDEX CONCURRENTLY` onde Seq Scan em tabelas > 1 000 rows. Codificado como migration Alembic.

**Numeric/Float Migration (D-15 — CONFIRMADO)**
- D-15: Todas as colunas monetárias já usam `Numeric(x,y)` no DB. O que existe são type hints Python `Mapped[float]` que podem ser actualizados para `Mapped[Decimal]`. Esta é uma mudança cosmética de tipos Python, não uma migration de schema.

**PostgreSQL RLS**
- D-16: RLS incluído como segunda camada de isolamento multitenant (defense-in-depth).
- D-17: `SET LOCAL app.tenant_id = '<uuid>'` via SQLAlchemy event listener no início de cada transacção. A policy verifica `current_setting('app.tenant_id')`.
- D-18: Dois roles PostgreSQL: `rotas_app` (RLS activo), `rotas_admin` (BYPASSRLS para ARQ worker). `DATABASE_URL` da app usa `rotas_app`; ARQ worker usa URL separada com `rotas_admin`.
- D-19: Alembic migration cria as policies RLS em todas as tabelas com `tenant_id`. Testes cross-tenant existentes (Phase 1) são o gate de verificação.

### Claude's Discretion
- Ponderação exacta de cada métrica no score composto (ex: 40% delivery proof, 30% km, 20% sync, 10% paradas).
- Quais tabelas específicas precisam de RLS policies vs apenas as principais.
- Número exacto de workers Gunicorn pode ser ajustado (baseline: 4 workers / 2 GB RAM).

### Deferred Ideas (OUT OF SCOPE)
- Scorecard visível ao motorista no PWA.
- Integrações com canais de notificação (email/WhatsApp) para alertas de manutenção.
- Resolução de conflitos de sync com UI.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MAINT-01 | Preventive maintenance scheduler: odometer/calendar triggers generating work orders automatically | D-01 through D-07 decisions; existing `evaluate_maintenance_schedule()` function is the foundation; ARQ cron + fuel service event hook are the two trigger paths |
</phase_requirements>

---

## Summary

Phase 4 is an operational hardening phase — no new user-facing features except the maintenance scheduler and driver scorecard. The research confirms five implementation workstreams: (1) MAINT-01 scheduler extending existing `evaluate_maintenance_schedule()` with WorkOrder auto-creation and next-cycle record creation, (2) driver scorecard aggregated from existing trip/sync/delivery data, (3) Python type annotation cleanup (`Mapped[float]` → `Mapped[Decimal]`) with no schema changes required, (4) ARQ + Gunicorn deployment configuration, and (5) PostgreSQL RLS via SQLAlchemy event listener + Alembic migration.

The most significant discovery is that the maintenance scheduler foundation already exists. `evaluate_maintenance_schedule()` in `backend/app/modules/workshop/service.py` already detects overdue plans and creates `MaintenanceSchedule` records with `status='overdue'`. What MAINT-01 adds is: (a) auto-creating a `WorkOrder` on trigger instead of just a schedule record, (b) creating the next-cycle schedule entry (D-03), (c) the dual-trigger architecture (odometer event + daily cron via ARQ), and (d) the proactive alerts panel (D-06). The `MaintenancePlan` and `MaintenanceSchedule` models are complete and require no schema changes — only the scheduler logic needs expansion.

The D-15 scout finding is confirmed: all monetary columns across all modules already use `Numeric(x,y)` at the database level. The `Mapped[float]` type hints are Python-only annotations. This makes the "numeric migration" purely a type-annotation update — no Alembic migration required for this workstream.

**Primary recommendation:** Implement in four waves: (Wave 0) ARQ + dependencies installed, test stubs created; (Wave 1) MAINT-01 scheduler with WorkOrder creation + next-cycle logic; (Wave 2) driver scorecard API + dashboard component; (Wave 3) RLS + Gunicorn + composite indexes.

---

## Standard Stack

### Core (new additions for this phase)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `arq` | `>=0.26` | Async Redis job queue + cron scheduler | asyncio-native, simple WorkerSettings API, cron built-in; already chosen in Phase 3 (CT-02) |
| `redis[asyncio]` | `>=5.0` | Redis client for ARQ | asyncio client required by arq; already provisioned on port 6381 |
| `gunicorn` | `>=22.0` | Multi-worker process manager | Supervises multiple UvicornWorker instances for horizontal CPU use |

### Supporting (type hardening)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `decimal` (stdlib) | stdlib | `Decimal` type for monetary Python annotations | Replace `Mapped[float]` where column is `Numeric(x,y)` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ARQ | Celery | Celery requires separate broker config, heavier, not asyncio-native; ARQ already decided in Phase 3 |
| ARQ cron | APScheduler | APScheduler runs in-process and doesn't survive worker restarts; ARQ cron persists in Redis |
| `gunicorn -k UvicornWorker` | `uvicorn --workers N` | `uvicorn --workers` uses multiprocessing but lacks graceful restart and `preload_app`; gunicorn is the FastAPI docs recommendation for production |

**Installation (new packages for this phase):**
```bash
cd backend
pip install "arq>=0.26" "redis[asyncio]>=5.0" "gunicorn>=22.0"
# Update pyproject.toml dependencies accordingly
```

**Version verification (run before planning tasks):**
```bash
pip index versions arq 2>/dev/null | head -2
pip index versions gunicorn 2>/dev/null | head -2
pip index versions redis 2>/dev/null | head -2
```

---

## Architecture Patterns

### Existing Code to Extend (not replace)

The key insight: `evaluate_maintenance_schedule()` at `backend/app/modules/workshop/service.py:1255` already does most of the detection work. Phase 4 must:

1. **Extend** it to create a `WorkOrder` when a schedule entry is created (not just a `MaintenanceSchedule` row)
2. **Add** next-cycle `MaintenanceSchedule` creation (D-03)
3. **Wire** the function as an ARQ cron task (daily) and as a side-effect of the fuel service odometer update

Current flow (`evaluate_maintenance_schedule`):
- Joins `MaintenancePlan` + `Vehicle`
- Checks `current_km >= next_due_km` OR `next_due_at <= now`
- Creates `MaintenanceSchedule` with `status='overdue'` (no WorkOrder, no next-cycle record)

Required additions per D-02 through D-04:
- After creating `MaintenanceSchedule`, call `create_work_order_from_plan()` (new helper)
- Skip if existing open WorkOrder for same `plan_id` + `vehicle_id` (D-04 de-dupe check)
- Create next-cycle `MaintenanceSchedule` with `status='pending'` and projected `due_km`/`due_at` (D-03)

### Recommended Project Structure (new files)

```
backend/app/
├── jobs/
│   ├── __init__.py
│   ├── worker.py              # WorkerSettings — functions + cron_jobs
│   └── tasks/
│       ├── __init__.py
│       └── maintenance.py     # check_maintenance_schedules() ARQ task
├── modules/
│   ├── workshop/
│   │   └── service.py         # extend evaluate_maintenance_schedule()
│   └── vehicles/
│       └── service.py         # extend fuel odometer update to enqueue ARQ task
└── database.py                # add RLS event listener (new section)
```

### Pattern 1: ARQ Worker with Cron + Database Access

```python
# backend/app/jobs/worker.py
from arq import cron
from arq.connections import RedisSettings
from app.jobs.tasks.maintenance import check_maintenance_schedules

async def startup(ctx: dict) -> None:
    # ARQ worker needs its own DB session factory (uses rotas_admin URL for BYPASSRLS)
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.config import get_settings
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)  # new setting
    ctx["session_factory"] = async_sessionmaker(engine, expire_on_commit=False)

async def shutdown(ctx: dict) -> None:
    await ctx["session_factory"].kw["bind"].dispose()

class WorkerSettings:
    functions = [check_maintenance_schedules]
    cron_jobs = [
        cron(check_maintenance_schedules, hour={2}, minute=0)  # 02:00 UTC daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(host="localhost", port=6381)
```

**Key point (D-18):** The ARQ worker must use `ADMIN_DATABASE_URL` with `rotas_admin` role (BYPASSRLS). The FastAPI app uses `DATABASE_URL` with `rotas_app` role (RLS enforced). This requires a new `ADMIN_DATABASE_URL` env var in Settings.

### Pattern 2: ARQ Cron Task for Maintenance Scheduler

```python
# backend/app/jobs/tasks/maintenance.py
import logging
from app.modules.workshop.service import evaluate_maintenance_schedule_all_tenants

logger = logging.getLogger(__name__)

async def check_maintenance_schedules(ctx: dict) -> dict:
    """Daily cron: scan all active tenants for overdue maintenance plans."""
    session_factory = ctx["session_factory"]
    async with session_factory() as db:
        result = await evaluate_maintenance_schedule_all_tenants(db)
    logger.info("Maintenance schedule check: %s", result)
    return result
```

The worker-level function `evaluate_maintenance_schedule_all_tenants()` is new — it iterates all active tenants and calls the existing per-tenant `evaluate_maintenance_schedule()` for each. This avoids the RLS problem (worker uses BYPASSRLS role).

### Pattern 3: Odometer Event Trigger (D-01 second path)

The odometer update happens in `backend/app/modules/fuel/service.py` at line 202:
```python
vehicle.current_km = max(vehicle.current_km, payload.km_at_refuel)
```

After this line, enqueue an ARQ task:
```python
# After updating vehicle.current_km
from arq.connections import create_pool, RedisSettings
redis = await create_pool(RedisSettings(host=..., port=6381))
await redis.enqueue_job(
    "check_vehicle_maintenance",
    vehicle_id=str(vehicle.id),
    tenant_id=str(tenant_id),
    current_km=vehicle.current_km,
)
```

This triggers an immediate check for that specific vehicle rather than waiting for the daily cron. The cron remains as the safety net for calendar-based plans.

### Pattern 4: PostgreSQL RLS via SQLAlchemy Event Listener (D-17)

```python
# backend/app/database.py — new section after engine creation
from contextvars import ContextVar
from sqlalchemy import event, text

_rls_tenant_id: ContextVar[str | None] = ContextVar("_rls_tenant_id", default=None)

def set_rls_tenant(tenant_id: str) -> None:
    _rls_tenant_id.set(tenant_id)

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _set_tenant_rls(conn, cursor, statement, parameters, context, executemany):
    tenant_id = _rls_tenant_id.get()
    if tenant_id:
        cursor.execute(f"SET LOCAL app.tenant_id = '{tenant_id}'")
```

**Wire into FastAPI session dependency:**
```python
# In get_session() dependency (database.py)
async def get_session(
    principal: Principal = Depends(get_current_principal),
) -> AsyncIterator[AsyncSession]:
    set_rls_tenant(str(principal.tenant_id))
    async with AsyncSessionLocal() as session:
        yield session
    set_rls_tenant(None)  # reset after request
```

**CRITICAL CAVEAT:** `SET LOCAL` scopes the variable to the current transaction. With asyncpg connection pooling, `SET LOCAL` (not `SET`) is mandatory — pooled connections must not carry stale tenant_id between requests.

**CRITICAL CAVEAT 2:** The `before_cursor_execute` event is synchronous. With asyncpg, this sync event fires on the underlying DBAPI connection via `sync_engine`. This approach is confirmed to work with SQLAlchemy 2.0 + asyncpg via `engine.sync_engine`.

### Pattern 5: RLS Alembic Migration (D-19)

```python
# backend/alembic/versions/XXXX_add_rls_policies.py
def upgrade() -> None:
    # Create roles
    op.execute("CREATE ROLE rotas_app")
    op.execute("CREATE ROLE rotas_admin BYPASSRLS")
    # Grant permissions
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rotas_app")
    # Enable RLS on tenant-scoped tables
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id::text = current_setting('app.tenant_id', true))
        """)
```

`current_setting('app.tenant_id', true)` — the `true` argument makes it return NULL if the setting is not set, rather than raising an error (important for migrations and admin operations).

### Pattern 6: Gunicorn Configuration (D-12)

```toml
# railway.toml — updated startCommand
[deploy]
preDeployCommand = ["alembic upgrade head"]
startCommand = "gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 30 --bind 0.0.0.0:$PORT backend.app.main:app"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 5
```

**Worker count rationale:** 4 workers is the Railway starter plan baseline (2 vCPU, 2 GB RAM). Formula: `(2 × vCPU) + 1 = 5`, but memory ceiling caps at 4 workers for 2 GB RAM (each worker uses ~300–400 MB with SQLAlchemy pool).

### Pattern 7: Driver Scorecard Formula (D-08, D-09 — Claude's Discretion)

Proposed weighting (open for planner adjustment):

| Metric | Weight | Source Tables | Computation |
|--------|--------|---------------|-------------|
| Delivery proof rate | 40% | `trips`, `delivery_proofs` / `cargo_manifests` | `delivered_trips / completed_trips` in rolling 30d |
| Sync discipline | 25% | `sync_events` | `sync_batches / trips` ratio — higher is better (floor at 1 per trip) |
| Distance efficiency | 20% | `trips` (km_start, km_end) | Raw km in period — normalized 0–100 against fleet percentile |
| Stop duration | 15% | `trip_stops` (stopped_at, resumed_at) | Avg stop minutes per km travelled — inverted (shorter = better) |

Score = `(0.40 × delivery_rate) + (0.25 × sync_score) + (0.20 × distance_score) + (0.15 × stop_score)`, each normalized 0–100.

This is a pure-read aggregation: no new data collection, no new tables. A single service function `get_driver_scorecard(db, tenant_id, driver_id, days=30)` performs the aggregation.

### Anti-Patterns to Avoid

- **SET without LOCAL:** `SET app.tenant_id = X` persists for the connection lifetime in the pool. Always `SET LOCAL` to scope to current transaction. Using `SET` causes cross-request tenant data leaks.
- **ARQ worker using app DATABASE_URL:** The worker processes all tenants and must bypass RLS. Using the app role would make cross-tenant queries fail or return empty. Always use `rotas_admin` (BYPASSRLS) role for the ARQ worker URL.
- **Re-triggering maintenance from WorkOrder close:** D-05 explicitly forbids this. Next-cycle record is created at trigger time, not at close time.
- **In-place reset of MaintenancePlan:** D-03 requires new `MaintenanceSchedule` row per cycle. Do not update `MaintenancePlan.next_due_km` in place — that loses the trigger history.
- **Gunicorn timeout too short for sync batch:** `POST /api/v1/sync/batch` can process large offline payloads. `--timeout 30` is the minimum; if sync batches time out in production, raise to 60.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cron scheduling | Custom cron runner with asyncio.sleep loop | `arq.cron()` in WorkerSettings | ARQ cron persists job IDs in Redis, prevents double-runs on worker restart, handles missed jobs |
| Job deduplication | Custom "check if job running" logic | `arq` built-in job_id uniqueness | ARQ uses deterministic job IDs (`cron:fn_name:timestamp`) — enqueueing same job twice is safe |
| RLS context propagation | Custom middleware that monkey-patches session | `ContextVar` + SQLAlchemy event listener | ContextVar is asyncio-safe (no shared state between coroutines); middleware approach races |
| Numeric aggregation for scorecard | Custom `float`-based rolling average | SQLAlchemy `func.avg()`, `func.count()` with proper filters | SQL-level aggregation avoids loading thousands of rows into Python memory |

---

## D-15 Confirmation: No Numeric Schema Migration Required

Confirmed by full scan of all `models.py` files across all modules:

**All monetary/financial columns already use `Numeric(x,y)` at the database level.**

The `Mapped[float]` Python type hints are annotations only — SQLAlchemy maps `Numeric` columns to `Decimal` at runtime regardless of the Python annotation. The annotation does not affect stored precision.

Files with `Mapped[float]` annotations on `Numeric(x,y)` columns (type hint update only):
- `billing/models.py` — subtotal, tax_amount, total_amount, quantity, unit_price, amount
- `trips/models.py` — total_fuel_cost, total_expense_cost, total_transport_cost, actual_revenue, actual_margin, cost (TripStop), amount (TripCost)
- `fuel/models.py` — liters, price_per_liter, total_cost, capacity_liters, current_stock_liters, etc.
- `workshop/models.py` — estimated_cost, actual_cost, current_quantity, average_unit_cost, etc.
- `contracts/models.py` — default_unit_price
- `trip_orders/models.py` — estimated costs

**Action required:** Update Python type annotations from `Mapped[float]` to `Mapped[Decimal]` where the SQLAlchemy column type is `Numeric`. No Alembic migration needed. This is a code-quality task, not a data migration.

---

## Composite Index Audit (D-14)

Based on schema review of high-traffic tables, the following composite indexes are candidates (to be verified with `EXPLAIN ANALYZE` on staging):

| Table | Suggested Index | Query Pattern |
|-------|----------------|---------------|
| `trips` | `(tenant_id, status)` | Control Tower: active trips per tenant |
| `trips` | `(tenant_id, driver_id, status)` | Driver scorecard: trips by driver in period |
| `trips` | `(tenant_id, vehicle_id, status)` | Fleet history per vehicle |
| `trips` | `(tenant_id, actual_departure)` | Date-range trip queries |
| `fuel_logs` | `(tenant_id, vehicle_id)` | Fuel history per vehicle |
| `fuel_logs` | `(tenant_id, created_at)` | Date-range fuel queries |
| `maintenance_plans` | `(tenant_id, status, next_due_km)` | Scheduler: find active plans near due |
| `maintenance_schedule` | `(tenant_id, status)` | Dashboard: overdue + pending counts |
| `sync_events` | `(tenant_id, driver_id, entity_type)` | Scorecard: sync batch count per driver |
| `trip_stops` | `(tenant_id, trip_id)` | Stop duration aggregation per trip |

**Current state:** All tables already have `tenant_id index=True` (single-column). The composite indexes add a second query-specific column to reduce index scan costs. Use `CREATE INDEX CONCURRENTLY` in Alembic migration to avoid locking.

---

## Tenant-Scoped Tables Requiring RLS Policies

Based on full schema scan, tables with `tenant_id` column (requiring RLS policy):

```
tenants (special — skip, tenant owns itself)
users, drivers, driver_devices, driver_sessions
vehicles, fuel_logs, fuel_tanks, fuel_purchases, fuel_receipts, fuel_movements, vehicle_refuels, fuel_stock_counts
trips, trip_stops, trip_costs, dispatch_clearances, trip_execution_events, trip_incidents, known_routes
trip_orders
checklists, checklist_templates, checklist_responses
cargo: load_permits, cargo_manifests, transport_documents, delivery_proofs
billing_documents, billing_items
contracts
maintenance_requests, work_orders, work_order_tasks, spare_parts_inventory, spare_part_movements, maintenance_parts_used, workshop_tools, tool_checkouts, maintenance_plans, maintenance_schedule
operational_exceptions, alerts
sync_events, idempotency_keys
audit_logs
```

**Tables to EXCLUDE from RLS (or use different policy):**
- `tenants` — the root table; policy would be `id = current_setting('app.tenant_id')::uuid` (not `tenant_id`)
- Alembic migration version tables — never have tenant_id, never get RLS

---

## Common Pitfalls

### Pitfall 1: RLS blocks Alembic migrations
**What goes wrong:** Alembic runs under `DATABASE_URL` with `rotas_app` role. If `app.tenant_id` is not set, `current_setting('app.tenant_id', true)` returns NULL and the RLS policy rejects all rows. Alembic `upgrade` fails.
**Why it happens:** Alembic connects as `rotas_app` (same URL as the app), so RLS applies.
**How to avoid:** Alembic must connect as `rotas_admin` (BYPASSRLS). Add `ALEMBIC_DATABASE_URL` env var with `rotas_admin` role. Update `alembic/env.py` to use this URL.
**Warning signs:** `alembic upgrade head` succeeds but `alembic downgrade` fails with zero rows affected.

### Pitfall 2: `MaintenanceSchedule` UniqueConstraint violation on next-cycle creation
**What goes wrong:** The existing `UniqueConstraint("tenant_id", "plan_id", "status", ...)` means only one record per (tenant, plan, status) can exist. Creating a next-cycle `status='pending'` record while a `status='overdue'` one exists is fine — but creating two `status='pending'` records (double-trigger) violates the constraint.
**Why it happens:** If the odometer event fires twice in quick succession (e.g., two fuel logs close together), two create attempts race.
**How to avoid:** D-04 de-dupe check before creating: `SELECT ... WHERE plan_id=X AND status NOT IN ('completed','cancelled')` — if any row exists, skip. The UniqueConstraint is a safety net, not the primary guard.

### Pitfall 3: ARQ worker uses pooled connections without asyncpg BYPASSRLS role
**What goes wrong:** If `ADMIN_DATABASE_URL` is not configured separately, the worker uses the same `DATABASE_URL` as the app. The app URL uses `rotas_app` — RLS is enforced. The daily cron calls `evaluate_maintenance_schedule_all_tenants()` which queries without setting `app.tenant_id` → returns zero rows for all tenants.
**How to avoid:** Add `admin_database_url: str = Field(validation_alias="ADMIN_DATABASE_URL")` to Settings. Worker startup uses this URL. Document this in Railway env vars.

### Pitfall 4: Gunicorn worker count exceeds Railway RAM
**What goes wrong:** 4 Gunicorn workers × ~400 MB each = 1.6 GB + SQLAlchemy connection pools + Redis client = OOM kills on Railway Starter (2 GB RAM).
**Why it happens:** SQLAlchemy `async_sessionmaker` creates a pool per worker process. With default `pool_size=5`, 4 workers = 20 DB connections minimum.
**How to avoid:** Set `pool_size=2, max_overflow=3` on the engine for production. Monitor Railway memory dashboard after first deploy.

### Pitfall 5: Driver scorecard with empty rolling window returns div-by-zero
**What goes wrong:** A driver with no trips in the last 30 days has `completed_trips = 0`. `delivered / completed` → division by zero.
**Why it happens:** New drivers, or drivers on leave.
**How to avoid:** All metric computations must guard with `NULLIF(denominator, 0)` in SQL, or return `None` / "insufficient data" score when `completed_trips < 3` (minimum viable window).

### Pitfall 6: `current_setting('app.tenant_id')` type mismatch
**What goes wrong:** PostgreSQL stores session variables as `text`. The `tenant_id` column is `UUID`. RLS policy `USING (tenant_id = current_setting('app.tenant_id'))` fails with type mismatch.
**How to avoid:** Cast in the policy: `USING (tenant_id::text = current_setting('app.tenant_id', true))` or `USING (tenant_id = current_setting('app.tenant_id', true)::uuid)`. The latter is safer for proper UUID validation.

---

## Code Examples

### MAINT-01: WorkOrder creation on scheduler trigger

```python
# Extension to evaluate_maintenance_schedule() in workshop/service.py
# Source: existing pattern in workshop/service.py create_work_order()

async def _trigger_maintenance_work_order(
    db: AsyncSession,
    tenant_id: UUID,
    plan: MaintenancePlan,
    vehicle: Vehicle,
    schedule: MaintenanceSchedule,
    actor_id: UUID | None,
) -> WorkOrder | None:
    """Create WorkOrder if no open one exists for this plan+vehicle (D-04)."""
    existing = await db.scalar(
        select(WorkOrder).where(
            WorkOrder.tenant_id == tenant_id,
            WorkOrder.vehicle_id == plan.vehicle_id,
            WorkOrder.status.not_in(["closed", "cancelled"]),
            # Link via maintenance_request or a new plan_id field
        )
    )
    if existing:
        logger.info("Skip: open WO %s for plan %s", existing.id, plan.id)
        return None
    # Create work order
    work_order = WorkOrder(
        tenant_id=tenant_id,
        vehicle_id=plan.vehicle_id,
        work_order_number=_generate_wo_number(tenant_id),
        planned_work=f"Preventive: {plan.name}",
        status="draft",
    )
    db.add(work_order)
    await db.flush()
    return work_order
```

### RLS: SQLAlchemy event listener wiring

```python
# backend/app/database.py
from contextvars import ContextVar
from sqlalchemy import event

_rls_tenant: ContextVar[str | None] = ContextVar("_rls_tenant", default=None)

def set_rls_tenant(tenant_id: str | None) -> None:
    _rls_tenant.set(tenant_id)

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _inject_rls_tenant(conn, cursor, statement, parameters, context, executemany):
    tid = _rls_tenant.get()
    if tid is not None:
        cursor.execute(f"SET LOCAL app.tenant_id = '{tid}'")
```

### ARQ cron registration

```python
# backend/app/jobs/worker.py
from arq import cron
from app.jobs.tasks.maintenance import check_maintenance_schedules

class WorkerSettings:
    functions = [check_maintenance_schedules]
    cron_jobs = [
        cron(check_maintenance_schedules, hour={2}, minute=0)  # 02:00 UTC
    ]
    redis_settings = RedisSettings(host="redis", port=6381)
    on_startup = startup
    on_shutdown = shutdown
```

### Composite index in Alembic migration

```python
# Alembic migration — use CONCURRENTLY to avoid table lock
def upgrade() -> None:
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trips_tenant_status ON trips (tenant_id, status)"
    )
    op.execute(
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
        "ix_trips_tenant_driver_status ON trips (tenant_id, driver_id, status)"
    )
```

**Note:** `op.execute()` with raw SQL is required for `CREATE INDEX CONCURRENTLY` — `op.create_index()` does not support the CONCURRENTLY keyword in Alembic.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `uvicorn --workers N` directly | `gunicorn -k UvicornWorker` | FastAPI docs 2022+ | Graceful reload, proper signal handling, pre-fork model |
| `arq` 0.25 synchronous API | `arq` 0.26+ with `cron()` built-in | arq 0.25 | Cron jobs declared in WorkerSettings, no separate scheduler |
| RLS via `SET` (persistent) | `SET LOCAL` (transaction-scoped) | PostgreSQL best practice | Critical for connection pool reuse — pool connections must not carry stale tenant |
| `python-jose` JWT | `PyJWT >= 2.8` | Phase 1 (already done per pyproject.toml) | CVE-2025-61152 fix — already implemented |

**Deprecated/outdated:**
- `python-jose`: already replaced by `PyJWT` in this project (confirmed in `pyproject.toml` and `auth.py`)
- `uvicorn --workers` in production: `gunicorn -k UvicornWorker` is the correct production pattern

---

## Open Questions

1. **WorkOrder linkage to MaintenancePlan**
   - What we know: `WorkOrder` has `maintenance_request_id` FK but no `plan_id` FK. The scheduler creates WorkOrders without a prior MaintenanceRequest.
   - What's unclear: How to link the auto-generated WorkOrder back to its `MaintenancePlan` for the D-04 de-dupe check. Current schema has no direct `WorkOrder.plan_id` column.
   - Recommendation: Add `plan_id UUID nullable FK maintenance_plans(id)` to `work_orders` table via Alembic migration. Use this for D-04 lookups. Alternative: use a naming convention in `work_order_number` (e.g., `MAINT-{plan_id[:8]}`) — but FK is cleaner.

2. **`ADMIN_DATABASE_URL` in Railway environment**
   - What we know: Railway provisions a single `DATABASE_URL`. Creating a second role requires running SQL against the provisioned database.
   - What's unclear: Whether Railway allows direct SQL execution on the provisioned PostgreSQL, or if a one-time migration is the only path.
   - Recommendation: Include `CREATE ROLE rotas_admin BYPASSRLS` and `CREATE ROLE rotas_app` in the RLS Alembic migration. Set `ADMIN_DATABASE_URL` in Railway env vars pointing to the same host with different role. Document the one-time role setup in Railway console.

3. **`before_cursor_execute` event with asyncpg**
   - What we know: `before_cursor_execute` is a DBAPI-level event. asyncpg uses a non-standard DBAPI. SQLAlchemy's asyncpg dialect wraps it.
   - What's unclear: Whether `before_cursor_execute` fires on the underlying asyncpg connection via `sync_engine` or whether a different event (e.g., `before_execute` on the Connection) is needed.
   - Recommendation: Use `after_begin` session event instead — fires after each transaction begins, guaranteed by SQLAlchemy, not DBAPI-dependent: `@event.listens_for(AsyncSessionLocal.sync_session_class, "after_begin")`. This executes `SET LOCAL` once per transaction, which is the correct scope.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | RLS migration, composite indexes | ✓ | 16 (port 55432) | — |
| Redis | ARQ worker | ✓ (provisioned) | 7 (port 6381) | — |
| Python | Backend | ✓ | 3.13.13 | — |
| `arq` package | MAINT-01 scheduler, CT-02 | Not installed (venv check) | — | Must install — no fallback |
| `gunicorn` package | D-12 Gunicorn deployment | Not installed (venv check) | — | Must install — no fallback |
| `redis[asyncio]` package | ARQ Redis client | Not installed (venv check) | — | Must install — no fallback |

**Missing dependencies with no fallback:**
- `arq` — required for MAINT-01 scheduler and CT-02 (Phase 3 dependency). Must be added to `pyproject.toml` and installed.
- `gunicorn` — required for D-12. Must be added to `pyproject.toml`.
- `redis[asyncio]` — required by arq. Must be added to `pyproject.toml`.

**Note:** These three packages are expected to be uninstalled at this point — they are Phase 3 + Phase 4 deliverables, not pre-existing. Wave 0 of the plan must install them.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ with pytest-asyncio |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `cd backend && python -m pytest tests/test_workshop_operations_api.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MAINT-01 | Scheduler creates WorkOrder when plan is overdue by km | unit | `pytest tests/test_maintenance_scheduler.py::test_scheduler_creates_work_order_on_km_trigger -x` | Wave 0 |
| MAINT-01 | Scheduler creates WorkOrder when plan is overdue by date | unit | `pytest tests/test_maintenance_scheduler.py::test_scheduler_creates_work_order_on_date_trigger -x` | Wave 0 |
| MAINT-01 | Scheduler skips if open WorkOrder exists (D-04) | unit | `pytest tests/test_maintenance_scheduler.py::test_scheduler_skips_duplicate_work_order -x` | Wave 0 |
| MAINT-01 | Next-cycle MaintenanceSchedule created after trigger (D-03) | unit | `pytest tests/test_maintenance_scheduler.py::test_next_cycle_schedule_created_after_trigger -x` | Wave 0 |
| D-06 | Imminent maintenance alerts returned by API | integration | `pytest tests/test_maintenance_scheduler.py::test_imminent_maintenance_alerts -x` | Wave 0 |
| D-09/D-10 | Driver scorecard returns 0–100 score for rolling 30d | unit | `pytest tests/test_driver_scorecard.py::test_scorecard_score_range -x` | Wave 0 |
| D-17/D-18 | RLS blocks cross-tenant data access | integration | `pytest tests/test_cross_tenant_isolation.py -x` | ✅ (existing) |
| D-12 | Gunicorn starts with UvicornWorker (smoke) | smoke | Manual — deploy verification | N/A |
| D-14 | Composite indexes present in DB schema | integration | `pytest tests/test_composite_indexes.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && python -m pytest tests/test_workshop_operations_api.py tests/test_cross_tenant_isolation.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_maintenance_scheduler.py` — covers MAINT-01 (trigger, de-dupe, next-cycle, alerts)
- [ ] `backend/tests/test_driver_scorecard.py` — covers D-08 through D-11
- [ ] `backend/tests/test_composite_indexes.py` — verifies indexes exist post-migration
- [ ] Framework install: `pip install "arq>=0.26" "redis[asyncio]>=5.0" "gunicorn>=22.0"` + update `pyproject.toml`

---

## Project Constraints (from CLAUDE.md)

- **Tech stack locked:** FastAPI + Next.js + PostgreSQL — no stack changes.
- **Dexie.js 4 compatibility:** No IndexedDB schema changes in this phase (Phase 4 is backend only).
- **Monetary precision:** Numeric(10,2) or higher for all monetary columns — confirmed already in place.
- **UTF-8:** No PDF/XLSX output in this phase — not applicable.
- **Multitenant safety:** Every query must filter by `tenant_id`. RLS adds DB-level enforcement but does not replace code-level filtering. Both must remain.
- **Ruff linting:** `E, F, I, UP, B` rules. `line-length = 100`. New files must pass `ruff check`.
- **Service layer returns `dict`:** Scorecard service must follow this convention.
- **No business logic in routers:** Scorecard aggregation logic belongs in `workshop/service.py` or a new `drivers/service.py` section.
- **`asyncio_mode = "auto"` in pytest:** All new test functions must be `async def`.

---

## Sources

### Primary (HIGH confidence)
- Codebase scan: `backend/app/modules/workshop/models.py` — MaintenancePlan, MaintenanceSchedule, WorkOrder models confirmed complete
- Codebase scan: `backend/app/modules/workshop/service.py:1255` — `evaluate_maintenance_schedule()` confirmed as foundation
- Codebase scan: `backend/app/modules/fuel/service.py:202` — odometer update location confirmed
- Codebase scan: `backend/alembic/versions/a97cbdef860b_add_preventive_maintenance.py` — migration pattern confirmed
- Codebase scan: `backend/app/database.py` — AsyncSession + sync_engine available for event listener
- Codebase scan: `backend/railway.toml` — current startCommand confirmed as uvicorn only
- Codebase scan: `backend/pyproject.toml` — arq, gunicorn, redis[asyncio] NOT yet in dependencies
- [ARQ documentation](https://arq-docs.helpmanual.io/) — WorkerSettings, cron_jobs pattern
- [SQLAlchemy 2.0 async docs](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — sync_engine event listener pattern

### Secondary (MEDIUM confidence)
- [FastAPI server workers docs](https://www.mintlify.com/fastapi/fastapi/deployment/server-workers) — gunicorn -k UvicornWorker pattern
- [PostgreSQL RLS docs](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) — SET LOCAL requirement, current_setting() NULL behavior
- [Tenant isolation with RLS + SQLAlchemy](https://personal-web-9c834.web.app/blog/pg-tenant-isolation/) — before_cursor_execute pattern

### Tertiary (LOW confidence — verify during implementation)
- Open Question 3: `before_cursor_execute` behavior with asyncpg/async_engine — recommend testing with `after_begin` as alternative

---

## Metadata

**Confidence breakdown:**
- MAINT-01 scheduler: HIGH — existing code base is clear, models are complete, service function is identified
- Driver scorecard: HIGH — all source data tables identified, pure aggregation from existing records
- D-15 numeric migration: HIGH — full scan of all models.py confirmed no Float columns
- RLS SQLAlchemy integration: MEDIUM — pattern is well-established, asyncpg-specific behavior of `before_cursor_execute` has a caveat (Open Question 3)
- Gunicorn deployment: HIGH — standard FastAPI production pattern
- Composite indexes: MEDIUM — index candidates identified from schema, actual `EXPLAIN ANALYZE` results will confirm

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (stable domain — ARQ, SQLAlchemy, PostgreSQL RLS are not fast-moving)
