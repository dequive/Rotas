# PR-04 — Empty Database Migration Evidence

Date: 2026-08-08
Branch: `codex/pr04-alembic-empty-db`
Base: PR-02 commit `26caedc5fe8aac0b0327e0ca8f29285268f785ed`

## Scope

This evidence covers the PR-04 acceptance criterion only: a new PostgreSQL
database must migrate from no schema to the single Alembic head, expose the
expected tenant-isolation controls, and match the SQLAlchemy metadata.

It does not certify upgrade from a populated historical snapshot. That remains
the separate PR-05 gate.

## Defects corrected

- Restored the missing migration chain from `1e006dfe187d` through `rec13`.
- Repaired `782fcb33513c`, which attempted to index `document_type` before the
  canonical chain created the column.
- Repaired the Payables migration so its upgrade creates all aggregate tables
  and its downgrade no longer mutates unrelated GPS, insurance or trip schema.
- Made the HR/inventory reconciliation fail closed for partial or divergent
  legacy snapshots.
- Registered the five supplemental workshop model modules before Alembic
  metadata comparison.
- Aligned inventory timestamps/UUID defaults, route-optimization columns,
  workshop detail fields and insurance FK actions with the physical schema.

## Reproduced evidence

Final isolated database: `rotas_pr04_final_20260808` on local PostgreSQL 16.

```text
alembic heads:                 rec13 (head)
alembic upgrade head:          PASS from an empty database
alembic current:               rec13 (head)
alembic check:                 No new upgrade operations detected
public base tables:            123
RLS enabled tables:            113
FORCE RLS tables:              113
non-partition tenant tables
without ENABLE/FORCE RLS:      0
```

The four apparent unprotected tenant tables are physical GPS partitions. Their
parent `gps_positions` has both RLS and FORCE RLS enabled.

Quality gates on the same candidate content:

```text
Backend pytest:                530 passed, 1 skipped, 1 warning
Pyright app + tests:           0 errors, 0 warnings
Ruff CI scope:                 PASS
Ruff changed migrations:       PASS
compileall app/tests/alembic:   PASS
git diff --check:              PASS
Migration metadata regression: 2 passed
```

## Residual observations

`alembic check` still reports SQLAlchemy warnings for mutually dependent
foreign keys and an upstream/reflection `dialect_options` argument. They do not
produce migration operations and did not prevent the empty-database gate, but
they remain technical debt for later constraint-graph cleanup.

The existing Pydantic class-based `Config` deprecation warning is unchanged and
outside this migration-only scope.

## Decision

PR-04 is `done_local`. G1 remains yellow until PR-05 proves a populated,
representative snapshot upgrade and the candidate is reproduced by remote CI.
