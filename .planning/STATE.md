---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Defining requirements
last_updated: "2026-06-06T08:45:01.303Z"
last_activity: 2026-06-06
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 35
  completed_plans: 30
---

# ROTAS — Project State

_Last updated: 2026-06-06_

---

## Current Phase

Phase: 04
Plan: Not started
Status: Defining requirements
Last activity: 2026-06-06

---

## Accumulated Context (v2.0)

### Key Decisions

| Decision | Phase | Rationale |
|----------|-------|-----------|
| SEC-05 (python-jose → PyJWT) first in Phase 1 | 1 | Active CVE — auth bypass active before any external user |
| Cross-tenant regression tests before CT-01 | 1 → 3 | CT-01 query rewrite is highest-risk window for cross-tenant data leaks |
| ARQ for background jobs (PDF, XLSX, KPI refresh) | 3 | Uses Redis already provisioned; asyncio-native; avoids blocking HTTP responses |
| SW served with Cache-Control: no-store | 2 | Broken cached SW is unrecoverable on low-cost Android — cannot be fixed server-side |
| Field testing on real Android hardware required to close Phase 2 | 2 | Background Sync API compatibility must be confirmed on target hardware |
| DeliveryProof patchable fields use actual model names (notes, receiver_name, receiver_contact) | 2 | Plan spec listed wrong field names; real model checked and corrected |
| _dispatch_update wraps patch calls in try/except for per-item error isolation | 2 | Batch HTTP stays 200; ApiError converts to failed result per item |
| registerType: prompt not autoUpdate in VitePWA config | 2 | autoUpdate calls skipWaiting unconditionally — would reload app mid-trip while driver records delivery proof |
| BackgroundSyncPlugin handles fetch exceptions only; Dexie handles HTTP errors | 2 | BackgroundSync only retries on network failure; 4xx/5xx need Dexie-level retry |
| Icons generated with Pillow + Windows Arial Bold (proper 192x192/512x512) | 2 | Proper dimensions required — Chrome installability checker rejects icons smaller than declared size |
| manifest.webmanifest in public/ is static fallback; live manifest from vite.config.mjs manifest block | 2 | VitePWA injectManifest strategy generates injected manifest from config, not public/ file |
| require_roles(*DASHBOARD_ROLES) for scorecard endpoint — driver tokens rejected at dependency level | 4 | Consistent with all other protected endpoints; no manual scope check needed |

### Blockers

_None yet — project not started._

### Todos

- [ ] Confirm `tailwind.config.*` exists in `apps/manager/` before Phase 3 dashboard work
- [ ] Fix Node.js to `"engines": { "node": "20.x" }` in all `package.json` before Vercel deploy

---

## Session Continuity

_Last session: 2026-06-05T20:55Z — Completed 03-05-PLAN.md (analytics module: KPI + document expiry, 3 tests green)_

---

## Project Reference

**Core value**: A Mozambican driver can complete an entire trip — departure, refueling, stops, and delivery proof — without connectivity, and all data arrives intact at the manager when signal returns.

**Stack**: FastAPI 0.115 + Python 3.12 + SQLAlchemy 2.0 async + PostgreSQL 16 / Next.js 14 App Router + React 18 + Tailwind / Vite + Dexie.js 4

**Deploy target**: Vercel (manager) + Railway or Render (backend FastAPI)

**Roadmap**: `.planning/ROADMAP.md`

**Requirements**: `.planning/REQUIREMENTS.md`

**Codebase analysis**: `.planning/codebase/` (7 documents, generated 2026-06-04)
