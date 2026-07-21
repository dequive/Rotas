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
| F6 | Governance outage + outbox (drain + retry) | parallel | done (commit 4581162) |
| F7 | BFF strategy component | parallel | done — catch-all proxy + bff helper (new commit) |

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
- F7 introduced `/api/proxy/route.ts` and `lib/bff.ts` so client components
  no longer need to read tokens from `localStorage`. Existing 18 client
  components still read tokens locally; migration to the BFF proxy is
  scheduled for P1 (per-module route handlers take precedence).

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
