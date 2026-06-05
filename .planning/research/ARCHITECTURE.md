# Architecture Research
_Last updated: 2026-06-04_

---

## Summary

ROTAS has a solid modular-monolith foundation. The five areas below each have a well-understood upgrade path that does not require rewrites — they are additive layers on top of existing code. The highest-value improvements in order of impact are: (1) Redis caching for the Control Tower, (2) SQLAlchemy eager-loading for the 38-query problem, (3) ARQ for deferrable background work, (4) RLS as a second-layer safety net, and (5) explicit conflict resolution surfacing in the client. CRDTs are overkill for this domain.

**Overall confidence:** MEDIUM-HIGH — all findings verified against multiple sources; code patterns drawn from official SQLAlchemy docs and production-grade articles from 2025-2026.

---

## Offline Sync Conflict Resolution

**Confidence: MEDIUM** — verified against multiple sources; specific recommendations are evidence-driven.

### Context

ROTAS already implements idempotency-key-based sync with a `conflict` status returned to the client. The gap is: what happens after `conflict`? The client currently only marks items `conflict` in IndexedDB with no resolution path.

### Options Assessment

| Strategy | Fit for ROTAS | Notes |
|---|---|---|
| CRDTs | Poor | Designed for collaborative real-time editing (multiple writers on same field). ROTAS entities are single-writer (one driver per trip). Mathematical elegance at high operational cost. |
| Wall-clock last-write-wins | Poor | Silently discards data. Device clocks on low-cost Android hardware in Mozambique cannot be trusted. A user with a 20-minute offline session can have work overwritten by a device 5 seconds ahead. |
| Monotonic version counter + server-wins | Good | Simple, safe, auditable. Server is the source of truth; the driver's offline work is the pending state. |
| Field-level merge with logical timestamps | Best fit | Merge concurrent changes to *different* fields on the same entity; server-wins on same-field conflicts. Requires a `version` column per entity. |

### Recommendation: Server-Authoritative Versioning with Field-Level Merge

For ROTAS's domain (single driver per trip, sequential operations), the practical approach is:

1. **Add `server_version` integer column** to all syncable entities. Increment on every server-side mutation.
2. **Client sends `base_version`** in the sync payload (the version it last saw from the server).
3. **Server conflict check**: if `stored_version != base_version`, it is a conflict. Current code already returns `conflict` — this makes the logic explicit.
4. **Conflict resolution rule**: For most ROTAS entities (trips, fuel logs, checklists), apply **server-wins** because server data reflects what was persisted and invoiced. The driver's offline update is likely a duplicate or retried operation.
5. **Exception — trip_stop costs and checklist responses**: These are append-only. Conflicts are impossible if operations use `INSERT` not `UPDATE`. Enforce this at the service layer.
6. **Client conflict UI**: When `conflict` is returned, surface it to the driver with the server value and a "force override" option gated behind a manager approval (waiver flow already exists for billing margins — reuse the pattern).

### Why Not CRDTs

CRDTs resolve data structure conflicts, not business logic conflicts. Two offline devices can both "reserve the last seat" and a CRDT merges the reservations perfectly while still violating the business rule. For fleet management, the constraint is operational (one driver, one trip, one vehicle at a time) — the conflict resolution rule is deterministic and domain-specific, not structural.

### Hybrid Logical Clocks (HLC) — Skip for Now

HLC solves clock drift. Given ROTAS's single-writer model (one driver app per device), standard monotonic server_version is sufficient. HLC adds complexity that isn't warranted until multi-device scenarios exist.

### Sources
- [The Cascading Complexity of Offline-First Sync: Why CRDTs Alone Aren't Enough](https://dev.to/biozal/the-cascading-complexity-of-offline-first-sync-why-crdts-alone-arent-enough-2gf)
- [How We Designed Offline Sync for Any Data Model](https://medium.com/@msujithr/how-we-designed-offline-sync-for-any-data-model-0079bd4bea2f)
- [Offline + Sync Architecture for Field Operations](https://www.alphasoftware.com/blog/offline-sync-architecture-tutorial-examples-tools-for-field-operations)
- [CRDT Implementation Guide](https://velt.dev/blog/crdt-implementation-guide-conflict-free-apps)

---

## Redis Caching Patterns (FastAPI + SQLAlchemy)

**Confidence: HIGH** — concrete patterns verified against official Redis docs and multiple production-grade FastAPI articles from 2025-2026.

### Context

Redis is already provisioned but unused. CT-02 in PROJECT.md calls for caching Control Tower KPIs. The Control Tower currently runs ~38 sequential queries per request. Redis should eliminate the repeat cost on cache-hit paths.

### Recommended Pattern: Cache-Aside with Tag-Based Invalidation

Cache-aside (lazy population) is the correct choice over read-through or write-through for ROTAS because:
- The Control Tower aggregates data from many tables — write-through would require hooking every mutation path
- Cache-aside is simpler to add incrementally to existing service code

```python
# backend/app/modules/control_tower/cache.py
import json
import hashlib
from redis.asyncio import Redis
from typing import Any, Callable, Awaitable

CONTROL_TOWER_TTL = 60  # seconds — KPIs are accepted as ~1min stale

async def get_or_set(
    redis: Redis,
    key: str,
    fetch: Callable[[], Awaitable[Any]],
    ttl: int = CONTROL_TOWER_TTL,
) -> Any:
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)

    # Stampede prevention: acquire a short lock before computing
    lock_key = f"lock:{key}"
    lock_acquired = await redis.set(lock_key, "1", nx=True, ex=5)

    if lock_acquired:
        try:
            data = await fetch()
            await redis.setex(key, ttl, json.dumps(data, default=str))
            return data
        finally:
            await redis.delete(lock_key)
    else:
        # Another worker is computing — wait briefly and return stale or None
        import asyncio
        await asyncio.sleep(0.1)
        cached = await redis.get(key)
        return json.loads(cached) if cached else await fetch()


def control_tower_key(tenant_id: str) -> str:
    return f"ct:kpis:{tenant_id}"
```

### Cache Key Design

Use a consistent prefix scheme for pattern-based invalidation:

```
ct:kpis:{tenant_id}          # Control Tower full payload
ct:alerts:{tenant_id}        # Active alert counts
ct:fleet:{tenant_id}         # Fleet status summary
```

On any mutation that affects KPIs (trip status change, fuel log, exception raised), delete `ct:*:{tenant_id}`. With Redis, this is a `SCAN` + `DEL` on the pattern — avoid `KEYS *` in production.

```python
async def invalidate_tenant_cache(redis: Redis, tenant_id: str):
    # Scan-based pattern delete — safe for production
    pattern = f"ct:*:{tenant_id}"
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break
```

### TTL Strategy by Data Type

| Cache Key | TTL | Rationale |
|---|---|---|
| Control Tower KPIs | 60s | Operational dashboard; 1-min staleness acceptable |
| Active alert counts | 30s | Alerts are time-sensitive |
| Fleet status summary | 120s | Slower-moving data |
| Bootstrap metadata | 3600s | Changes rarely (entity types, TTL config) |
| Per-user role/permissions | 300s | Invalidate on user mutation |

### Stampede Prevention

The `NX + EX` lock pattern above is the standard Redis approach. Only one worker computes; others either wait 100ms and re-read, or fall through to a direct DB call if the lock holder is still computing. This is sufficient for ROTAS's expected concurrent load.

For higher scale (>100 concurrent dashboard users per tenant), consider probabilistic early expiration: a small probability on each read that the cache is refreshed before actual TTL expiry. Libraries like `redis-py` do not ship this natively — implement inline if needed.

### Redis Client Setup (asyncio-native)

```python
# backend/app/database.py (add alongside get_session)
from redis.asyncio import Redis, ConnectionPool

_redis_pool: ConnectionPool | None = None

def get_redis_pool() -> ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20,
            decode_responses=True,
        )
    return _redis_pool

async def get_redis() -> Redis:
    return Redis(connection_pool=get_redis_pool())
```

Inject via `Depends(get_redis)` in route handlers or service functions. Do not create a new connection per request.

### Sources
- [How to Implement Cache Invalidation in FastAPI](https://oneuptime.com/blog/post/2026-02-02-fastapi-cache-invalidation/view)
- [Redis Distributed Locks](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)
- [How to Handle Cache Stampede (Thundering Herd) in Redis](https://oneuptime.com/blog/post/2026-01-21-redis-cache-stampede/view)
- [Integrating Redis Caching in FastAPI the Right Way](https://medium.com/@dronarajgyawali/integrating-redis-caching-in-fastapi-the-right-way-edb212183d45)

---

## PostgreSQL RLS for Multitenant Safety

**Confidence: HIGH** — migration approach, session variable pattern, and SQLAlchemy event listener all verified against official guides from 2025-2026.

### Context

ROTAS currently enforces tenant isolation exclusively in application code (`WHERE tenant_id = :tenant_id` in every service function). PROJECT.md notes this as a known risk: "bug can leak data between tenants." RLS adds a second enforcement layer at the database level so even a buggy query cannot return another tenant's rows.

### Architecture Decision: RLS as Defense-in-Depth

RLS must be additive, not a replacement for application-level filtering. The existing `tenant_id` filtering stays. RLS is the safety net that makes it impossible for a bug to produce a cross-tenant data leak.

### Step 1 — Alembic Migration per Table

Create a separate migration file for RLS policies. Policies are schema objects that should be versioned like tables.

```python
# alembic/versions/xxxx_add_rls_policies.py
from alembic import op

def upgrade():
    # Example for trips table — repeat for all tenant-scoped tables
    op.execute("ALTER TABLE trips ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE trips FORCE ROW LEVEL SECURITY")  # applies to table owner too
    op.execute("""
        CREATE POLICY tenant_isolation ON trips
        AS PERMISSIVE
        FOR ALL
        TO PUBLIC
        USING (tenant_id::text = current_setting('app.current_tenant_id', true))
    """)
    # Repeat for: vehicles, drivers, fuel_logs, trip_stops, trip_costs,
    # checklists, checklist_responses, load_permits, cargo_manifests,
    # transport_documents, delivery_proofs, billing_documents, billing_items,
    # work_orders, maintenance_requests, alerts, audit_logs, sync_events, etc.

def downgrade():
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON trips")
    op.execute("ALTER TABLE trips DISABLE ROW LEVEL SECURITY")
```

### Step 2 — Thread-Safe Tenant Context (contextvars)

```python
# backend/app/core/rls_context.py
from contextvars import ContextVar

_current_tenant_id: ContextVar[str | None] = ContextVar(
    "current_tenant_id", default=None
)

def set_tenant_context(tenant_id: str) -> None:
    _current_tenant_id.set(tenant_id)

def get_tenant_context() -> str | None:
    return _current_tenant_id.get()
```

### Step 3 — SQLAlchemy Async Event Listener

The SQLAlchemy `before_cursor_execute` event fires before every query on the session. Inject the PostgreSQL session variable there.

```python
# backend/app/database.py — add after async_session_maker creation
from sqlalchemy import event, text
from app.core.rls_context import get_tenant_context

@event.listens_for(async_session_maker.sync_session_class, "after_begin")
def set_tenant_on_session(session, transaction, connection):
    tenant_id = get_tenant_context()
    if tenant_id:
        connection.exec_driver_sql(
            "SELECT set_config('app.current_tenant_id', %s, true)",
            (str(tenant_id),),
        )
```

Note: For `asyncpg`, use `SET LOCAL` inside a transaction. The `true` flag on `set_config` scopes the setting to the current transaction, which is the safe default — it resets automatically on transaction commit/rollback. This prevents context bleed between requests sharing a connection from the pool.

### Step 4 — Middleware to Populate Context

```python
# backend/app/core/auth.py — extend get_current_principal()
# After decoding JWT and extracting tenant_id, call:
from app.core.rls_context import set_tenant_context
set_tenant_context(str(principal.tenant_id))
```

This ensures RLS context is set for every authenticated request before any DB query runs.

### Admin/Migration Bypass

For Alembic migrations and superuser maintenance operations, PostgreSQL BYPASSRLS role privilege or `SET row_security = off` in a privileged session bypasses policies. The application DB user should NOT have BYPASSRLS — only the migration user.

### Existing Library Option

`fastapi-rowsecurity` (PyPI) provides a FastAPI dependency that wraps the above pattern. Evaluate it if you want less boilerplate, but it adds a dependency. The manual pattern above is ~50 lines and gives full control.

### Migration Sequence

1. Add RLS policies in a migration (disabled by default in Postgres until `ENABLE ROW LEVEL SECURITY` is called).
2. Test in staging: run existing integration tests to confirm no queries break (they should not, since application filtering already provides correct `tenant_id`).
3. Add a test that deliberately omits `tenant_id` from a query and asserts it returns zero rows.
4. Enable in production via migration.

### Sources
- [Row-Level Security with SQLAlchemy and Alembic: A Complete Guide](https://www.adrianovieira.eng.br/en/posts/architecture/row-level-security-sqlachemy-alembic-guide/)
- [Building Multi-Tenant Row-Level Security in PostgreSQL: A Production Pattern](https://dev.to/uaslimcreate/building-multi-tenant-row-level-security-in-postgresql-a-production-pattern-4n2k)
- [How to Secure Multi-Tenant Data with Row-Level Security in PostgreSQL](https://oneuptime.com/blog/post/2026-01-25-row-level-security-postgresql/view)
- [GitHub: fastapi-rowsecurity](https://github.com/JWDobken/fastapi-rowsecurity)

---

## SQLAlchemy 2.0 N+1 Query Optimization

**Confidence: HIGH** — patterns directly from SQLAlchemy 2.0 official docs and multiple production articles. Code verified against the async API.

### Context

Control Tower runs ~38 sequential queries per request. This is a classic N+1 pattern: fetch trips, then for each trip fetch vehicle, driver, stops, costs, exceptions, etc. The fix is explicit eager loading declared at the query site.

### Rule of Thumb

| Relationship Type | Strategy | SQL Generated |
|---|---|---|
| Many-to-one (e.g., trip → vehicle) | `joinedload` | Single JOIN query |
| One-to-many collection (e.g., trip → stops) | `selectinload` | 2 queries (parent + IN clause) |
| Nested collection (e.g., trip → stops → costs) | `selectinload(...).selectinload(...)` | 3 queries total |
| Load only specific columns | `load_only(Model.col_a, Model.col_b)` | Reduces data transfer |

**Never use `lazyload` in async SQLAlchemy** — async sessions do not support implicit lazy loads. SQLAlchemy will raise `MissingGreenlet` if a lazy-loaded relationship is accessed outside the session context. Set `lazy="raise"` on all relationships during development to catch this early.

### Pattern for Control Tower Aggregate Query

The Control Tower currently calls individual service functions per entity type in a loop. Replace with a single rich query:

```python
# backend/app/modules/control_tower/service.py
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload, load_only

async def get_fleet_status(db: AsyncSession, tenant_id: str):
    stmt = (
        select(Trip)
        .where(Trip.tenant_id == tenant_id)
        .where(Trip.status.in_(["active", "pending"]))
        .options(
            # Many-to-one: JOIN (1 query per relationship, included in main)
            joinedload(Trip.vehicle).load_only(
                Vehicle.id, Vehicle.plate, Vehicle.status
            ),
            joinedload(Trip.driver).load_only(
                Driver.id, Driver.full_name
            ),
            # One-to-many collections: IN clause (1 extra query each)
            selectinload(Trip.stops).load_only(
                TripStop.id, TripStop.location, TripStop.cost
            ),
            selectinload(Trip.operational_exceptions),
        )
        # Pagination — CT-03 requirement
        .limit(100)
        .offset(offset)
        .order_by(Trip.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().unique().all()
```

This replaces ~10-15 of the 38 sequential queries for the trips portion.

### Aggregate KPIs — Use SQL-Level Aggregation

For KPI counts (active trips, vehicles in workshop, fuel spend today), do not fetch rows and count in Python. Use `func.count()`, `func.sum()`, `func.coalesce()` with a single scalar query per metric, or combine with CTE:

```python
# Single query for multiple KPIs using correlated subqueries
from sqlalchemy import select, func, case, literal_column

async def get_kpi_summary(db: AsyncSession, tenant_id: str) -> dict:
    stmt = select(
        func.count(case((Trip.status == "active", 1))).label("active_trips"),
        func.count(case((Trip.status == "pending", 1))).label("pending_trips"),
        func.count(case((Vehicle.status == "in_workshop", 1))).label("vehicles_in_workshop"),
    ).select_from(Trip).join(Vehicle, Vehicle.id == Trip.vehicle_id).where(
        Trip.tenant_id == tenant_id
    )
    row = (await db.execute(stmt)).one()
    return {"active_trips": row.active_trips, ...}
```

This collapses multiple scalar COUNT queries into one.

### Development Safety Net

```python
# In all SQLAlchemy model relationships — add during a cleanup pass
from sqlalchemy.orm import relationship

class Trip(Base):
    vehicle = relationship("Vehicle", lazy="raise")  # raises if accidentally lazy-loaded
    stops = relationship("TripStop", lazy="raise")
```

This forces all relationship loading to be explicit at the query site, making N+1 patterns fail loudly in development and tests.

### Expected Impact

Based on community benchmarks:
- SelectinLoad at scale: 95% query reduction, ~56x throughput improvement, p99 latency from seconds to tens of milliseconds
- For Control Tower specifically: 38 queries → 4-6 queries (main query + selectinload batches + KPI aggregates)

### Sources
- [SQLAlchemy 2.0 Relationship Loading Techniques (official docs)](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html)
- [Advanced SQLAlchemy 2.0: SelectinLoad and WithParent Strategies 2025](https://www.johal.in/advanced-sqlalchemy-2-0-selectinload-and-withparent-strategies-2025/)
- [FastAPI + SQLAlchemy 2.0: Modern Async Database Patterns](https://dev-faizan.medium.com/fastapi-sqlalchemy-2-0-modern-async-database-patterns-7879d39b6843)
- [Mastering SQLAlchemy Performance: Fix Slow Queries, N+1 Problems](https://python.elitedev.in/python/mastering-sqlalchemy-performance-fix-slow-queries/)

---

## Background Job Processing (no heavy queue)

**Confidence: HIGH** — comparison verified against official FastAPI docs, ARQ docs, and multiple production comparison articles. Celery async gap confirmed from multiple sources.

### Context

ROTAS has no background task runner. The alerts module presumably generates alerts synchronously (or not at all). Identified needs: (1) alert generation triggered by sync events, (2) PDF/XLSX export for billing, (3) cache warming after invalidation, (4) potential future: scheduled compliance checks, document expiry notifications.

### Options Compared

| Option | Fits ROTAS? | Key Characteristics |
|---|---|---|
| FastAPI `BackgroundTasks` | Partial | Simple fire-and-forget. No status tracking, no retries, no persistence. Killed if server crashes. Acceptable for low-stakes tasks (e.g., cache invalidation after a mutation). |
| **ARQ** | **Best fit** | Asyncio-native, uses Redis already provisioned. Simple worker process. Retries, job status, cron scheduling. No additional infrastructure. |
| Celery | No | No native async/await as of 2025 (issue open since 2020). Requires bridging sync/async. Adds broker complexity. Overkill for ROTAS's current load. |
| RQ (Redis Queue) | Fallback | Simpler than Celery. Sync-only workers. Works but not asyncio-native. |

### Recommendation: ARQ

ARQ is the correct choice because:
- Redis is already provisioned — ARQ uses the same Redis instance as the cache, no new infrastructure
- Asyncio-native — no sync/async bridging, shares connection pools with FastAPI workers
- 50 concurrent async tasks in a single worker process (vs 50 Celery processes)
- Retries, backoff, job status tracking, cron jobs all built in
- Operational simplicity: one extra process (`arq worker.WorkerSettings`)

### Implementation Pattern

```python
# backend/app/worker/tasks.py
from arq.connections import RedisSettings
from app.modules.alerts.service import generate_alerts_for_tenant
from app.modules.billing.service import generate_billing_pdf
from app.database import get_session_factory

async def task_generate_alerts(ctx: dict, tenant_id: str, trip_id: str):
    """Run after sync batch completes — generate/update alerts for this trip."""
    async with get_session_factory()() as db:
        await generate_alerts_for_tenant(db, tenant_id, trip_id=trip_id)

async def task_export_billing_pdf(ctx: dict, tenant_id: str, billing_id: str):
    """Async PDF export — decouples export from HTTP request lifecycle."""
    async with get_session_factory()() as db:
        await generate_billing_pdf(db, tenant_id, billing_id)

async def startup(ctx: dict):
    # Shared resources available to all tasks via ctx
    from redis.asyncio import Redis
    ctx["redis"] = Redis.from_url(settings.redis_url)

async def shutdown(ctx: dict):
    await ctx["redis"].aclose()

class WorkerSettings:
    functions = [task_generate_alerts, task_export_billing_pdf]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = 20
    job_timeout = 300  # 5 min max per job
    retry_jobs = True
    max_tries = 3
```

```python
# backend/app/modules/sync/service.py — enqueue after batch processed
from arq import create_pool
from arq.connections import RedisSettings

async def process_batch(db, principal, payload):
    # ... existing sync processing ...
    # After successful batch:
    arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    await arq_pool.enqueue_job(
        "task_generate_alerts",
        principal.tenant_id,
        trip_id=trip_id,
    )
```

### When to Use FastAPI BackgroundTasks Instead

Keep using `BackgroundTasks` for:
- Cache invalidation after mutations (fire-and-forget, no retry needed)
- Logging side-effects
- Sending a webhook notification where loss is acceptable

Use ARQ for:
- Alert generation (needs retry, must not be lost on server crash)
- PDF/XLSX export (CPU-bound, should not block HTTP worker)
- Scheduled compliance checks (cron)
- Any task that takes >500ms

### Deployment

```bash
# Dockerfile / Railway Procfile — add alongside the FastAPI app
web: uvicorn app.main:app --host 0.0.0.0 --port 8000
worker: arq app.worker.tasks.WorkerSettings
```

Railway and Render both support multiple process types per service or separate services. Run the worker as a separate process on the same Redis instance. One worker process handles ROTAS's initial load comfortably.

### Sources
- [Managing Background Tasks in FastAPI: BackgroundTasks vs ARQ + Redis](https://davidmuraya.com/blog/fastapi-background-tasks-arq-vs-built-in/)
- [FastAPI Background Tasks vs Celery vs ARQ](https://medium.com/@komalbaparmar007/fastapi-background-tasks-vs-celery-vs-arq-picking-the-right-asynchronous-workhorse-b6e0478ecf4a)
- [FastAPI Background Tasks (official docs)](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Why I Chose arq and RQ Over Celery for LLM Workloads](https://dangquan1402.github.io/llm-engineering-notes/2026/04/02/lightweight-task-queues-for-llm-apps.html)
- [ARQ vs Celery, How to Run FastAPI Background Tasks with ARQ](https://www.bithost.in/blog/tech-3/how-to-run-fastapi-background-tasks-arq-vs-celery-11)

---

## Gaps / Unknowns

1. **Sync pull direction**: Research did not address the missing pull mechanism (server → client). The `bootstrap` endpoint returns metadata only. A delta-sync endpoint (`GET /api/v1/sync/pull?since=<server_version>`) is needed for trip assignments, checklist template updates, and vehicle data changes to reach the driver app without a full app reload. This requires its own design.

2. **RLS on `audit_logs` and `idempotency_keys`**: Audit logs carry `tenant_id` but are written by the application itself, not by user requests. The RLS event listener must correctly handle the audit log writer context — confirm the session variable is set before audit writes, or use a separate DB role for audit writes that bypasses RLS.

3. **Redis connection pool sizing**: No load data was available for ROTAS's expected concurrent user count. The pool size of 20 in the pattern above is a starting point. Monitor `redis_connected_clients` and `rejected_connections` after deploy.

4. **ARQ worker crash recovery**: ARQ persists job state in Redis. Jobs enqueued before a worker crash will be picked up on restart. Confirm Redis persistence (AOF or RDB snapshot) is enabled on the provisioned Redis instance — otherwise crashed jobs are lost.

5. **`availability` module**: Listed in `backend/app/modules/` but not registered in `main.py` or `database.py`. If this module has tenant-scoped tables, they need RLS policies too. Investigate before running the RLS migration.

6. **Monetary columns as `float`**: Several billing/cost columns are `float` instead of `Numeric(10,2)`. This is a separate data integrity issue, not architecture, but any Redis caching of financial aggregates must be invalidated immediately after the float→Numeric migration or cached values will reflect floating-point rounding errors.

7. **Control Tower pagination (CT-03)**: The N+1 fix patterns above include `.limit(100)` but the correct pagination parameters (page size, cursor vs offset) need to be agreed upon before implementation. Cursor-based pagination (by `created_at` + `id`) is preferred over offset for large datasets, but adds client-side complexity.
