# Technology Stack
_Last updated: 2026-06-04_

## Summary

ROTAS is a monorepo containing three sub-projects: a Python FastAPI backend, a Next.js manager web app, and a Vite + React PWA for drivers. The backend uses Python 3.11+ with async SQLAlchemy and PostgreSQL. Both frontends use TypeScript 5.5 and React 18.3. The project is in early MVP state (v0.1.0) with no production deployment configuration present.

---

## Languages

**Primary:**
- Python 3.11+ — backend API (`backend/`)
- TypeScript 5.5 — both frontend apps (`apps/driver/`, `apps/manager/`)

**Secondary:**
- HTML/CSS — `apps/driver/index.html`, `apps/manager/app/globals.css`

---

## Runtime

**Backend:**
- Python >= 3.11 (declared in `backend/pyproject.toml`)
- ASGI server: Uvicorn `>=0.29` with `[standard]` extras (websocket/http2 support)

**Frontend:**
- Node.js (version unspecified — no `.nvmrc` or `.node-version` file)
- npm workspaces (root `package.json` manages `apps/*`)

---

## Package Managers

**JavaScript:** npm (root `package-lock.json` present)
- Workspace layout: `apps/driver`, `apps/manager`

**Python:** pip with `pyproject.toml` (PEP 517)
- Build backend: `setuptools>=69` + `wheel`
- Virtual environment: `backend/.venv/` (committed, not gitignored per current state)

---

## Frameworks

### Backend — `backend/`

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | `>=0.111` | HTTP API framework, ASGI |
| `sqlalchemy[asyncio]` | `>=2.0` | ORM + async query layer |
| `alembic` | `>=1.13` | Database migrations |
| `pydantic-settings` | `>=2.2` | Settings via env vars (`backend/app/config.py`) |
| `uvicorn[standard]` | `>=0.29` | ASGI server |
| `python-jose[cryptography]` | `>=3.3` | JWT signing/verification (HS256 algorithm) |
| `python-multipart` | `>=0.0.9` | File upload parsing |
| `asyncpg` | `>=0.29` | Async PostgreSQL driver (used by SQLAlchemy) |
| `psycopg[binary]` | `>=3.1` | Sync Psycopg3 driver (used by Alembic migrations) |

### Driver PWA — `apps/driver/`

| Package | Version | Purpose |
|---|---|---|
| `react` | `^18.3.0` | UI framework |
| `react-dom` | `^18.3.0` | DOM renderer |
| `dexie` | `^4.0.0` | IndexedDB wrapper for offline-first local storage |
| `lucide-react` | `^0.468.0` | Icon library |
| `vite` | `^5.4.0` | Dev server + bundler |
| `@vitejs/plugin-react` | `^4.3.0` | React Fast Refresh + JSX transform |

### Manager Web App — `apps/manager/`

| Package | Version | Purpose |
|---|---|---|
| `next` | `^14.2.0` | React framework with App Router |
| `react` | `^18.3.0` | UI framework |
| `react-dom` | `^18.3.0` | DOM renderer |
| `@tanstack/react-query` | `^5.0.0` | Server state / data fetching |
| `lucide-react` | `^0.468.0` | Icon library |

---

## Build / Dev Tooling

**Backend:**
- `ruff >=0.4` — linter and formatter (`target-version = "py311"`, `line-length = 100`)
- Selected rules: `E, F, I, UP, B` (errors, pyflakes, isort, pyupgrade, bugbear)

**Frontend (Driver PWA):**
- `vite ^5.4.0` — build + dev server, port 5174 (`apps/driver/vite.config.mjs`)
- `typescript ^5.5.0` — type checking only (`tsc --noEmit`)

**Frontend (Manager):**
- `next ^14.2.0` — dev server at port 3030 (`apps/manager/next.config.mjs`)
- `typescript ^5.5.0` — type checking only

---

## Testing

**Backend:**
| Package | Version | Purpose |
|---|---|---|
| `pytest` | `>=8.2` | Test runner |
| `pytest-asyncio` | `>=0.23` | Async test support (`asyncio_mode = "auto"`) |
| `httpx` | `>=0.27` | HTTP client for ASGI integration tests |

- Test directory: `backend/tests/`
- 18 test modules present covering API endpoints and domain logic
- No frontend test framework detected in either `apps/driver/` or `apps/manager/`

---

## Configuration

**Backend settings class:** `backend/app/config.py` — `pydantic_settings.BaseSettings`

Key settings loaded from environment:
| Setting | Env Var | Default |
|---|---|---|
| Database URL | `DATABASE_URL` | `postgresql+asyncpg://rotas:rotas@localhost:55432/rotas` |
| JWT secret | `JWT_SECRET_KEY` | `change-me-in-env` |
| JWT algorithm | (hardcoded) | `HS256` |
| Access token TTL | (hardcoded) | 15 minutes |
| Refresh token TTL | (hardcoded) | 30 days |
| CORS origins | `CORS_ORIGINS` | `[]` |
| Local upload dir | `LOCAL_UPLOAD_DIR` | `.rotas_uploads` |

Reads from `.env` and `../.env` (parent directory fallback).

**Driver PWA env vars** (Vite, prefixed `VITE_`):
- `VITE_ROTAS_API_BASE_URL` — backend base URL
- `VITE_ROTAS_TENANT_ID`, `VITE_ROTAS_VEHICLE_ID`, `VITE_ROTAS_DRIVER_ID`, `VITE_ROTAS_CHECKLIST_TEMPLATE_ID`, `VITE_ROTAS_DRIVER_TOKEN`
- Runtime override: values can also be set in `localStorage` (e.g., `rotas_api_base_url`, `rotas_tenant_id`)

**Manager env vars:**
- `ROTAS_API_BASE_URL` — backend base URL (read in `apps/manager/app/lib/api.ts`, `apps/manager/app/lib/auth.ts`)

---

## Infrastructure

**Local dev orchestration:** `infra/docker-compose.yml`
- PostgreSQL 16 on port 55432
- Redis 7 on port 6381 (AOF persistence enabled)

**Alembic timezone:** `Africa/Maputo` (`backend/alembic.ini`)

---

## PDF / XLSX Generation

PDF and XLSX billing exports are generated entirely in pure Python stdlib (`BytesIO`, `zipfile`, `xml.sax`) — no third-party PDF/spreadsheet library. Implementation at `backend/app/modules/billing/exporters.py`.

---

## Gaps / Unknowns

- No Node.js version pinned (no `.nvmrc`, `.node-version`, or `engines` field in `package.json`)
- No Tailwind CSS detected in `apps/manager/` despite it being mentioned in project docs — only `globals.css` and no `tailwind.config.*` found
- Redis is provisioned in `infra/docker-compose.yml` but no Redis client package (`redis-py`, `aioredis`) is present in `backend/pyproject.toml` — Redis is unused by the backend at this time
- No frontend test framework (Vitest, Jest, Playwright) present in either app
- No PWA manifest or service worker found in `apps/driver/` — offline-first is implemented via Dexie IndexedDB but no SW registered
- Python version is declared as `>=3.11` but the actual installed interpreter appears to be 3.13 (`.pyc` files in `__pycache__` are `cpython-313`)
