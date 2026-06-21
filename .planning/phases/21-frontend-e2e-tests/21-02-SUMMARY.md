# Plan 21-02 — E2E Spec Files + CI Job

**Status:** Complete  
**Date:** 2026-06-21  

## What Was Done

### 5 Playwright spec files created under `apps/manager/e2e/`

| File | Tests | Notes |
|------|-------|-------|
| `auth.spec.ts` | 3 | Uses `storageState: { cookies: [], origins: [] }` — no saved auth |
| `navigation.spec.ts` | 2 | Sidebar Viaturas link + Motoristas navigation |
| `vehicles.spec.ts` | 2 | List loads + detail shows "Apólices de Seguro"; graceful skip if empty |
| `drivers.spec.ts` | 2 | List loads + detail loads; graceful skip if empty |
| `billing.spec.ts` | 1 | Billing page title "Cobrança de Transporte" visible |

Total: **10 tests** confirmed by `npx playwright test --list`.

### CI job added to `.github/workflows/ci.yml`

- `e2e` job depends on `backend` and `frontend` passing
- Services: `postgres:16` + `redis:7` (same config as backend job)
- Steps: install Python + Node → init DB roles → migrations → seed E2E user → start uvicorn → install npm deps → install Playwright chromium → start Next.js dev → wait-on `/health` + `http://localhost:3030` → `npx playwright test`
- HTML report uploaded as artifact (14-day retention) on `if: always()`

## Acceptance Criteria Met

- `npx playwright test --list` shows 10 tests in 5 spec files ✓
- Auth tests correctly opt-out of saved storageState ✓  
- Graceful skip for vehicles/drivers detail when E2E tenant has no data ✓
- CI job seeds DB before running tests ✓
- Report artifact always uploaded for debugging failures ✓
