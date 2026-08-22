# Stabilization Log — P0 / P1 / P2

> Tracking for the rotation period `stabilization/p0-2026-q3`.
> Goal: bring ROTAS to pilot readiness without rewriting the architecture.

## Plan

Three phases executed sequentially. Each phase is gated on the previous one
returning green CI.

- **P0 — Restore integrity (no new features).** Goals: backend imports, Alembic
  tree solid, Manager typechecks, RLS + GRANT complete, RBAC for ERP modules,
  transaction boundaries defined, Governance Engine wired via transactional
  outbox + retry.
- **P1 — Close architectural boundaries.** Goals: canonical Accounting
  contracts, OpenAPI-driven Manager types, BFF-only strategy, sync hardening,
  Service Worker identity isolation, runtime contract validation, features
  hidden behind flags.
- **P2 — Pilot preparation.** Goals: migration smoke on empty/prod-snapshot
  DBs, load tests for sync/concurrency/photo upload, backup/restore + DR
  validation, vulnerability sweep, Go-Live checklist with hard acceptance
  criteria.

## Fronts (executed in order)

| ID | Front | Owner-fronter | Status |
|---|---|---|---|
| F0 | Branch + flags + log | this session | done (commit aca0248) |
| F1 | Backend import (Accounting + HR + main.py) | this session | done (commit aca0248) |
| F2 | Alembic: DDL for HR/Inventory/Accounting | depends on F1 | done (commit c51c1b0) |
| F3 | Manager typecheck (49 errors → 0) | depends on F2 | done (commit e176a6a) |
| F4 | RLS + GRANT complete tables | depends on F2 | done (commit 64a88a5) |
| F5 | RBAC for ERP modules | depends on F3 | done (commit 907ce34) |
| F6 | Governance outage + outbox (drain + retry) | parallel | done_local — produtores transaccionais, contrato, retry/dead-letter e runtime real validados; promocao operacional pendente |
| F7 | BFF strategy component | parallel | done_local — browser sem token persistido, BFF/refresh e entitlement cobertos; E2E de seguranca pendente |

## Decisions log

- 2026-Q3: Keep mono-modular architecture — no rewrite, no new micro-service.
- 2026-Q3: Canonical names in Accounting are `JournalEntry*` and
  `JournalItem*`. Legacy names (`ManualEntryCreate`, `ManualEntryItem`) are
  removed in P1.1 — no aliases.
- 2026-Q3: Alembic stays single-head. `95929ae669b9` remains idempotent; new
  DDL lives in downstream migrations.
- 2026-Q3: Services `flush()`, routers `commit()` via `async with session.begin()`.
- 2026-Q3: All Manager tokens stay on the BFF (server side). Zero
  `localStorage.*token` reads in `apps/manager/**\/*.tsx`.
- 2026-Q3: Governance Engine integration runs through a transactional outbox
  table with exponential backoff and a dead-letter state. `asyncio.create_task`
  on critical paths is banned.

## Regressions / discoveries

- Empty Alembic migration bodies (`95929ae669b9`) caused `IndentationError`
  breaking `alembic heads`. Restored with explicit `pass`.
- `HR` service imported `ManualEntryItemCreate` (legacy); renamed to the
  canonical `JournalItemCreate` via Pydantic alias shims so callers and the
  ORM stay compatible.
- `payables/router.py` resolved `account_id` via `account_number` PGC-NIRF
  codes. Centralised the resolution inside `create_journal_entry()`.
- `inventory-api.ts` read tokens from `localStorage`; refactored to
  `apiFetch()` (BFF token resolution only).
- `StatCard` component previously not implemented; wrapped as alias of
  `KpiCard` so existing pages continue to render.
- Manager `Button` did not accept the `"outline"` variant; added it as a
  dual alias of `ghost`.
- F7 introduced `/api/proxy/route.ts` and `lib/bff.ts`; the Manager no longer
  persists bearer tokens in browser storage/cookies acessiveis a JavaScript.
  Refresh and entitlement boundaries are covered locally; security E2E and
  pentest remain release evidence.

## Revalidation — 2026-07-25

- The current frontend source/build baseline is green: Manager 74 tests,
  Driver 12 tests, both typechecks, Manager Next 16.2.11 build (72 pages) and
  Driver React 19/PWA build (1,805 modules, precache 6). Backend and Governance
  Ruff are green. A fixed release-candidate SHA and remote CI reproduction
  remain mandatory before G0 can be promoted from yellow to green.
- Alembic is single-head at `rec09`. A temporary PostgreSQL database created
  from zero upgraded through the complete history, `alembic check` reported no
  drift and the complete backend suite passed against that canonical schema.
  PR-05 production snapshot upgrade/restore remains mandatory.
- RLS now uses the canonical `tenant_isolation` policy on every known
  tenant-scoped table except the explicitly designed `files` boundary. The RLS
  completeness test and full backend suite pass.
- Manager rate-limit tests are order-independent; owner/admin/manager workshop
  permissions include the new reception/quote capabilities.
- F6 is locally closed at the engineering boundary: critical producers enqueue
  in the business transaction; the drainer uses
  `/api/v1/adapters/rotas/events`, `X-API-Key`, 409 idempotency, bounded retry,
  dead-letter and `SKIP LOCKED`. A live local event created and authenticated a
  Governance case. Operational replay/reconciliation/alerts still block
  production promotion.
- F7 is locally closed at the code boundary: browser token persistence and
  direct bearer use were removed, refresh is mediated by the BFF, and tenants
  cannot self-upgrade product entitlements. Security E2E and pentest remain.
- The onboarding register/verify flow now crosses the Manager BFF and stores
  credentials only in HttpOnly cookies. The generic BFF proxy fails closed
  without a complete session, rejects non-allowlisted targets, preserves the
  intended upstream query and maps network failure to a typed 502 response.
- Canonical production plan, owners, dependencies, evidence and GO/NO-GO gates
  now live in `docs/ROTAS_MASTER_DELIVERY_PLAN.md`, section 15.
- The Manager runtime moved to Next 16.2.11, Sentry 10.67.0 and React 19.2.4.
  The obsolete instrumentation flag and middleware convention were removed.
- PR-18 is upstream-blocked: the current stable Next release itself installs
  PostCSS 8.4.31 and Sharp 0.34.5, while the current Sharp advisory requires
  0.35.0 or newer. A forced Next 9 downgrade is rejected as unsafe.
- The current backend suite completed with 563 passed and 1 skipped in
  440.54 seconds against a temporary PostgreSQL database migrated to `rec09`.
  The first repeat exposed an important environment defect: the historical
  default development database declared `rec09` while physically missing
  composite indexes. Revision labels alone are therefore not accepted as
  schema parity evidence; clean migration and physical invariant tests remain
  mandatory.
- Residual quality debt: Vite toolchain/canvas-test warnings and historical
  migration style remain. None is recorded as runtime proof of failure, but
  each remains tracked before final premium release.

## Revalidation — 2026-08-22

- The Manager/OpenAPI contract auditor is green for the first time:
  `npm run verify:api-contracts` reports 208 references, 158 operations and
  **0 violations**, down from 72 empty `2xx` schemas. Every operation the
  Manager calls now declares a response schema, and binary endpoints (PDF,
  XLSX, file download) declare their media type through
  `backend/app/core/openapi_responses.py` instead of returning an empty
  contract. `test_openapi_contract` is 9/9 against the committed
  `openapi/rotas-v1.json`.
- Full backend suite: 728 passed, 1 skipped. Manager: `tsc --noEmit` clean and
  124/124 unit tests across 32 files. `ruff check app/` clean.
- Typing the responses exposed a real defect class rather than only closing a
  gate: `GET/PUT /tenants/me/driver-despacho-table` began silently dropping
  `entry_mode` because the response model reused the write schema. Tenant
  despacho tables live inside `tenant.compliance_policy`, so the read contract
  now allows the stored provenance fields through explicitly. Response models
  are therefore treated as truncation risk, not documentation.
- Environment defect, not a schema defect: `backend/.env` pointed
  `DATABASE_URL` at port 5440, which is another project's Postgres container
  (`mozaia_postgres`). It carried a stale ROTAS schema at alembic head `rec15`
  from the unmerged PR #25, including an orphan `trip_document_requests`
  table, and it was the sole cause of the RLS completeness test failing. The
  project's own `rotas-postgres` container on 55432 was healthy at `rec13`,
  this branch's head. Repointing `.env` was the entire fix; no data was
  destroyed. Database state that looks impossible must be checked against the
  configured port before any rebuild is considered.
- Two test defects fixed while proving the above: NUIT fixtures in
  `test_third_party.py` used `uuid4().hex[:5]`, whose hex letters fail the
  9-digit validator on most runs; and the long-standing E501 in the
  `ThirdParty` docstring.

## Acceptance gates

- **P0 green** when:
  - `python -c "from app.main import app"` returns no error,
  - `alembic heads` returns exactly one head,
  - `alembic upgrade head` against an empty DB succeeds,
  - `tsc --noEmit` in `apps/manager` returns 0 errors,
  - `pytest --collect-only` collects the 87 backend tests,
  - `ruff check backend/app` returns 0 F821/F823/F811.

- **P1 green** when:
  - OpenAPI-generated Manager types replace ad-hoc types,
  - Service Worker caches are keyed by `(tenant_id, driver_id)`,
  - 401 in sync triggers refresh-token flow,
  - Dead-letter queue is user-visible for ops.

- **P2 / Go-Live** when:
  - One week of CI green on `main`,
  - One real driver/tenant exercises the app end-to-end,
  - Runbook for incident response documented,
  - Latency P95 < 500ms sync batch, < 200ms GET read paths.
