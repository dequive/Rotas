---
phase: 21-frontend-e2e-tests
plan: "01"
subsystem: testing-scaffold
tags: [playwright, e2e, auth-setup, seed]
key_files:
  created:
    - apps/manager/playwright.config.ts
    - apps/manager/e2e/auth.setup.ts
    - apps/manager/.gitignore
    - backend/tests/seed_e2e.py
  modified:
    - apps/manager/package.json
    - package-lock.json
decisions:
  - Use engine (not async_engine) from app.database — the exported name is engine per database.py
  - Playwright 1.61.0 already present in package.json (newer than required 1.44.0) — kept as-is
  - Tenant constructor uses all-nullable optional fields with defaults — minimal constructor is correct
  - seed_e2e.py imports engine directly and wraps with AsyncSession (no async_engine alias needed)
metrics:
  completed_date: "2026-06-21"
  tasks_completed: 3
  tasks_total: 3
  duration_minutes: 15
---

# Phase 21 Plan 01: Playwright Scaffold — Summary

## One-liner
Playwright installed with two-project config (setup → chromium), auth.setup.ts saves storageState after login, seed script provisions e2e@rotas.local owner user with mfa_enabled=False using the project's scrypt hash_password.

## What Was Built

### apps/manager/playwright.config.ts
Two projects: `setup` (testMatch `**/auth.setup.ts`) and `chromium` (depends on setup, uses `storageState: 'playwright/.auth/user.json'`). baseURL defaults to `http://localhost:3030`. webServer auto-starts `npm run dev` for local runs; CI must start it manually (`process.env.CI` guard). Timeout 30s, expect timeout 5s.

### apps/manager/e2e/auth.setup.ts
Fills `input[type="email"]` and `input[type="password"]`, clicks `getByRole('button', { name: 'Entrar' })`, awaits redirect to `/` with 15s timeout, then calls `page.context().storageState({ path: authFile })` to save all cookies including httpOnly session cookies (`rotas_access_token`, `rotas_tenant_id`, etc.) to `playwright/.auth/user.json`.

### apps/manager/.gitignore
Excludes `playwright/.auth/` (session cookies must never be committed), `playwright-report/`, and `test-results/`.

### backend/tests/seed_e2e.py
Idempotent: queries for existing `e2e-test` tenant and `e2e@rotas.local` user before creating. Uses `app.core.passwords.hash_password` (scrypt, stdlib). Sets `mfa_enabled=False` explicitly — MFA challenge would break the headless auth flow. On repeated runs refreshes password hash and re-asserts `mfa_enabled=False`. Runs as `pytest.mark.asyncio` test via `python -m pytest tests/seed_e2e.py -v`.

## Verification

- `npx playwright --version` → `Version 1.61.0`
- `npx playwright test --list` → `[setup] › auth.setup.ts:6:6 › authenticate as E2E user`
- `grep "playwright/.auth" apps/manager/.gitignore` → matches
- `grep "storageState" apps/manager/e2e/auth.setup.ts` → matches
- `.venv/Scripts/python -c "import tests.seed_e2e; print('syntax OK')"` → `syntax OK`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Engine import name correction**
- **Found during:** Task 3
- **Issue:** Plan mentioned `from app.database import async_engine` but `database.py` exports `engine` (the `create_async_engine` result). The pre-existing seed file already used the correct name.
- **Fix:** Confirmed seed_e2e.py uses `from app.database import engine` and wraps with `AsyncSession(engine)`.
- **Files modified:** backend/tests/seed_e2e.py (pre-existing, correct)
- **Commit:** bbde8cf

**2. [Observation] All files pre-existed**
- `apps/manager/e2e/auth.setup.ts` and `backend/tests/seed_e2e.py` were already created (untracked in git). Content matched plan spec exactly — no changes required.
- `package.json` already had `@playwright/test ^1.61.0` and all three e2e scripts.
- Only new files created: `playwright.config.ts` and `.gitignore`.

## Known Stubs

None — this plan only scaffolds infrastructure (config files and a seed script). No UI components or data flows involved.

## Self-Check: PASSED

- apps/manager/playwright.config.ts: FOUND
- apps/manager/e2e/auth.setup.ts: FOUND
- apps/manager/.gitignore: FOUND
- backend/tests/seed_e2e.py: FOUND
- Commit bbde8cf: FOUND
