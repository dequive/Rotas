---
phase: 9
slug: postgresql-rls-policies
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-06
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.2 + pytest-asyncio 0.23 (`asyncio_mode = "auto"`) |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `cd backend && python -m pytest tests/test_rls.py -x -v` |
| **Full suite command** | `cd backend && python -m pytest tests/test_rls.py tests/test_cross_tenant_isolation.py -v` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** `cd backend && python -m pytest tests/test_rls.py -x -v`
- **After every plan wave:** `cd backend && python -m pytest tests/test_rls.py tests/test_cross_tenant_isolation.py -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~20 seconds

---

## Per-Task Verification Map

| Task ID | Req | Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-----|----------|-----------|-------------------|-------------|--------|
| 09-W0-01 | RLS-01 | All tenant tables have policy | integration | `pytest tests/test_rls.py::test_rls_all_tenant_tables_have_policy -x` | ❌ Wave 0 | ⬜ pending |
| 09-01 | RLS-01 | tenant_isolation policy exists on trips table | integration | `pytest tests/test_rls.py::test_rls_tenant_isolation_policy_exists -x` | ✅ | ⬜ pending |
| 09-02 | RLS-01 | SET LOCAL is transaction-scoped | integration | `pytest tests/test_rls.py::test_rls_set_local_scoped_to_transaction -x` | ✅ | ⬜ pending |
| 09-03 | RLS-02 | ALEMBIC_DATABASE_URL bypasses RLS | deployment | `alembic upgrade head` (Railway deploy log) | Deploy-time | ⬜ pending |
| 09-04 | RLS-03 | Cross-tenant trip access blocked | integration | `pytest tests/test_rls.py::test_rls_blocks_cross_tenant_trip_access -x` | ✅ | ⬜ pending |
| 09-05 | RLS-03 | Cross-tenant vehicle/driver blocked | integration | `pytest tests/test_cross_tenant_isolation.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_rls.py::test_rls_all_tenant_tables_have_policy` — completeness gate: count of `pg_policies` WHERE `policyname = 'tenant_isolation'` equals expected count of tenant-scoped tables

*Existing `test_rls.py` and `test_cross_tenant_isolation.py` cover all other requirements — no new test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `pg_policies` count = expected table count | RLS-01 | SQL query against live DB | `SELECT count(*) FROM pg_policies WHERE policyname LIKE 'rls_%'` — must match expected count |
| Alembic runs clean after RLS enabled | RLS-02 | Railway deployment step | Check Railway deploy logs after enabling `ALEMBIC_DATABASE_URL` |
| ARQ worker uses `ADMIN_DATABASE_URL` | RLS-02 | Runtime verification | Confirm `backend/app/worker.py` uses `resolved_admin_database_url` |
| Role passwords set in Railway | RLS-02 | Railway console | Run `ALTER ROLE rotas_app PASSWORD '...'` and `ALTER ROLE rotas_admin PASSWORD '...'` as one-time admin SQL |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
