# Phase 3: Manager Dashboard + Reporting Layer — Research

**Researched:** 2026-06-05
**Domain:** FastAPI query optimization / Redis caching / ARQ background jobs / fpdf2 PDF / openpyxl XLSX / Next.js 14 + Tailwind 4 + shadcn/ui migration / KPI analytics / waiver workflow
**Confidence:** HIGH (backed by codebase inspection + verified library docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**UI Framework — Tailwind + shadcn/ui Migration**
- D-01: Introduce Tailwind CSS in `apps/manager/`. Install `tailwind.config.ts`, `postcss.config.js`, configure `globals.css` with Tailwind directives.
- D-02: Install shadcn/ui as base component library. Use `Button`, `Dialog`, `Table`, `Badge`, `Card`, `Select`, `DatePicker` in new KPI, export, and waiver components.
- D-03: Migrate ALL existing manager components to Tailwind — `ControlTowerOverview`, `CostMarginBoard`, `FleetComplianceBoard`, `FuelControlBoard`, `FleetHistoryBoard`, `BillingTripActions`, `TransportCargoActions`, `TransportCargoBoard`, `DriverDespachoTableAdmin`, `SidebarLayout`, and existing pages. Custom CSS classes (`tower-metric`, `worklist`, `fleet-fact`, etc.) replaced by Tailwind.
- D-04: Custom CSS from `globals.css` keeps `:root` vars (`--nav`, `--soft`, `--ink`, ...) but component classes are migrated to Tailwind. Vars available as `bg-[var(--nav)]` etc.

**KPI Dashboard (RPT-01)**
- D-05: New `/analytics` page in manager sidebar. Separate route from Control Tower — CT is daily operational view, /analytics is strategic fleet view.
- D-06: Interactive filters: period dropdown (this month, last 3 months, custom range) + vehicle or driver filter. Backend needs parameterized queries by `period_start`, `period_end`, `vehicle_id?`, `driver_id?`.
- D-07: KPIs to show: cost-per-km per vehicle, fleet utilization % (active trips / total vehicles), fuel consumption L/100km rolling 30 days, trip summary per driver. All filtered by `tenant_id` — mandatory.

**Export PDF/XLSX (BILL-01, BILL-02)**
- D-08: Exports are async ARQ jobs. Flow: manager clicks "Export PDF/XLSX" → frontend calls endpoint that enqueues ARQ job and returns `job_id` → frontend polls `GET /api/v1/jobs/{job_id}/status` → when status is `done`, shows "Download" button.
- D-09: File delivery: save file to `LOCAL_UPLOAD_DIR` and serve via authenticated endpoint `GET /api/v1/jobs/{job_id}/download`. URL with `tenant_id` in path for isolation. No public URL.
- D-10: PDF uses `fpdf2 >= 2.8.7` with `DejaVuSans.ttf` embedded. XLSX uses `openpyxl`. Both generated in ARQ worker, never blocking HTTP response.

**Waiver for Negative Margin (BILL-03)**
- D-11: Inline waiver flow in billing queue: trips with `margin < 0` show "Margem negativa" badge and "Solicitar waiver" button (available to any manager with manager, admin, or owner role).
- D-12: Clicking "Solicitar waiver" opens modal (shadcn/ui `Dialog`) with: margin detail, mandatory justification field, "Submeter pedido" button. Creates waiver record with status `pending_approval`.
- D-13: Separate approval modal (visible only to owner/admin): shows manager justification + trip financial detail + "Aprovar" / "Rejeitar" buttons. On approve, `waiver_id` is attached to trip and it can enter billing cycle.
- D-14: RBAC: `manager` can request. `owner` and `admin` can approve or reject. `viewer` cannot do anything. Aligns with existing RBAC.

**Redis Cache (CT-02)**
- D-15: Install `redis[asyncio]` in `backend/pyproject.toml`. Cache-aside with key `ct:kpis:{tenant_id}`, TTL 60s. Document alert keys with TTL 30s.
- D-16: ARQ worker deployed as separate process on Railway. Worker performs async KPI refresh in background.
- D-17: Cache stampede lock via `NX + EX` to prevent multiple workers from recalculating simultaneously.

**Control Tower (CT-01, CT-03)**
- D-18: Replace ~38 sequential queries with `joinedload` (many-to-one: trip → vehicle/driver), `selectinload` (one-to-many: trip → stops), `func.count()` SQL-level for KPI scalars. Target: 4-6 queries for the full payload.
- D-19: Set `lazy="raise"` on SQLAlchemy relationships in dev config to detect accidental lazy loads.
- D-20: Pagination on all Control Tower queues: `page` and `page_size` with default cap of 50. No unbounded queries.
- D-21 (inherited from Phase 1): Each batch of query rewrites must pass cross-tenant regression tests. This is the highest-risk window for cross-tenant data leaks.

**Document Alerts (RPT-02)**
- D-22: Proactive alert panel shows vehicles and drivers with documents expiring in the next 30 days. Displayed in Control Tower (already has `vehicleDocumentsExpiring` and `driverDocumentsExpiring` in API) and also as highlighted section on `/analytics` page.
- D-23: Three-level threshold: 30 days (orange), 15 days (light red), 7 days (red). Display only in Phase 3 — push/email notifications are v2.

### Claude's Discretion
- Exact schema for waivers (`waivers` table vs field on `billing_items`)
- Number of ARQ workers and retry configuration
- File delivery method (D-09 as guidance)
- shadcn/ui animations/transitions
- Folder structure for new Tailwind components vs migrated existing components
- Design of job polling (interval, max attempts, error message if timeout)

### Deferred Ideas (OUT OF SCOPE)
- Email/WhatsApp notifications when documents are within X days — v2
- Driver scorecard (score composition) — Phase 4
- Public URL with signed URL for exports (S3/R2) — when R2 is configured in production
- WebSocket for real-time Control Tower updates — current architecture is polling, WS would be new infra
- PostgreSQL RLS as second isolation layer — Phase 4
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CT-01 | Replace ~38 sequential queries with aggregated queries using `selectinload`/`joinedload` and `func.count()` (target: 4-6 queries) | Codebase inspection confirms N+1 patterns; `_operational_close_queue` alone fires 2 per-row queries in a loop; SQLAlchemy 2.0 eager loading patterns verified |
| CT-02 | Redis cache for Control Tower KPIs — `redis[asyncio]` installed, cache-aside TTL 60s, `ct:kpis:{tenant_id}` namespace, ARQ worker | redis-py 8.0 + ARQ 0.28.0 versions confirmed; packages NOT yet in pyproject.toml; Redis server not currently running locally |
| CT-03 | Pagination on all Control Tower queues — no unbounded queries | Existing queue functions use `.limit(10)` hardcoded without page/page_size params; requires parameter extraction |
| BILL-01 | PDF export with full UTF-8 support — Mozambican names with diacritics rendered correctly | CRITICAL: existing `exporters.py` uses hand-rolled PDF with `latin-1` encoding — DOES NOT support UTF-8; must be replaced with `fpdf2 + DejaVuSans.ttf`; fpdf2 2.8.7 is latest |
| BILL-02 | XLSX export — value columns, dates, descriptions, totals formatted | CRITICAL: existing `exporters.py` uses hand-rolled XLSX XML/ZIP — must be replaced with `openpyxl 3.1.5` for proper formatting |
| BILL-03 | Negative margin waiver workflow — end-to-end, trip cannot enter billing without supervisor approval | Partial infrastructure exists: `OperationalWaiver` model in `operations/models.py` and `require_margin_governance()` in billing service; billing waiver needs dedicated status flow and frontend modal |
| RPT-01 | KPI dashboard — cost-per-km, fleet utilization, fuel consumption trends, trip summary per driver | New `/analytics` page and backend endpoint required; queries must be parametrized by period and optional filters; no existing analytics endpoint found |
| RPT-02 | Proactive document expiry alerts (30/15/7 days) — vehicles and drivers | Backend already returns `vehicle_documents_expiring` and `driver_documents_expiring` in CT payload; needs 3-level severity display in frontend and `/analytics` section |
</phase_requirements>

---

## Summary

Phase 3 transforms ROTAS from a data-collection tool into an operational management platform. The phase has three distinct tracks: (1) backend performance — eliminating N+1 queries in the Control Tower service and introducing Redis caching via ARQ workers; (2) reporting — replacing hand-rolled PDF/XLSX exporters with `fpdf2` and `openpyxl`, adding a `/analytics` KPI page, and implementing the negative margin waiver workflow; (3) frontend migration — installing Tailwind CSS 4 and shadcn/ui in `apps/manager/` and migrating all 18 existing components from custom CSS classes.

The most critical discovery from codebase inspection is that `exporters.py` already exists but uses hand-rolled PDF (raw PDF bytes, `latin-1` encoding) and hand-rolled XLSX (raw XML/ZIP). These implementations CANNOT handle UTF-8 (Mozambican names with diacritics will silently corrupt or crash). Both must be fully replaced. The `OperationalWaiver` model already exists in `operations/models.py` with the right shape, but the billing waiver workflow (`pending_approval` status, approval flow) is only partially wired — `require_margin_governance()` checks for active waivers but there are no endpoints to create or approve billing waivers.

For the frontend migration, the project uses Next.js 14 with React 18. The latest shadcn/ui CLI (shadcn@latest) defaults to Tailwind 4 and React 19. For this project's stack, `shadcn@2.3.0` must be used to stay on Tailwind v3 compatibility. The tailwind configuration pattern uses `tailwind.config.ts` with CSS variable extensions (not Tailwind 4's CSS-first approach).

**Primary recommendation:** Execute in three sequential waves: (1) CT query rewrite + Redis + pagination (CT-01/02/03), running cross-tenant regression tests after each query batch; (2) exporters replacement + waiver model + ARQ job infrastructure (BILL-01/02/03); (3) Tailwind/shadcn install + full component migration + new /analytics page + RPT-01/02 features.

---

## Standard Stack

### Core Backend Additions
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `redis[asyncio]` | 8.0.0 (PyPI latest) | Redis client with asyncio support for cache-aside pattern | `redis.asyncio` module provides async-native client; `[asyncio]` extra ensures hiredis for performance |
| `arq` | 0.28.0 (PyPI latest) | Async job queue built on Redis; asyncio-native | Designed for FastAPI/asyncio; uses same Redis as cache; avoids Celery/multiprocessing overhead |
| `fpdf2` | 2.8.7 (PyPI latest) | PDF generation with embedded TTF fonts | Only Python PDF library with proper Unicode TTF subsetting; `DejaVuSans.ttf` covers full Latin Extended range for Portuguese diacritics |
| `openpyxl` | 3.1.5 (PyPI latest) | XLSX generation with number formatting, bold headers | Standard Python XLSX library; handles `#,##0.00` format codes, font styles, column widths |

### Frontend Additions
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| `tailwindcss` | 4.3.0 (npm latest) | Utility-first CSS — replaces all custom CSS classes | Project decided on full migration; D-01 locked |
| `@tailwindcss/postcss` | 4.3.0 | PostCSS plugin for Tailwind 4 | Required by Next.js PostCSS pipeline |
| `shadcn` | 2.3.0 | Component CLI for Radix UI-based components | Must use 2.3.0 for Next.js 14 + React 18 + Tailwind v3 compatibility; latest CLI defaults to Tailwind 4 + React 19 |

**CRITICAL VERSION NOTE:** `shadcn@latest` (4.x+) targets Tailwind 4 + React 19 + Next.js 15. This project uses Next.js 14 + React 18. Use `npx shadcn@2.3.0 init` to stay on Tailwind v3 component outputs. Components generated by shadcn@2.3.0 use `tailwind.config.ts` pattern, not CSS-first Tailwind 4.

**Tailwind version decision:** The CONTEXT.md UI-SPEC shows `tailwind.config.ts` with `colors: { nav: 'var(--nav)', ... }` extension pattern. This is the Tailwind v3 pattern (config file with `theme.extend.colors`). Tailwind 4 removes `tailwind.config.ts`. Since shadcn@2.3.0 generates Tailwind v3 components, install `tailwindcss@3.x` not `tailwindcss@4.x`.

**Revised frontend install:**
```bash
npm install -D tailwindcss@3 postcss autoprefixer
npx tailwindcss@3 init -p
npx shadcn@2.3.0 init
```

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `DejaVuSans.ttf` | N/A (font file) | Unicode TTF for fpdf2 | Bundle in `backend/app/modules/billing/fonts/`; fpdf2 `add_font()` references this path |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `fpdf2` | `reportlab` | reportlab is more powerful but heavier; fpdf2 is simpler and has explicit DejaVuSans TTF subsetting |
| `openpyxl` | `xlsxwriter` | xlsxwriter is write-only and faster; openpyxl supports read/write and has simpler API for this use case |
| `arq` | `celery` | Celery requires separate broker setup; ARQ uses same Redis already provisioned; asyncio-native is cleaner with FastAPI |
| `shadcn@2.3.0` | `shadcn@latest` | Latest targets Tailwind 4 / React 19; project is on Next.js 14 / React 18 |

**Installation (backend):**
```bash
cd backend
pip install "redis[asyncio]>=7.4" "arq>=0.28" "fpdf2>=2.8.7" "openpyxl>=3.1"
# Then add to pyproject.toml dependencies
```

**Version verification (confirmed 2026-06-05):**
- `fpdf2`: 2.8.7 (latest on PyPI)
- `openpyxl`: 3.1.5 (latest on PyPI)
- `arq`: 0.28.0 (latest on PyPI)
- `redis`: 8.0.0 (latest on PyPI)
- `tailwindcss` (npm): 4.3.0 (latest) — use `tailwindcss@3` for compatibility
- `shadcn` (npm): 4.10.0 (latest) — use `shadcn@2.3.0` for Next.js 14 / React 18

---

## Architecture Patterns

### CT-01: Query Optimization

The current `get_control_tower()` fires 15+ individual `_count()` calls sequentially (each `await _count(db, ...)` is a separate database round-trip), plus 15+ queue fetches. Total: ~38 round-trips.

**Target pattern:** Consolidate summary counts into batched queries; fix per-row N+1 in `_operational_close_queue`.

**N+1 hotspot — `_operational_close_queue`:**
```python
# CURRENT (bad): 1 + 2*N queries for N trips
for trip, vehicle, driver in rows:
    proof = await db.scalar(select(DeliveryProof)...)      # N queries
    blocking_incident_id = await db.scalar(select(TripIncident.id)...)  # N queries
```

**Fix pattern — subquery with LEFT JOIN or correlated subquery to get latest proof + blocking incident in the same pass:**
```python
# Source: SQLAlchemy 2.0 docs — https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
from sqlalchemy.orm import contains_eager, selectinload

# Option 1: Use a lateral subquery for latest proof
latest_proof_subq = (
    select(DeliveryProof)
    .where(DeliveryProof.trip_id == Trip.id, DeliveryProof.tenant_id == tenant_id)
    .order_by(DeliveryProof.delivered_at.desc(), DeliveryProof.created_at.desc())
    .limit(1)
    .correlate(Trip)
    .lateral()
)
# Option 2: Load all proofs for the fetched trip IDs in a single IN query
trip_ids = [trip.id for trip, _, _ in rows]
proofs = await db.execute(
    select(DeliveryProof)
    .where(DeliveryProof.tenant_id == tenant_id, DeliveryProof.trip_id.in_(trip_ids))
    .order_by(DeliveryProof.delivered_at.desc())
)
```

**Document expiry queues — current pattern also N+1:**
`_vehicle_document_expiry_queue` fetches all active vehicles then iterates calling `vehicle_compliance_warnings()` in Python. This is acceptable (no extra SQL per vehicle) but loads all vehicles — should be capped.

**KPI scalars consolidation pattern:**
```python
# Current: 15 separate await _count() calls = 15 round-trips
# Target: Group counts into 2-3 multi-column SELECT with CASE/FILTER
summary_row = await db.execute(
    select(
        func.count(Trip.id).filter(Trip.status.in_(active_statuses)).label("trips_in_execution"),
        func.count(Trip.id).filter(Trip.billing_status == "billable").label("billing_ready"),
        func.sum(Trip.total_transport_cost).label("transport_cost_total"),
        # ... other scalar aggregates from Trip
    ).where(Trip.tenant_id == tenant_id)
)
```

### CT-02: Redis Cache-Aside

```python
# Source: redis-py 8.0 asyncio docs — https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
import redis.asyncio as aioredis

CACHE_KEY = "ct:kpis:{tenant_id}"
TTL_KPI = 60   # seconds
TTL_ALERTS = 30

async def get_control_tower_cached(db, tenant_id, redis_client):
    key = f"ct:kpis:{tenant_id}"
    lock_key = f"ct:kpis:{tenant_id}:lock"
    
    # Try cache first
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)
    
    # Acquire stampede lock: SET lock_key "1" NX EX 10
    acquired = await redis_client.set(lock_key, "1", nx=True, ex=10)
    if acquired:
        try:
            result = await get_control_tower(db, tenant_id)
            await redis_client.setex(key, TTL_KPI, json.dumps(result, default=str))
            return result
        finally:
            await redis_client.delete(lock_key)
    else:
        # Another worker is computing — wait briefly and return from DB
        return await get_control_tower(db, tenant_id)
```

**Redis client initialization pattern (FastAPI lifespan):**
```python
# In app/main.py lifespan
from redis.asyncio import Redis

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.aclose()
```

### CT-03: Pagination

```python
# Current hardcoded: .limit(10)
# Target pattern: parameterized page/page_size
async def _pending_dispatch_queue(
    db: AsyncSession, tenant_id: UUID,
    *, page: int = 1, page_size: int = 50
) -> list[dict]:
    offset = (page - 1) * page_size
    rows = await db.execute(
        select(DispatchClearance, Trip)
        ...
        .limit(page_size).offset(offset)
    )
```

### BILL-01 / BILL-02: Replacing exporters.py

**Current state:** `exporters.py` uses hand-rolled PDF (raw PDF bytes, `latin-1` encoding) and hand-rolled XLSX (raw XML/ZIP). The `latin-1` encoding silently corrupts or crashes on characters like `ã`, `ç`, `é`, `ê`. This must be completely replaced.

**fpdf2 pattern with DejaVuSans:**
```python
# Source: fpdf2 docs — https://py-pdf.github.io/fpdf2/Unicode.html
from fpdf import FPDF

class InvoicePDF(FPDF):
    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        # Font file must be bundled in the repo
        self.add_font("DejaVu", "", "backend/app/modules/billing/fonts/DejaVuSans.ttf")
        self.add_font("DejaVu", "B", "backend/app/modules/billing/fonts/DejaVuSans-Bold.ttf")
    
    def render_row(self, text: str):
        self.set_font("DejaVu", size=9)
        self.cell(0, 8, text)  # UTF-8 strings render correctly
```

**Font file sourcing:** DejaVuSans.ttf is available from the DejaVu Fonts project (fonts.debian.org / dejavu-fonts.github.io). Bundle both `DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` in `backend/app/modules/billing/fonts/`. Font license: Bitstream Vera (permissive, redistribution allowed).

**openpyxl pattern:**
```python
# Source: openpyxl docs
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, numbers

wb = Workbook()
ws = wb.active
# Header row bold
ws["A1"] = "Cliente"
ws["A1"].font = Font(bold=True)
# Currency columns right-aligned with format
ws["G2"].number_format = "#,##0.00"
ws["G2"].alignment = Alignment(horizontal="right")
# Date columns as ISO 8601 string (not datetime object)
ws["A2"] = "2026-06-01"
```

### BILL-03: Waiver Workflow

**Existing infrastructure:**
- `OperationalWaiver` model in `backend/app/modules/operations/models.py` — fields: `entity_type`, `entity_id`, `waiver_type`, `reason`, `approved_by`, `status`
- `require_margin_governance()` in `billing/service.py` — already checks for active waiver with `waiver_type="negative_margin_approved"`
- `has_active_waiver()` in `operations/service.py` — utility for waiver lookup

**What needs to be added:**
1. Endpoints for billing waiver lifecycle: `POST /api/v1/billing/waivers` (create with `pending_approval`), `POST /api/v1/billing/waivers/{id}/approve` (owner/admin only), `POST /api/v1/billing/waivers/{id}/reject`
2. The waiver status flow: `pending_approval` → `active` (on approve) or `rejected`
3. Frontend: modal components for request and approval dialogs

**RBAC enforcement for waiver approval:**
```python
from app.core.permissions import OWNER_ADMIN_ROLES, require_roles

@router.post("/waivers/{waiver_id}/approve")
async def approve_waiver(
    waiver_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*OWNER_ADMIN_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    ...
```

### ARQ Worker Pattern

```python
# backend/app/worker.py
from arq import Worker
from arq.connections import RedisSettings

async def generate_billing_pdf(ctx, document_id: str, tenant_id: str, job_id: str):
    """ARQ task: generate PDF and save to LOCAL_UPLOAD_DIR."""
    db = ctx["db"]
    # ... fetch document, render with fpdf2, save file, update job record

class WorkerSettings:
    functions = [generate_billing_pdf, generate_billing_xlsx, refresh_kpi_cache]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    retry_failed_jobs = True
    max_tries = 3
    on_startup = startup
    on_shutdown = shutdown
```

**Job tracking table (new migration required):**
```sql
-- New table: export_jobs
id UUID PRIMARY KEY
tenant_id UUID REFERENCES tenants(id)
job_type VARCHAR(30)  -- 'billing_pdf', 'billing_xlsx'
entity_id UUID        -- billing_document_id
status VARCHAR(20)    -- 'queued', 'processing', 'done', 'failed'
file_path TEXT        -- path within LOCAL_UPLOAD_DIR when done
error_message TEXT
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### RPT-01: Analytics KPI Queries

**New backend module or extension to billing module:**
```python
# GET /api/v1/analytics/kpis
# Params: period_start, period_end, vehicle_id?, driver_id?, tenant_id (from JWT)

async def get_fleet_kpis(
    db: AsyncSession, tenant_id: UUID,
    period_start: datetime, period_end: datetime,
    vehicle_id: UUID | None = None,
    driver_id: UUID | None = None,
) -> dict:
    # Cost-per-km: fuel_cost + stop_costs / total_km grouped by vehicle
    # Fleet utilization: trips in active status / total active vehicles
    # L/100km: fuel liters / km over rolling 30-day window
    # Driver summary: trips, km, total cost per driver
    pass
```

All KPI queries must have `WHERE tenant_id = ?` — this is the highest-risk area for cross-tenant leaks alongside CT-01.

### Frontend: Tailwind Config Extension Pattern

```typescript
// tailwind.config.ts (Tailwind v3 pattern — NOT Tailwind 4 CSS-first)
import type { Config } from "tailwindcss"

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        nav:    "var(--nav)",
        soft:   "var(--soft)",
        panel:  "var(--panel)",
        ink:    "var(--ink)",
        muted:  "var(--muted)",
        line:   "var(--line)",
        blue:   "var(--blue)",
        green:  "var(--green)",
        orange: "var(--orange)",
        red:    "var(--red)",
        cyan:   "var(--cyan)",
      },
    },
  },
  plugins: [],
}
export default config
```

This matches the UI-SPEC contract exactly. The `:root` CSS vars in `globals.css` are preserved; Tailwind maps them to utility classes like `bg-nav`, `text-muted`, `border-line`.

### Anti-Patterns to Avoid

- **Hand-rolled PDF with `latin-1`:** The existing `exporters.py` silently corrupts UTF-8. The entire file must be replaced, not patched.
- **Blocking HTTP for export:** Do not call `fpdf2` or `openpyxl` synchronously in a request handler — always enqueue to ARQ.
- **`shadcn@latest` with Next.js 14:** Will install Tailwind 4 components incompatible with the project's React 18 peer requirements.
- **`tailwindcss@4` with `tailwind.config.ts`:** Tailwind 4 removes the config file; the UI-SPEC uses `tailwind.config.ts` — stay on Tailwind 3.
- **Removing `tenant_id` filters during CT-01 optimization:** Every consolidated query must retain `.where(Model.tenant_id == tenant_id)`. Cross-tenant regression tests must run after each query batch.
- **`lazy="raise"` in production:** Only set `lazy="raise"` for development — it will crash production if any relationship is lazy-loaded at runtime.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PDF generation with Unicode | Raw PDF bytes + font embedding (current `exporters.py`) | `fpdf2 >= 2.8.7` + `DejaVuSans.ttf` | Latin Extended Unicode subsetting, proper bidi algorithm, no corrupt bytes on diacritics |
| XLSX generation with formatting | Raw XML/ZIP (current `exporters.py`) | `openpyxl 3.1.5` | Handles `#,##0.00` format codes, bold headers, cell alignment; hand-rolled XML breaks on special chars |
| Background job queue | FastAPI `BackgroundTasks` (no retry, no monitoring) | `arq 0.28.0` | ARQ has retry logic, job status tracking, Redis-backed durability, asyncio-native |
| Redis cache stampede prevention | Custom lock primitives | `redis.set(key, val, nx=True, ex=N)` | Atomic SET NX EX is the standard Redis distributed lock primitive |
| Component library | Custom modal/dialog/badge HTML | `shadcn/ui` components via CLI | Radix UI primitives provide accessible focus trap, keyboard nav, ARIA roles — these are hard to hand-roll correctly |

**Key insight:** The most expensive hand-rolled code in the codebase is `exporters.py`. It works for ASCII but silently corrupts any Portuguese name with an accent. This is a silent data quality bug that will only surface in production when a Mozambican manager opens a PDF with "Machanga" or "Quelimane" in it.

---

## Common Pitfalls

### Pitfall 1: latin-1 PDF Encoding (CRITICAL — already in codebase)
**What goes wrong:** `exporters.py` line 187 encodes stream bytes as `latin-1` — `.encode("latin-1")`. Characters outside Latin-1 (e.g., `ã`, `ç`, `â`, `ê`) are silently replaced with `?` or raise `UnicodeEncodeError` on certain chars.
**Why it happens:** The hand-rolled PDF builder uses Type1 fonts (Helvetica) which are Latin-1 only. fpdf2 with DejaVuSans embeds the TTF glyphs directly and handles UTF-8 at the library level.
**How to avoid:** Replace `exporters.py` entirely with fpdf2. Do not patch the existing implementation.
**Warning signs:** Any name with ã, ç, é, ê, â, ô in a generated PDF.

### Pitfall 2: Tailwind 4 / shadcn Version Mismatch
**What goes wrong:** Running `npx shadcn@latest init` installs Tailwind 4 components. The project is on Next.js 14 + React 18. Tailwind 4 peer deps require React 19 for some Radix components. Build fails or components have wrong utility class names.
**Why it happens:** shadcn@latest changed defaults in mid-2025 to target the Next.js 15 + Tailwind 4 ecosystem.
**How to avoid:** Pin `npx shadcn@2.3.0 init` and `tailwindcss@3` in package.json.
**Warning signs:** `tailwind.config.ts` not generated; `@theme` directive in globals.css; React peer dependency warnings.

### Pitfall 3: CT-01 Cross-Tenant Leak During Query Consolidation
**What goes wrong:** When consolidating 15 individual `_count()` calls into 2-3 batched queries, a `.where(Model.tenant_id == tenant_id)` filter is accidentally dropped. A merged query returns aggregate counts across all tenants.
**Why it happens:** Refactoring attention is on reducing query count, not on per-filter verification.
**How to avoid:** Run `test_cross_tenant_isolation.py` after EVERY batch of query rewrites. The test file already exists at `backend/tests/test_cross_tenant_isolation.py`.
**Warning signs:** Summary counts that seem too high for a new tenant; control tower showing another tenant's trips.

### Pitfall 4: `lazy="raise"` Breaking Production
**What goes wrong:** `lazy="raise"` is set globally on relationships in SQLAlchemy models. In production, any code path that triggers a lazy relationship access raises `MissingGreenlet` or `InvalidRequestError`, crashing the request.
**Why it happens:** Dev-only setting applied to production models.
**How to avoid:** Use `lazy="raise"` only in test fixtures or conditional on `ENVIRONMENT=development`. Do NOT set it in model definitions.
**Warning signs:** 500 errors on endpoints that weren't touched, with SQLAlchemy `InvalidRequestError`.

### Pitfall 5: ARQ Job Not Idempotent
**What goes wrong:** ARQ retries failed jobs (at-least-once delivery). A PDF export job that partially writes a file before failing gets retried, writing a second file or duplicate database record.
**Why it happens:** ARQ's default retry behavior assumes idempotent tasks.
**How to avoid:** Check for existing `export_jobs` record by `(tenant_id, entity_id, job_type)` before generating. Update existing record rather than inserting a new one.
**Warning signs:** Duplicate files in `LOCAL_UPLOAD_DIR`; duplicate job records.

### Pitfall 6: `_operational_close_queue` N+1 (highest query count)
**What goes wrong:** This single function currently fires up to 21 queries for 10 trips (1 base query + 2 per trip). It is the primary contributor to the ~38 total query count.
**Why it happens:** Sequential `await db.scalar()` inside a `for` loop.
**How to avoid:** Use a single IN query to fetch all relevant delivery proofs and blocking incidents for the trip_id batch, then correlate in Python. See Architecture Patterns above.
**Warning signs:** Slow CT response even after count consolidation.

### Pitfall 7: DejaVuSans Font File Not Found
**What goes wrong:** `fpdf2` raises `FileNotFoundError` in the ARQ worker process because font path is relative to the calling process's working directory.
**Why it happens:** ARQ worker may be launched from a different directory than the FastAPI app.
**How to avoid:** Use `Path(__file__).parent / "fonts" / "DejaVuSans.ttf"` — absolute path relative to the Python file, not the process CWD.
**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'fonts/DejaVuSans.ttf'` in ARQ worker logs.

---

## Code Examples

Verified patterns from official sources:

### fpdf2 Unicode Invoice (UTF-8 safe)
```python
# Source: https://py-pdf.github.io/fpdf2/Unicode.html
from pathlib import Path
from fpdf import FPDF

FONTS_DIR = Path(__file__).parent / "fonts"

def render_invoice_pdf(document, items) -> bytes:
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, "ROTAS — Documento de Cobrança de Transporte", ln=True)
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 8, f"Cliente: {document.client_name}", ln=True)  # diacritics work
    return pdf.output()
```

### openpyxl Invoice Export
```python
# Source: openpyxl official docs
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment

def render_invoice_xlsx(document, items) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Cobrança"
    # Bold header
    headers = ["Data descarga", "Origem", "Destino", "Carga", "Qtd", "Preço unit.", "Total"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True)
    # Currency format for value columns
    for row_idx, item in enumerate(items, start=2):
        ws.cell(row=row_idx, column=6, value=float(item.unit_price or 0)).number_format = "#,##0.00"
        ws.cell(row=row_idx, column=7, value=float(item.amount or 0)).number_format = "#,##0.00"
    output = BytesIO()
    wb.save(output)
    return output.getvalue()
```

### ARQ Worker Definition
```python
# Source: https://arq-docs.helpmanual.io/ + https://github.com/python-arq/arq
# backend/app/worker.py
from arq.connections import RedisSettings
from app.config import settings

async def startup(ctx):
    from app.database import AsyncSessionLocal
    ctx["db_factory"] = AsyncSessionLocal

async def shutdown(ctx):
    pass

async def generate_billing_export(ctx, job_id: str, document_id: str, export_format: str, tenant_id: str):
    async with ctx["db_factory"]() as db:
        await _do_export(db, job_id, document_id, export_format, tenant_id)

class WorkerSettings:
    functions = [generate_billing_export]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    max_tries = 3
    keep_result = 86400  # 24 hours
```

### Redis Cache-Aside (asyncio)
```python
# Source: https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html
import redis.asyncio as aioredis
import json

async def get_ct_cached(redis: aioredis.Redis, key: str, ttl: int, compute_fn):
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    lock = f"{key}:lock"
    acquired = await redis.set(lock, "1", nx=True, ex=10)
    if acquired:
        try:
            result = await compute_fn()
            await redis.setex(key, ttl, json.dumps(result, default=str))
            return result
        finally:
            await redis.delete(lock)
    return await compute_fn()  # lock contention fallback: compute without caching
```

### SQLAlchemy Consolidated Count Query
```python
# Source: https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html
from sqlalchemy import func, case, select

# Replace 6 separate _count() calls with one aggregation query
trip_summary = (await db.execute(
    select(
        func.count(Trip.id).filter(
            Trip.status.in_(("dispatched", "in_progress", "delayed", "incident"))
        ).label("trips_in_execution"),
        func.count(Trip.id).filter(
            Trip.billing_status == "billable"
        ).label("billing_ready"),
        func.count(Trip.id).filter(
            Trip.status == "closed", Trip.costs_reconciled_at.is_(None)
        ).label("closed_unreconciled"),
        func.coalesce(func.sum(Trip.total_transport_cost), 0).label("transport_cost_total"),
        func.coalesce(func.sum(Trip.actual_revenue), 0).label("revenue_total"),
    ).where(Trip.tenant_id == tenant_id)
)).one()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `python-jose` JWT | `PyJWT >= 2.8` (done in Phase 1) | Phase 1 | CVE-2025-61152 closed |
| Hand-rolled PDF/XLSX in `exporters.py` | `fpdf2` + `openpyxl` | Phase 3 | UTF-8 support enabled |
| Custom CSS classes in `globals.css` | Tailwind utility classes | Phase 3 | Eliminates CSS maintenance overhead |
| Synchronous export in HTTP response | ARQ background jobs | Phase 3 | No HTTP timeout on large invoices |
| `shadcn@latest` (Tailwind 4) | `shadcn@2.3.0` (Tailwind 3) | Phase 3 | Next.js 14 / React 18 compatibility |

**Deprecated/outdated:**
- `exporters.py` hand-rolled PDF: Current file at `backend/app/modules/billing/exporters.py` is technically functional for ASCII content only. Must be deleted and replaced entirely, not patched.
- Hardcoded `.limit(10)` in CT queue functions: Replace with page/page_size params.
- Sequential `await _count()` pattern: Replace with batched aggregation queries where models share the same base table.

---

## Open Questions

1. **`tailwindcss@3` vs `@4` exact resolution**
   - What we know: shadcn@2.3.0 targets Tailwind v3; shadcn@latest targets Tailwind v4; project is on Next.js 14 + React 18
   - What's unclear: Whether the `@tailwindcss/postcss` package at 4.3.0 is for Tailwind 4 only, or also supports Tailwind 3 (it is Tailwind 4's PostCSS plugin)
   - Recommendation: Install `tailwindcss@^3.4`, `postcss`, `autoprefixer` for Tailwind 3; do NOT install `@tailwindcss/postcss` (that's Tailwind 4 only). Use `tailwind.config.ts` as specified in UI-SPEC.

2. **`analytics` module placement**
   - What we know: No existing analytics module or endpoint; queries span trips, fuel_logs, trip_costs
   - What's unclear: Whether to create a new `app/modules/analytics/` module or extend `control_tower/` with analytics endpoints
   - Recommendation: Create `app/modules/analytics/` as a new module — the queries are sufficiently different from operational CT queries to warrant separation.

3. **Waiver model reuse vs new table**
   - What we know: `OperationalWaiver` exists in `operations/models.py` with `waiver_type="negative_margin_approved"`; `require_margin_governance()` already checks it
   - What's unclear: Whether to reuse `OperationalWaiver` (adding `pending_approval` status) or create a separate `BillingMarginWaiver` table
   - Recommendation (Claude's discretion): Reuse `OperationalWaiver` — add `status` flow (`pending_approval` → `active`/`rejected`) to the existing model via new Alembic migration. The `approved_by` and `approved_at` columns already exist.

4. **Redis availability in production**
   - What we know: Redis 7 is defined in `infra/docker-compose.yml` on port 6381; Redis is NOT currently running locally (redis-cli ping failed); `redis[asyncio]` is NOT yet in pyproject.toml
   - What's unclear: Railway deployment configuration for Redis
   - Recommendation: Add `REDIS_URL` to `pydantic-settings` config with `redis://localhost:6381` default; Railway will inject the production URL. Implement graceful degradation: if Redis is unavailable, CT falls back to direct DB query with warning log.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | All backend | ✓ | 3.13.13 | — |
| Node.js 20.x | Frontend build | ✓ | 24.16.0 | — |
| PostgreSQL | All backend | Not verified locally | 16 (expected) | — |
| Redis | CT-02, ARQ | ✗ (not running locally) | — | Direct DB fallback for CT; block feature without Redis |
| Docker | Redis startup | ✓ | 29.5.2 | `docker compose up redis` for local dev |
| `redis[asyncio]` (pip) | CT-02 | ✗ (not in venv) | 8.0.0 (PyPI) | Install via `pip install "redis[asyncio]"` |
| `arq` (pip) | BILL-01/02 async | ✗ (not in venv) | 0.28.0 (PyPI) | Install via `pip install arq` |
| `fpdf2` (pip) | BILL-01 | ✗ (not in venv) | 2.8.7 (PyPI) | No fallback — required for UTF-8 PDF |
| `openpyxl` (pip) | BILL-02 | ✗ (not in venv) | 3.1.5 (PyPI) | No fallback — required for XLSX export |
| `tailwindcss` (npm) | Frontend migration | ✗ (not in package.json) | 3.x (use 3, not 4) | Install via npm |
| `shadcn` (npm CLI) | Component generation | ✗ (not installed) | 2.3.0 (pin this) | Install via npx |
| DejaVuSans.ttf | BILL-01 | ✗ (not in repo) | N/A (font file) | Download from DejaVu project, commit to repo |

**Missing dependencies with no fallback:**
- `fpdf2` — required for BILL-01 (UTF-8 PDF); no fallback; install in Wave 0
- `openpyxl` — required for BILL-02 (XLSX); no fallback; install in Wave 0
- `DejaVuSans.ttf` font file — required for fpdf2 to render diacritics; must be committed to repo

**Missing dependencies with fallback:**
- Redis / `redis[asyncio]` — CT-02 can degrade to direct DB query; ARQ jobs cannot queue without Redis
- `arq` — export jobs cannot be async without it; could fall back to synchronous export (blocks HTTP) as temporary measure
- `tailwindcss` / `shadcn` — frontend currently works without them; migration is additive

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2+ with pytest-asyncio |
| Config file | `backend/pyproject.toml` (`[tool.pytest.ini_options]` section, `asyncio_mode = "auto"`) |
| Quick run command | `pytest backend/tests/test_billing_domain.py backend/tests/test_control_tower_api.py -x -q` |
| Full suite command | `pytest backend/tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CT-01 | CT response under 3s for 20-vehicle tenant; N+1 queries eliminated | integration | `pytest backend/tests/test_control_tower_api.py -x -q` | ✅ (extend existing) |
| CT-01 | Cross-tenant isolation preserved after query rewrite | regression | `pytest backend/tests/test_cross_tenant_isolation.py -x -q` | ✅ |
| CT-02 | Redis cache returns cached value on second call; TTL respected | integration | `pytest backend/tests/test_control_tower_cache.py -x -q` | ❌ Wave 0 |
| CT-03 | Pagination params `page`/`page_size` respected; no unbounded query | unit | `pytest backend/tests/test_control_tower_api.py::test_pagination -x -q` | ❌ Wave 0 |
| BILL-01 | PDF bytes render Mozambican name "Quelimane" correctly (no corrupt bytes) | unit | `pytest backend/tests/test_billing_export.py::test_pdf_utf8 -x -q` | ❌ Wave 0 |
| BILL-02 | XLSX bytes contain header bold + currency `#,##0.00` format | unit | `pytest backend/tests/test_billing_export.py::test_xlsx_format -x -q` | ❌ Wave 0 |
| BILL-03 | Trip with `margin < 0` cannot be billed without waiver; `409` returned | unit | `pytest backend/tests/test_billing_domain.py -x -q` | ✅ (extend) |
| BILL-03 | Waiver create → approve flow sets `status=active`; trip can be billed | integration | `pytest backend/tests/test_waiver_flow.py -x -q` | ❌ Wave 0 |
| RPT-01 | KPI endpoint returns `cost_per_km`, `fleet_utilization`, `l_per_100km` for tenant | integration | `pytest backend/tests/test_analytics_api.py -x -q` | ❌ Wave 0 |
| RPT-02 | Document expiry panel shows vehicles/drivers within 30-day threshold | unit | `pytest backend/tests/test_control_tower_api.py::test_document_expiry -x -q` | ❌ Wave 0 (CT test partially covers) |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/test_cross_tenant_isolation.py backend/tests/test_billing_domain.py -x -q`
- **Per wave merge:** `pytest backend/tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_control_tower_cache.py` — covers CT-02 Redis cache behavior
- [ ] `backend/tests/test_billing_export.py` — covers BILL-01 UTF-8 PDF + BILL-02 XLSX format
- [ ] `backend/tests/test_waiver_flow.py` — covers BILL-03 end-to-end waiver lifecycle
- [ ] `backend/tests/test_analytics_api.py` — covers RPT-01 KPI endpoint
- [ ] `backend/tests/conftest.py` — verify Redis mock fixtures don't require live Redis for unit tests

---

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `backend/app/modules/control_tower/service.py` — confirmed N+1 patterns
- Codebase inspection: `backend/app/modules/billing/exporters.py` — confirmed latin-1 encoding bug
- Codebase inspection: `backend/app/modules/operations/models.py` — confirmed `OperationalWaiver` exists
- Codebase inspection: `backend/app/modules/billing/service.py` — confirmed `require_margin_governance()` exists
- Codebase inspection: `apps/manager/package.json` — confirmed no Tailwind; `engines.node=20.x` already set
- PyPI version check: fpdf2=2.8.7, openpyxl=3.1.5, arq=0.28.0, redis=8.0.0
- npm version check: tailwindcss=4.3.0, shadcn=4.10.0, @tailwindcss/postcss=4.3.0
- https://py-pdf.github.io/fpdf2/Unicode.html — fpdf2 Unicode/TTF font support
- https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html — SQLAlchemy 2.0 eager loading
- https://redis.readthedocs.io/en/stable/examples/asyncio_examples.html — redis-py asyncio

### Secondary (MEDIUM confidence)
- https://arq-docs.helpmanual.io/ — ARQ 0.28 worker pattern
- https://ui.shadcn.com/docs/tailwind-v4 — shadcn Tailwind 4 migration notes; confirmed Tailwind 3 is "non-breaking"
- https://v3.shadcn.com/docs/installation/next — shadcn@2.3.0 for Tailwind v3

### Tertiary (LOW confidence)
- WebSearch: "Building Resilient Task Queues in FastAPI with ARQ Retries" — ARQ retry patterns (single source, not official docs)

---

## Metadata

**Confidence breakdown:**
- CT-01 N+1 analysis: HIGH — direct code inspection of `service.py`
- BILL-01/02 latin-1 bug: HIGH — direct code inspection of `exporters.py`, line 187
- BILL-03 waiver infrastructure: HIGH — direct inspection confirms partial wiring
- Library versions: HIGH — verified against PyPI registry 2026-06-05
- shadcn version pinning (2.3.0): MEDIUM — confirmed from shadcn docs; Next.js 14 + React 18 compatibility behavior unverified in CI
- Tailwind 3 vs 4 for this project: MEDIUM — deduced from UI-SPEC `tailwind.config.ts` pattern; Tailwind 4 removes this file

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (stable libraries; Redis/ARQ API unlikely to change in 30 days)
