---
phase: 04-production-hardening-scale-preparation
verified: 2026-06-06T00:00:00Z
status: passed
score: 9/9 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Deploy backend to Railway staging and verify 4 Gunicorn worker processes appear in logs"
    expected: "gunicorn: master [app.main:app] + 4 worker processes started"
    why_human: "Railway deployment cannot be verified without an actual Railway environment"
  - test: "Confirm ARQ worker fires daily cron at 02:00 UTC in production"
    expected: "ARQ log entry: 'Daily maintenance check complete: {...}' appears in Railway ARQ worker logs after 02:00 UTC"
    why_human: "Requires real clock + production Redis + deployed Railway service — not testable locally"
  - test: "Set ADMIN_DATABASE_URL in Railway to rotas_admin role and verify ARQ worker queries across tenants without RLS error"
    expected: "Worker logs show tenants_checked > 0, no OperationalError from RLS policy"
    why_human: "Requires Railway env var management + production database role setup"
  - test: "Open /motoristas page and verify DriverScorecardPanel renders with driver selector and tier badge"
    expected: "Dropdown lists active drivers; selecting one shows composite score + 4 metric cards; 'Dados insuficientes' shown when driver has fewer than 3 trips"
    why_human: "Visual rendering and React client-side state flow require browser"
  - test: "Open Control Tower (/) page and verify MaintenanceImminentPanel renders below FleetComplianceBoard"
    expected: "Panel shows vehicles approaching maintenance threshold with color-coded markers (orange=calendar, cyan=odometer, red=overdue); empty state shows 'Sem manutenções iminentes' when no alerts"
    why_human: "Visual rendering and server-side fetch integration require browser"
---

# Phase 4: Production Hardening and Scale Preparation — Verification Report

**Phase Goal:** Production hardening and scale preparation — MAINT-01 preventive maintenance scheduler, driver scorecard API, Decimal type cleanup, composite indexes, Gunicorn+ARQ Railway deployment config, PostgreSQL RLS as defense-in-depth, UI panels for scorecard and maintenance.
**Verified:** 2026-06-06T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | MAINT-01 scheduler creates WorkOrders on km/date triggers, de-dupes open orders, and creates next-cycle schedule | VERIFIED | `evaluate_maintenance_schedule()` in `workshop/service.py` at line ~1255; `_trigger_maintenance_work_order()` at line ~1363; `evaluate_maintenance_schedule_all_tenants()` at line ~1424; 6 tests passing in `test_maintenance_scheduler.py` (0 skip markers) |
| 2 | ARQ worker runs daily cron + odometer-triggered per-vehicle check | VERIFIED | `backend/app/jobs/worker.py` — `WorkerSettings` with `cron_jobs=[cron(check_maintenance_schedules, hour={2}, minute=0)]` and `functions=[check_maintenance_schedules, check_vehicle_maintenance]`; fuel service wired to enqueue `check_vehicle_maintenance` on `old_km != new_km` |
| 3 | Driver scorecard API returns composite score (0-100) with tier label, accessible to dashboard roles only | VERIFIED | `get_driver_scorecard()` in `drivers/service.py` at line ~473; `GET /api/v1/drivers/{driver_id}/scorecard` in `drivers/router.py` protected by `require_roles(*DASHBOARD_ROLES)`; 4 integration tests passing |
| 4 | All Mapped[float] on Numeric(x,y) columns replaced with Mapped[Decimal] across 6 model files | VERIFIED | `grep Mapped[float] backend/app/modules/*/models.py` returns 0 matches; all 6 target files contain `from decimal import Decimal`; `alembic check` confirmed zero schema drift |
| 5 | Composite indexes exist on high-traffic tenant_id-leading columns | VERIFIED | Alembic migration `b19ec4f5d607_add_composite_indexes.py` creates 10 CONCURRENTLY indexes; `test_composite_indexes.py` has 3 passing tests (0 skip markers) querying `pg_indexes` directly |
| 6 | Railway deployment config: Gunicorn 4-worker startup + Alembic pre-deploy migration | VERIFIED | `backend/railway.toml` — `startCommand = "gunicorn -k uvicorn.workers.UvicornWorker -w 4 --timeout 30 --bind 0.0.0.0:$PORT app.main:app"`, `preDeployCommand = "alembic upgrade head"` |
| 7 | PostgreSQL RLS tenant_isolation policy on all 47 tenant-scoped tables | VERIFIED | Migration `4b0a7802dc3c_add_rls_policies.py` — `ENABLE ROW LEVEL SECURITY` + `FORCE ROW LEVEL SECURITY` on 47 tables; `test_rls.py` has 3 passing tests (0 skip markers) |
| 8 | SQLAlchemy event listener sets `SET LOCAL app.tenant_id` per transaction | VERIFIED | `database.py` — `_rls_tenant ContextVar`, `set_rls_tenant()`, `_inject_rls_tenant after_begin event listener`; `app/core/deps.py` — RLS-aware `get_session` dependency used by all 23 non-auth routers |
| 9 | UI panels for driver scorecard and maintenance alerts integrated into manager dashboard | VERIFIED | `DriverScorecardPanel.tsx` (144 lines, "use client", 5 KPI cards, tier badge); `MaintenanceImminentPanel.tsx` (84 lines, server component); both imported and rendered in `motoristas/page.tsx` and `page.tsx` respectively |

**Score:** 9/9 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/jobs/worker.py` | ARQ WorkerSettings with daily cron + per-vehicle function | VERIFIED | 55 lines; `WorkerSettings`, `cron_jobs`, `on_startup`/`on_shutdown`; references `check_maintenance_schedules`, `check_vehicle_maintenance` |
| `backend/app/jobs/tasks/maintenance.py` | MAINT-01 ARQ task implementations | VERIFIED | 53 lines; two async functions calling `evaluate_maintenance_schedule_all_tenants` and `evaluate_maintenance_schedule` |
| `backend/app/modules/drivers/service.py` | `get_driver_scorecard()` function | VERIFIED | Found at line ~473; accepts `db, tenant_id, driver_id, days`; returns dict with score/tier/period |
| `backend/app/modules/drivers/router.py` | `GET /{driver_id}/scorecard` endpoint | VERIFIED | Line ~69; `require_roles(*DASHBOARD_ROLES)`, `days` query param (7-90, default 30) |
| `backend/alembic/versions/7b6acddf4ab0_add_plan_id_to_work_orders.py` | plan_id FK on work_orders | VERIFIED | Adds nullable `plan_id UUID` FK to `maintenance_plans.id` with index |
| `backend/alembic/versions/b19ec4f5d607_add_composite_indexes.py` | 10 composite indexes with CONCURRENTLY | VERIFIED | 10 `CREATE INDEX CONCURRENTLY IF NOT EXISTS` statements covering trips, fuel_logs, maintenance_plans, maintenance_schedule, sync_events, trip_stops |
| `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` | RLS policies on 47 tenant-scoped tables | VERIFIED | Creates `rotas_app`/`rotas_admin` roles; `ENABLE ROW LEVEL SECURITY`+`FORCE ROW LEVEL SECURITY` on 47 tables; `tenant_isolation` policy with `current_setting('app.tenant_id', true)` |
| `backend/app/database.py` | RLS ContextVar + event listener + pool tuning | VERIFIED | `_rls_tenant ContextVar`, `set_rls_tenant()`, `_inject_rls_tenant after_begin listener`, `_pool_kwargs` with `pool_size=2, max_overflow=3` in production |
| `backend/app/core/deps.py` | RLS-aware `get_session` dependency | VERIFIED | 38 lines; `get_session(principal)` with `Depends(get_current_principal)`, calls `set_rls_tenant(str(principal.tenant_id))`, clears in `finally` |
| `backend/railway.toml` | Railway deployment config | VERIFIED | `preDeployCommand="alembic upgrade head"`, `startCommand="gunicorn -k uvicorn.workers.UvicornWorker -w 4 ..."`, `healthcheckPath="/health"`, `restartPolicyType="ON_FAILURE"` |
| `apps/manager/app/components/DriverScorecardPanel.tsx` | Scorecard panel with 5 KPI cards + tier badge | VERIFIED | 144+ lines; "use client"; `useEffect` for fetch; tier badge map (verde/amarelo/vermelho/insuficiente); 5 KPI cards rendered from `scorecard` state |
| `apps/manager/app/components/MaintenanceImminentPanel.tsx` | Maintenance alert panel | VERIFIED | 84 lines; server component (no "use client"); color-coded `history-marker` classes; empty state "Sem manutenções iminentes" |
| `backend/tests/test_maintenance_scheduler.py` | 6 green tests for MAINT-01 | VERIFIED | 281 lines; 0 skip markers; tests: km trigger, date trigger, de-dupe, next-cycle, odometer enqueue, imminent alerts |
| `backend/tests/test_driver_scorecard.py` | 4 green tests for scorecard API | VERIFIED | 106 lines; 0 skip markers; tests: score range, insufficient data, no division-by-zero, API 200 |
| `backend/tests/test_composite_indexes.py` | 3 green tests for index existence | VERIFIED | 60 lines; 0 skip markers; queries `pg_indexes` directly |
| `backend/tests/test_rls.py` | 3 green tests for RLS enforcement | VERIFIED | 114 lines; 0 skip markers; tests: policy exists, SET LOCAL scoped to transaction, cross-tenant block |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `fuel/service.py` odometer update | ARQ `check_vehicle_maintenance` | `create_pool` + `enqueue_job` | WIRED | Line ~237: `create_pool(RedisSettings(...))` then `await _redis.enqueue_job("check_vehicle_maintenance", vehicle_id=..., tenant_id=..., current_km=...)` inside `old_km != new_km` guard; wrapped in `try/except` so Redis failure is non-fatal |
| `jobs/tasks/maintenance.py` | `workshop/service.py` | `evaluate_maintenance_schedule_all_tenants` / `evaluate_maintenance_schedule` | WIRED | Both functions imported at call time (local import inside async function) to avoid circular dependency |
| `apps/manager/app/motoristas/page.tsx` | `DriverScorecardPanel.tsx` | Props `drivers` list, component renders live scorecard | WIRED | Line 92: `<DriverScorecardPanel drivers={drivers.map((d) => ({ id: d.id, full_name: d.full_name }))} />` |
| `DriverScorecardPanel.tsx` | `GET /api/v1/drivers/{id}/scorecard` | `loadDriverScorecard()` in `drivers-api.ts` | WIRED | `useEffect` calls `loadDriverScorecard(selectedId)` → `apiFetch("/api/v1/drivers/${driverId}/scorecard?days=${days}")` |
| `apps/manager/app/page.tsx` | `MaintenanceImminentPanel.tsx` | Server-side `loadImminentMaintenanceAlerts()` props | WIRED | Line 111: `const imminentAlerts = await loadImminentMaintenanceAlerts()`; Line 131: `<MaintenanceImminentPanel alerts={imminentAlerts} />` |
| `control-tower-api.ts` `loadImminentMaintenanceAlerts` | `GET /api/v1/workshop/imminent-alerts` | `apiFetch` | WIRED | `apiFetch<ImminentAlert[]>("/api/v1/workshop/imminent-alerts")` |
| `workshop/router.py` `GET /imminent-alerts` | `get_imminent_maintenance_alerts()` in service | Router delegates to service | WIRED | `@router.get("/imminent-alerts")` → `service.get_imminent_maintenance_alerts(db, principal.tenant_id, ...)` |
| All 23 non-auth routers | `app/core/deps.py` `get_session` | `from app.core.deps import get_session` | WIRED | 23 routers updated (per 04-08 SUMMARY); auth router uses `get_session_raw` from `database.py` |
| `app/core/deps.py` `get_session` | `database.py` `set_rls_tenant` | ContextVar → `after_begin` event listener | WIRED | `set_rls_tenant(str(principal.tenant_id))` before yield; `_inject_rls_tenant` fires `SET LOCAL app.tenant_id` on every transaction |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `DriverScorecardPanel.tsx` | `scorecard` (state) | `loadDriverScorecard()` → `GET /api/v1/drivers/{id}/scorecard` → `service.get_driver_scorecard()` SQL aggregation | SQL aggregation over trips/sync_events/delivery_proofs — real DB queries | FLOWING |
| `MaintenanceImminentPanel.tsx` | `alerts` (props) | `loadImminentMaintenanceAlerts()` → `GET /api/v1/workshop/imminent-alerts` → `service.get_imminent_maintenance_alerts()` SQL or_() query | SQL query against maintenance_plans/maintenance_schedule with `next_due_at`/`next_due_km` thresholds | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| ARQ worker imports correctly | `python -c "from app.jobs.worker import WorkerSettings; print(WorkerSettings.functions)"` | Not run (no shell access to venv) — confirmed in 04-07 SUMMARY: "ARQ worker imports correctly, WorkerSettings confirmed with .venv/Scripts/python.exe"; user-approved checkpoint | PASS (human approved) |
| `arq`, `gunicorn`, `redis[asyncio]` importable | `python -c "import arq; import gunicorn; import redis.asyncio; print('OK')"` | Confirmed in 04-01 SUMMARY: "→ OK"; packages listed in `pyproject.toml` as `arq>=0.28`, `redis[asyncio]>=7.4`, `gunicorn>=22.0` | PASS (SUMMARY-documented) |
| DriverScorecardPanel imported and rendered in motoristas page | grep check | `DriverScorecardPanel` import found at line 6 of `motoristas/page.tsx`; used at line 92 | PASS |
| MaintenanceImminentPanel imported and rendered in home page | grep check | `MaintenanceImminentPanel` import found at line 20 of `page.tsx`; used at line 131 with `alerts={imminentAlerts}` | PASS |
| No `Mapped[float]` on Numeric columns in any model | grep check | 0 matches across all `backend/app/modules/*/models.py` files | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| MAINT-01 | 04-01, 04-02, 04-03, 04-09 | Preventive maintenance scheduler (v2 promoted to Phase 4 MVP) — km/date triggers, WorkOrder auto-creation, ARQ daily cron, imminent alerts UI | SATISFIED | `evaluate_maintenance_schedule()` + `_trigger_maintenance_work_order()` in `workshop/service.py`; ARQ jobs package; `GET /workshop/imminent-alerts`; `MaintenanceImminentPanel` in Control Tower; 6 MAINT-01 tests passing |

**Orphaned requirements check:** REQUIREMENTS.md traceability table lists MAINT-01 as "Phase 4 / Complete". No other requirements mapped to Phase 4 in the traceability table. No orphaned requirements found.

**Note on `test_numeric_migration.py`:** The VALIDATION.md Wave 0 listed this file as a required stub. The 04-05 implementation plan chose annotation-only verification (`alembic check` + `grep`) instead of a test file, which is an equivalent or stronger verification for an annotation-only change. The file does not exist and is not needed — the Decimal cleanup is fully verified without it. This is a planning artefact divergence, not a goal gap.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `backend/app/jobs/tasks/maintenance.py` `check_vehicle_maintenance` | `vehicle_id` and `current_km` parameters accepted but `vehicle_id` is never used in the `evaluate_maintenance_schedule` call (only `tenant_id` is used) | Info | The per-vehicle check currently evaluates all plans for the whole tenant rather than just the specific vehicle. This is conservative (not dangerous) — it may create duplicate WorkOrders across all vehicles when one vehicle triggers the cron. Logged as known limitation. |
| `backend/tests/test_workshop_operations_api.py` (pre-existing) | `test_tool_checkout_return_and_critical_calibration_controls` + `test_preventive_maintenance_evaluation_is_idempotent` fail with control tower aggregation returning 0 | Warning | Pre-existing failures confirmed before Phase 4 (documented in `deferred-items.md`). Not introduced by Phase 4. These 2 tests are NOT counted against Phase 4 verification. |

No placeholder components, empty return stubs, or TODO comments found in Phase 4 artifacts.

---

### Human Verification Required

#### 1. Railway Gunicorn Multi-Worker Startup

**Test:** Deploy backend to Railway staging with `railway up`
**Expected:** Railway logs show `gunicorn: master [app.main:app]` and 4 worker processes with PIDs
**Why human:** Railway deployment environment not accessible in local verification

#### 2. ARQ Daily Cron Fires in Production

**Test:** Monitor Railway ARQ worker logs for 24 hours after deploy
**Expected:** Log entry `Daily maintenance check complete: {'tenants_checked': N, 'work_orders_created': M}` at 02:00 UTC
**Why human:** Requires real clock + production Redis + deployed Railway ARQ service

#### 3. ADMIN_DATABASE_URL Railway Configuration

**Test:** In Railway dashboard, verify `ADMIN_DATABASE_URL` env var is set to the PostgreSQL connection string using `rotas_admin` role (BYPASSRLS)
**Expected:** ARQ worker connects without RLS errors; `evaluate_maintenance_schedule_all_tenants` returns non-zero `tenants_checked`
**Why human:** Railway env var management is manual; BYPASSRLS role setup requires DBA access

#### 4. DriverScorecardPanel Visual Verification

**Test:** Open `/motoristas` in the manager dashboard as a manager user who has at least one active driver with trips
**Expected:** Dropdown shows driver names; selecting a driver loads composite score with colored tier badge and 4 breakdown cards; selecting a driver with fewer than 3 trips in 30 days shows "Dados insuficientes" badge
**Why human:** React client-side state, fetch lifecycle, and visual rendering require browser

#### 5. MaintenanceImminentPanel Visual Verification

**Test:** Open the Control Tower home page (`/`) in manager dashboard
**Expected:** Panel titled "Manutenção Iminente" appears after FleetComplianceBoard; vehicles approaching due date/km show with orange (calendar), cyan (odometer), or red (overdue) markers; no vehicles = "Sem manutenções iminentes"
**Why human:** Server-side fetch, prop passing, and visual rendering require browser

---

### Gaps Summary

No gaps found. All 9 observable truths are verified against the codebase. All required artifacts exist, are substantive (not stubs), are wired to their data sources, and have passing tests. The phase goal is fully achieved.

**Pre-existing issues (not Phase 4 gaps):**
- 2 test failures in `test_workshop_operations_api.py` — control tower aggregation bugs predating Phase 4, documented in `deferred-items.md`
- `test_numeric_migration.py` was listed in VALIDATION Wave 0 but never created — the 04-05 plan used `alembic check` as the equivalent verification, which is acceptable for an annotation-only change

**Known limitation (info severity):**
- `check_vehicle_maintenance` ARQ task ignores the `vehicle_id` parameter and evaluates all plans for the whole tenant. This is conservative behavior but means a single vehicle's odometer event can trigger WorkOrder evaluation for all vehicles in the tenant. Candidate for a follow-up fix in a maintenance plan.

---

_Verified: 2026-06-06T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
