---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: gestao-clientes-contas-receber
status: Roadmap defined — ready for Phase 5 planning
last_updated: "2026-06-06T12:00:00.000Z"
last_activity: 2026-06-06
progress:
  total_phases: 3
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# ROTAS — Project State

_Last updated: 2026-06-06_

---

## Current Phase

Phase: 5 — Client Registry + Migration Foundation
Plan: Not started
Status: Roadmap defined — awaiting `/gsd:plan-phase 5`
Last activity: 2026-06-06 — v2.0 roadmap created (Phases 5, 6, 7)

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
| fpdf2+DejaVuSans for billing PDF — full Latin Extended Unicode, font path via Path(__file__) | 3 | latin-1 hand-rolled builder silently corrupted Mozambican diacritics; fpdf2 TTF font path is CWD-independent |
| openpyxl for XLSX — native bold/number_format, no hand-rolled XML/ZIP | 3 | openpyxl is the standard Python XLSX library; proper cell formatting without raw XML |
| Idempotent export job creation — returns existing queued/processing job on duplicate request | 3 | Prevents duplicate ARQ jobs for same document+format; safe for retry from frontend |
| Four Alembic migrations for client migration — DDL and DML never in same file | 5 | Established pattern in this codebase (28 existing migrations); DDL+DML mixing causes transaction issues on some PG versions |
| RLS policy created in the CREATE TABLE migration — not a follow-up patch | 5 | PITFALL-06: new tables not covered by existing RLS migration; must be explicit per table |
| due_date added in Phase 5 migration (b) alongside client_id — not in Phase 7 | 5 | PITFALL-04: aging needs stored due_date from day one; adding later requires second backfill of all issued documents |
| payment_allocations junction table created in Phase 6 — not deferred to Phase 7 | 6 | PITFALL-05: retrofitting allocation table after payment rows exist is high-risk schema migration |
| client_payments.billing_document_id is nullable — allocations live in junction table | 6 | Supports advance payments and multi-invoice allocation; direct FK would permanently block these flows |
| Payments voided via status field — never hard-deleted | 6 | Financial records must have immutable audit trail; hard delete corrupts AR history |
| Aging uses billing_documents.due_date (stored) not issued_at + payment_terms_days (derived) | 7 | due_date is authoritative; derived calculation drifts when payment_terms change post-issue |
| AR aging endpoint requires explicit as_of date parameter | 7 | Makes aging testable without time mocking; allows retrospective report generation |

### Architecture: v2.0 Phase Sequence

```
Phase 5: Client entity + 4-migration sequence + CLI frontend
  Migration (a): CREATE clients + RLS + GRANT
  Migration (b): ADD client_id FK (nullable) to contracts + billing_documents; ADD due_date to billing_documents
  Migration (c): Backfill — SELECT DISTINCT client_name → INSERT clients → UPDATE FKs
  Migration (d): CREATE payments + payment_allocations tables + RLS + GRANT

  Gate: SELECT count(*) FROM contracts WHERE client_id IS NULL = 0
        SELECT count(*) FROM billing_documents WHERE client_id IS NULL = 0

Phase 6: Payments (only starts after Phase 5 gate passes)
  POST /api/v1/billing/payments (idempotency-key required)
  payment_allocations for invoice linking
  Advance payment support (no billing_document_id at creation)

Phase 7: AR dashboard + aging (requires both clients + payments)
  GET /clients/{id}/statement
  GET /clients/{id}/aging?as_of=YYYY-MM-DD
  GET /billing/ar-summary?as_of=YYYY-MM-DD
  Client statement PDF (fpdf2 + DejaVuSans — same as billing PDF)
```

### Blockers

_None — roadmap defined, planning not yet started._

### Todos

- [ ] Run pre-migration audit query before writing Phase 5 migration code: `SELECT tenant_id, lower(trim(client_name)), count(*) FROM contracts GROUP BY 1, 2 HAVING count(*) > 1` — review variant groups
- [ ] Confirm `tailwind.config.*` exists in `apps/manager/` before Phase 3 dashboard work
- [ ] Fix Node.js to `"engines": { "node": "20.x" }` in all `package.json` before Vercel deploy

---

## Session Continuity

_Last session: 2026-06-06 — v2.0 roadmap created (Phases 5, 6, 7 — 12 requirements, 100% mapped)_

---

## Project Reference

**Core value**: A Mozambican driver can complete an entire trip — departure, refueling, stops, and delivery proof — without connectivity, and all data arrives intact at the manager when signal returns.

**Current milestone**: v2.0 — Gestão de Clientes e Contas a Receber

**Stack**: FastAPI 0.115 + Python 3.12 + SQLAlchemy 2.0 async + PostgreSQL 16 / Next.js 14 App Router + React 18 + Tailwind / Vite + Dexie.js 4

**Deploy target**: Vercel (manager) + Railway or Render (backend FastAPI)

**Roadmap**: `.planning/ROADMAP.md`

**Requirements**: `.planning/REQUIREMENTS.md`

**Codebase analysis**: `.planning/codebase/` (7 documents, generated 2026-06-04)

**Research**: `.planning/research/ARCHITECTURE.md` + `.planning/research/PITFALLS.md` (generated 2026-06-06)
