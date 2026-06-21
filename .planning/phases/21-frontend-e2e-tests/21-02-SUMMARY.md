---
phase: 21-frontend-e2e-tests
plan: "02"
subsystem: e2e-tests
tags: [playwright, e2e, ci, spec-files]
key_files:
  created:
    - apps/manager/e2e/auth.spec.ts
    - apps/manager/e2e/navigation.spec.ts
    - apps/manager/e2e/vehicles.spec.ts
    - apps/manager/e2e/drivers.spec.ts
    - apps/manager/e2e/billing.spec.ts
  modified:
    - .github/workflows/ci.yml
metrics:
  completed_date: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  tests_added: 10
---

# Phase 21 Plan 02: E2E Spec Files + CI Job — Summary

## One-liner
10 Playwright E2E tests across 5 spec files covering auth, navigation, vehicles, drivers, and billing; CI e2e job updated in ci.yml with `needs: [backend]`, postgres+redis services, seed step, HTML report artifact (30-day retention).

## What Was Built

### Spec files

| File | Tests | Coverage |
|------|-------|----------|
| `auth.spec.ts` | 3 | login success redirect, login error `p.login-error`, unauthenticated redirect to /login |
| `navigation.spec.ts` | 2 | dashboard sidebar Viaturas link, Motoristas link navigates to /motoristas |
| `vehicles.spec.ts` | 2 | list loads (table or empty state), detail shows "Apólices de Seguro" (graceful skip if empty) |
| `drivers.spec.ts` | 2 | list loads (table or empty state), detail page loads (graceful skip if empty) |
| `billing.spec.ts` | 1 | /cobranca shows "Cobrança de Transporte" title |

Total: **10 tests** confirmed by `npx playwright test --list` (11 including auth.setup.ts).

All spec files (except auth.spec.ts) inherit `storageState` from `playwright/.auth/user.json` via the `chromium` project config. `auth.spec.ts` explicitly overrides with `test.use({ storageState: { cookies: [], origins: [] } })` to test unauthenticated flows.

### CI e2e job
Runs after `backend` job passes (`needs: [backend]`). Starts postgres:16 + redis:7, runs migrations, seeds E2E user via `python -m pytest tests/seed_e2e.py -v`, starts backend (port 8000) + Next.js dev (port 3030), waits for both with `npx wait-on`, runs `npx playwright test --reporter=html`, uploads HTML report artifact (30-day retention).

## Verification

- `npx playwright test --list` — 10 tests across 5 spec files + 1 setup
- `python3 -c "import yaml; yaml.safe_load(...)"` — YAML valid
- `grep "name: E2E" .github/workflows/ci.yml` — E2E job present
- `grep "needs: \[backend\]"` — e2e depends only on backend (not frontend)
- `grep "retention-days: 30"` — 30-day artifact retention confirmed
- `grep "storageState.*cookies.*\[\]"` — auth tests clear saved state

## Deviations from Plan

None — plan executed as specified. The CI file already contained a prior draft of the e2e job; this execution updated it to the final spec (`needs: [backend]` only, `--reporter=html`, `retention-days: 30`, `NEXT_PUBLIC_API_URL` + `ROTAS_ALLOW_DEMO_FALLBACK` env vars).

## Known Stubs

None — all spec files assert real selectors against the live app.

## Self-Check: PASSED

All files exist and commits are present in git history.
