---
phase: 21
plan: RESEARCH
subsystem: frontend-testing
tags: [playwright, e2e, next-js, ci]
researched: 2026-06-21
---

# Phase 21: Frontend E2E Tests — Research

## ## RESEARCH COMPLETE

---

## 1. Current State of the Manager App

### Routes (26 pages)

| Route | File | Type |
|---|---|---|
| `/` | `app/page.tsx` | Dashboard (Server Component) |
| `/login` | `app/login/page.tsx` | Auth form (Client Component) |
| `/register` | `app/register/page.tsx` | Registration |
| `/viaturas` | `app/viaturas/page.tsx` | Vehicles list (Server Component) |
| `/viaturas/[id]` | `app/viaturas/[id]/page.tsx` | Vehicle detail (Client tabs) |
| `/viaturas/[id]/historico` | `app/viaturas/[id]/historico/page.tsx` | Vehicle history |
| `/motoristas` | `app/motoristas/page.tsx` | Drivers list (Server Component) |
| `/motoristas/[id]` | `app/motoristas/[id]/page.tsx` | Driver detail |
| `/viagens` | `app/viagens/page.tsx` | Trips |
| `/contratos` | `app/contratos/page.tsx` | Contracts |
| `/cobranca` | `app/cobranca/page.tsx` | Billing |
| `/ar` | `app/ar/page.tsx` | Accounts receivable |
| `/analytics` | `app/analytics/page.tsx` | Analytics + export buttons |
| `/manutencao` | `app/manutencao/page.tsx` | Maintenance |
| `/alertas` | `app/alertas/page.tsx` | Alerts |
| `/clientes` | `app/clientes/page.tsx` | Clients |
| `/terceiros` | `app/terceiros/page.tsx` | Third parties |
| `/settings` | `app/settings/page.tsx` | Settings |
| `/empresa` | `app/empresa/page.tsx` | Company profile |
| `/security` | `app/security/page.tsx` | Security settings |
| `/analytics` | `app/analytics/page.tsx` | Analytics + export buttons |

### Authentication Mechanism

**Login flow:**
1. `POST /api/auth/login` (Next.js API route proxy) — sends `{email, password}`
2. API route calls backend `POST /api/v1/auth/login`
3. On success: sets 6 httpOnly cookies: `rotas_access_token`, `rotas_tenant_id`, `rotas_user_id`, `rotas_role`, `rotas_full_name`, `rotas_refresh_token`
4. Client-side `router.push('/')` on success

**Session check (Server Components):**
```ts
await requireSession(); // reads rotas_access_token cookie; redirects to /login if absent
```

**Login form selectors** (no data-testid attributes currently):
- Email: `input[type="email"]`
- Password: `input[type="password"]`
- Submit: `button[type="submit"]` or `getByRole('button', { name: 'Entrar' })`
- Error: `p.login-error`

### Data Fetching Pattern

Server Components call `loadVehicles()`, `loadDrivers()` etc. which call `apiFetch()` → backend. This means:
- `page.route()` in Playwright **cannot** intercept server-side fetches (they happen Node.js → backend)
- For E2E tests to see data, the backend must be running OR we use `page.route()` to intercept the **Next.js API routes** (the proxy routes under `/api/*`)

**Resolution**: CI should run the backend as a service (already done in `ci.yml` `backend` job). The E2E job should start both `next dev` and the backend.

### Current Package.json (apps/manager)

```json
"devDependencies": {
  "@types/node": "^20.0.0",
  "@types/react": "^18.3.0",
  "@types/react-dom": "^18.3.0",
  "autoprefixer": "^10.5.0",
  "postcss": "^8.4.31",
  "tailwindcss": "^3.4.19",
  "typescript": "^5.5.0"
}
```

**No test framework currently**. Scripts: `dev`, `build`, `start`, `lint`, `typecheck` — no `test` or `e2e` script.

### CI Pipeline (`ci.yml`)

Two jobs:
- `backend`: pytest with PostgreSQL 16 + Redis 7 services
- `frontend`: typecheck + next build (no E2E)

---

## 2. Playwright + Next.js 14 App Router — Key Decisions

### Auth State Approach

Playwright's `storageState` captures cookies (including httpOnly). The correct pattern:

```typescript
// e2e/auth.setup.ts
import { test as setup } from '@playwright/test';
const authFile = 'playwright/.auth/user.json';
setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.locator('input[type="email"]').fill(process.env.E2E_EMAIL ?? 'test@rotas.local');
  await page.locator('input[type="password"]').fill(process.env.E2E_PASSWORD ?? 'testpass');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await page.waitForURL('/');
  await page.context().storageState({ path: authFile });
});
```

Then in `playwright.config.ts`:
```typescript
projects: [
  { name: 'setup', testMatch: '**/auth.setup.ts' },
  {
    name: 'chromium',
    use: { ...devices['Desktop Chrome'], storageState: 'playwright/.auth/user.json' },
    dependencies: ['setup'],
  }
]
```

### webServer Configuration

For local dev (not CI), Playwright can auto-start the Next.js server:
```typescript
webServer: {
  command: 'npm run dev',
  url: 'http://localhost:3030',
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
}
```

In CI, we start the server manually before the Playwright job.

### Selector Strategy (No data-testid currently)

Since the codebase has no `data-testid` attributes, use these resilient selectors:
- Form inputs: `input[type="email"]`, `input[type="password"]`, `input[type="text"]`
- Buttons by role+name: `getByRole('button', { name: '...' })`
- Links by role+name: `getByRole('link', { name: '...' })`
- Table rows: `getByRole('row')`
- CSS class selectors for app-specific elements: `.login-error`, `.panel`, `.table`
- Navigation: sidebar links by their text content (e.g., "Viaturas", "Motoristas")

**Recommendation**: Add `data-testid` to critical interactive elements during Phase 21 implementation — this makes selectors stable across visual refactors.

### Server-Side Data Problem

For tests that load pages with server-fetched data (vehicle list, driver list etc.):
- Tests require a running backend with real data **OR** the pages need seed data in the test database
- CI will run backend + run alembic + have a seeded test user
- Local dev: tests run against local dev stack

**Approach for data-dependent tests**:
- Create a test user in the backend (seed via Alembic data migration or fixture endpoint)
- Test pages load but check for structure (table headers, empty states) rather than specific data values
- This avoids brittle data dependencies

---

## 3. What to Test (Priority Order)

### Critical Path Tests (must have)

| Test | Route | What to assert |
|---|---|---|
| Login happy path | `/login` | Redirects to `/` after valid credentials |
| Login bad credentials | `/login` | `.login-error` visible with error text |
| Unauthenticated redirect | `/viaturas` | Redirects to `/login` |
| Dashboard loads | `/` | Page title or sidebar visible |
| Vehicles list loads | `/viaturas` | Table or empty state visible (no JS error) |
| Vehicle detail loads | `/viaturas/[id]` | Tabs visible including "Seguros" |
| Drivers list loads | `/motoristas` | Table or empty state visible |
| Driver detail loads | `/motoristas/[id]` | Page renders without error |
| Billing list loads | `/cobranca` | Page renders (Faturação section) |

### Nice to Have

| Test | Route | What to assert |
|---|---|---|
| Third parties list | `/terceiros` | Table or empty state visible |
| Analytics loads | `/analytics` | KPI cards visible, export buttons render |
| Maintenance loads | `/manutencao` | Tabs render |
| Sidebar navigation | Any | Clicking links navigates correctly |

---

## 4. CI Job Design

```yaml
# New job in .github/workflows/ci.yml
e2e:
  name: E2E
  runs-on: ubuntu-latest
  needs: [backend, frontend]  # both must pass first
  services:
    postgres:
      image: postgres:16
      env: { POSTGRES_DB: rotas, POSTGRES_USER: rotas, POSTGRES_PASSWORD: rotas }
      ports: ["5432:5432"]
      options: --health-cmd "pg_isready -U rotas" --health-interval 10s --health-retries 5
    redis:
      image: redis:7
      ports: ["6379:6379"]
  env:
    ENVIRONMENT: test
    JWT_SECRET_KEY: test-secret-at-least-32-chars-long-abc
    DATABASE_URL: postgresql+asyncpg://rotas:rotas@localhost:5432/rotas
    REDIS_URL: redis://localhost:6379
    NEXT_PUBLIC_API_URL: http://localhost:8000
    ROTAS_ALLOW_DEMO_FALLBACK: "1"
    E2E_EMAIL: e2e@rotas.local
    E2E_PASSWORD: E2eP@ss2024!
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with: { python-version: "3.11" }
    - uses: actions/setup-node@v4
      with: { node-version: "20", cache: npm }
    - name: Install backend
      working-directory: backend
      run: pip install -e ".[dev]"
    - name: Run migrations + seed E2E user
      working-directory: backend
      run: |
        python -m alembic upgrade head
        python -m pytest tests/seed_e2e.py -v  # or a seed script
    - name: Start backend
      working-directory: backend
      run: uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    - name: Install npm deps
      run: npm ci
    - name: Install Playwright browsers
      working-directory: apps/manager
      run: npx playwright install --with-deps chromium
    - name: Start Next.js
      working-directory: apps/manager
      run: npm run dev &
    - name: Wait for servers
      run: |
        npx wait-on http://localhost:8000/health http://localhost:3030 --timeout 60000
    - name: Run E2E tests
      working-directory: apps/manager
      run: npx playwright test --reporter=html
    - name: Upload Playwright report
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: playwright-report
        path: apps/manager/playwright-report/
        retention-days: 30
```

**Note on `needs`**: `e2e` should depend on `backend` passing (tests pass) but not necessarily on `frontend` build — we start `next dev` directly. Change `needs: [backend]` for faster CI.

---

## 5. E2E User Seeding

Need a way to create an E2E test user in the test DB. Options:

**Option A**: Seed script `backend/tests/seed_e2e.py` that calls the registration endpoint or directly inserts via SQLAlchemy. Called from CI before starting server.

**Option B**: `POST /api/v1/tenants` (platform admin) to create tenant + user. Requires platform admin credentials.

**Option C**: Alembic data migration that inserts a fixed test user (bad — test data in migrations).

**Recommendation**: Option A — a pytest script that creates a test tenant + owner user with known credentials. Already have the `POST /api/v1/auth/register` or similar endpoint. Check `apps/manager/app/register/page.tsx` for the registration flow.

---

## 6. Playwright Config Template

```typescript
// apps/manager/playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false, // auth setup must run first
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:3030',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'setup',
      testMatch: '**/auth.setup.ts',
    },
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'playwright/.auth/user.json',
      },
      dependencies: ['setup'],
    },
  ],
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:3030',
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
```

---

## 7. Test File Structure

```
apps/manager/
  e2e/
    auth.setup.ts          # Login → save storageState
    auth.spec.ts           # Login happy/sad paths, logout
    navigation.spec.ts     # Sidebar links, page titles
    vehicles.spec.ts       # /viaturas list, /viaturas/[id] detail + Seguros tab
    drivers.spec.ts        # /motoristas list, /motoristas/[id] detail
    billing.spec.ts        # /cobranca list, pagination
  playwright/.auth/
    user.json              # Saved auth state (gitignored)
  playwright.config.ts
```

---

## 8. Key Risks

| Risk | Mitigation |
|---|---|
| Server-side data fetches fail in CI | Seed test user + tenant before tests; check empty states not specific data |
| httpOnly cookie not captured by storageState | Not an issue — Playwright captures all cookies including httpOnly |
| Next.js dev server slow to start | `wait-on` with 60s timeout; `reuseExistingServer: true` locally |
| Flaky tests due to network timing | Use `waitForURL`, `waitForLoadState('networkidle')`, `expect().toBeVisible()` with timeout |
| No data-testid in existing components | Use semantic selectors + add data-testid to key elements during implementation |
| CI cost (E2E is slow) | Only run on PR; use `--project=chromium` (one browser); parallel: false |

---

## 9. Seed Script Design

```python
# backend/tests/seed_e2e.py
"""Run with: python -m pytest tests/seed_e2e.py -v"""
import asyncio
import pytest
from app.database import async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.tenants.service import create_tenant
from app.modules.users.service import create_user

@pytest.mark.asyncio
async def test_seed_e2e_user():
    async with AsyncSession(async_engine) as db:
        # Create test tenant if not exists
        tenant = await create_tenant(db, {"name": "E2E Test", "slug": "e2e-test", "plan": "basic"})
        # Create owner user
        user = await create_user(db, {
            "email": "e2e@rotas.local",
            "password": "E2eP@ss2024!",
            "full_name": "E2E Test User",
            "role": "owner"
        }, tenant_id=tenant["id"])
        assert user["email"] == "e2e@rotas.local"
```

---

## 10. Validation Architecture

### Tests to write (9 tests across 4 spec files)

1. `auth.setup.ts` — 1 setup (not counted as test)
2. `auth.spec.ts` — 3 tests: login success, login failure, unauthenticated redirect
3. `navigation.spec.ts` — 2 tests: dashboard loads, sidebar link navigation
4. `vehicles.spec.ts` — 2 tests: list loads, detail + Seguros tab
5. `drivers.spec.ts` — 1 test: list loads
6. `billing.spec.ts` — 1 test: /cobranca loads

Total: **9 E2E tests** across 5 files.

### Acceptance criteria (phase level)
- `npx playwright test` exits 0 in CI with PostgreSQL + Redis services
- HTML report generated at `playwright-report/`
- No test depends on specific data values — only structure (table headers, empty states, page titles)
