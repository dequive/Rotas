---
phase: 4
slug: production-hardening-scale-preparation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-asyncio |
| **Config file** | `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `cd backend && python -m pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `cd backend && python -m pytest tests/ -v --timeout=60` |
| **Estimated runtime** | ~30 seconds (quick), ~90 seconds (full) |

---

## Sampling Rate

- **After every task commit:** Run `cd backend && python -m pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `cd backend && python -m pytest tests/ -v --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | MAINT-01 | unit | `pytest tests/test_maintenance_scheduler.py -x -q` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 1 | MAINT-01 | integration | `pytest tests/test_maintenance_scheduler.py -x -q` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 1 | MAINT-01 | integration | `pytest tests/test_maintenance_scheduler.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | — | unit | `pytest tests/test_driver_scorecard.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | — | integration | `pytest tests/test_driver_scorecard.py -x -q` | ❌ W0 | ⬜ pending |
| 4-03-01 | 03 | 1 | — | migration | `cd backend && alembic upgrade head && alembic downgrade -1` | ✅ | ⬜ pending |
| 4-03-02 | 03 | 2 | — | schema | `pytest tests/test_numeric_migration.py -x -q` | ❌ W0 | ⬜ pending |
| 4-04-01 | 04 | 2 | — | performance | `pytest tests/test_composite_indexes.py -x -q` | ❌ W0 | ⬜ pending |
| 4-05-01 | 05 | 2 | — | manual | N/A — deployment config | N/A | ⬜ pending |
| 4-06-01 | 06 | 3 | — | integration | `pytest tests/test_rls.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_maintenance_scheduler.py` — stubs for MAINT-01 (ARQ worker trigger, work order creation, dual-trigger odometer + calendar)
- [ ] `backend/tests/test_driver_scorecard.py` — stubs for scorecard aggregation endpoint
- [ ] `backend/tests/test_numeric_migration.py` — stubs verifying all monetary columns are Numeric(x,y) after annotation cleanup
- [ ] `backend/tests/test_composite_indexes.py` — stubs verifying index existence on priority tables
- [ ] `backend/tests/test_rls.py` — stubs for RLS cross-tenant isolation (if RLS is implemented)
- [ ] Wave 0 also installs `arq`, `gunicorn`, `redis[asyncio]` packages — required before integration tests can run

*Existing `backend/tests/conftest.py` and pytest infrastructure covers shared fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Gunicorn multi-worker startup on Railway | — | Deployment config, not testable in local CI | Deploy to Railway staging, verify `gunicorn -w 4` workers appear in Railway logs |
| ARQ worker daily cron fires in production | MAINT-01 | Requires real clock + production Redis | Monitor Railway logs 24h after deploy for `maintenance_check` job execution |
| `ADMIN_DATABASE_URL` env var set in Railway | — | Railway env var management | Verify in Railway dashboard: `ADMIN_DATABASE_URL` points to same DB with `rotas_admin` role |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
