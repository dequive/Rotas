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
| F0 | Branch + flags + log | this session | in progress |
| F1 | Alembic: DDL for HR/Inventory/Accounting | depends on F2 schemas | pending |
| F2 | Backend import (Accounting + HR + main.py) | this session | next |
| F3 | Manager typecheck (49 errors) | depends on Backend contracts | pending |
| F4 | Transaction boundaries (services flush) | parallel to F5 | pending |
| F5 | RLS + GRANT complete | depends on F1 | pending |
| F6 | RBAC for ERP modules | depends on F2 | pending |
| F7 | BFF-only Manager | depends on F3 | pending |
| F8 | Governance Engine outbox + retry | parallel, needs DB | pending |

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

(empty — append entries as they appear)

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
