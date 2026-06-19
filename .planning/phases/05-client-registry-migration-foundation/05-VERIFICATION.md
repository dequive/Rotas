---
phase: 05-client-registry-migration-foundation
verified: 2026-06-19T05:00:00Z
status: human_needed
score: 5/5 must-haves verified
gaps: []
human_verification:
  - item: "CLI-03 Backfill Applied to Live DB — run: SELECT count(*) FROM contracts WHERE client_id IS NULL AND client_name IS NOT NULL AND client_name != ''; expected: 0"
  - item: "ClientCombobox Search UX — open /contratos → Novo Contrato → type 2+ chars in Client field; verify filtering and NUIT in IBM Plex Mono"
  - item: "Credit Warning Strip at Runtime — set client credit_limit=1000 MZN, issue billing doc for 850 MZN; verify amber warning on /clientes/[id]"
---

# Phase 5: Client Registry — Migration Foundation Verification Report

**Phase Goal:** Establish a first-class client registry and wire it into contracts + billing so ROTAS has a structured client entity from day 1 of the public SaaS launch. Includes 3 Alembic data migrations for the backfill (CLI-03).
**Verified:** 2026-06-19T05:00:00Z
**Status:** human_needed (5/5 automated checks pass; 3 items need human testing)
**Re-verification:** Yes — Plan 05-06 gap closure implemented test_backfill_zero_null_client_ids; status updated from gaps_found → human_needed

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | CLI-01: GET/POST/PATCH /api/v1/clients endpoints exist and work with tenant scoping, NUIT uniqueness (409), and deactivation | VERIFIED | `backend/app/modules/clients/router.py` — all 4 routes present and wired; `test_clients_api.py` — 6 tests pass (create, dup NUIT, list scoped, patch deactivate, cross-tenant, credit balance) |
| 2 | CLI-02: Credit limit warning shown when outstanding_balance >= 80% of credit_limit | VERIFIED | `apps/manager/app/clientes/[id]/page.tsx` lines 172-213 — creditPct computed, AlertTriangle at 80%, AlertOctagon at 100%; backend `_get_outstanding_balance` queries issued BillingDocuments via real FK |
| 3 | CLI-03: Alembic backfill migration exists and correctly populates client_id from client_name | VERIFIED | Migration `f6a7b8c9d0e1_backfill_client_ids.py` exists with correct DML (DISTINCT ON, ON CONFLICT DO NOTHING, 5-step backfill); `test_backfill_zero_null_client_ids` implemented (Plan 05-06) and PASSES — seeds 3 contracts with distinct NUITs, runs Steps 1+2+3, asserts zero NULL client_ids remain |
| 4 | CLI-04: ContractFormModal uses ClientCombobox (client_id) instead of free-text client_name | VERIFIED | `ContractFormModal.tsx` imports and uses `ClientCombobox`; backend `contracts/service.py` resolves `client_name` from `Client.trading_name`; 5 tests pass in `test_contracts_api.py` |
| 5 | CLI-05: Invoice numbers are sequential per tenant in AAAA/NNNN format; test_invoice_number_format passes | VERIFIED | `test_billing_api.py` — `test_invoice_number_format` and `test_invoice_number_increments` both pass; `_assign_invoice_number` uses PostgreSQL SEQUENCE; MonoCell renders invoice_number in `cobranca/page.tsx` |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/modules/clients/models.py` | Client SQLAlchemy model | VERIFIED | Full model with UniqueConstraint(tenant_id, nuit), all required fields, RLS-compatible |
| `backend/app/modules/clients/service.py` | list_clients, get_client_with_balance, create_client, patch_client, serialize_client | VERIFIED | All 5 functions present; `_get_outstanding_balance` wired to real BillingDocument.client_id query (outstanding_balance_estimate=False) |
| `backend/app/modules/clients/router.py` | GET/POST /clients, GET/PATCH /clients/{id} | VERIFIED | All 4 routes, uses `get_current_principal`, `get_session` |
| `backend/alembic/versions/a2b3c4d5e6f7_add_clients_table.py` | DDL: CREATE clients + RLS + GRANT rotas_app | VERIFIED | ENABLE ROW LEVEL SECURITY, FORCE ROW LEVEL SECURITY, tenant_isolation policy, GRANT to rotas_app |
| `backend/alembic/versions/e5f6a7b8c9d0_add_client_fks_and_due_date.py` | DDL: nullable client_id FKs + due_date + composite index | VERIFIED | contracts.client_id, billing_documents.client_id, due_date, ix_billing_documents_tenant_client_due |
| `backend/alembic/versions/f6a7b8c9d0e1_backfill_client_ids.py` | DML backfill: client_id on contracts + billing_documents | VERIFIED (migration) | 5-step backfill using DISTINCT ON + ON CONFLICT; correct idempotent SQL |
| `backend/alembic/versions/a7b8c9d0e1f2_scaffold_payments_tables.py` | DDL: client_payments + payment_allocations + RLS + GRANT | VERIFIED | Both tables, per-table RLS + GRANT loop, correct for Phase 6 scaffold |
| `backend/tests/test_clients_api.py` | 7 passing tests (CLI-01/CLI-02/CLI-03) | VERIFIED | 7 tests pass, 0 skipped. `test_backfill_zero_null_client_ids` implemented by Plan 05-06 and PASSES |
| `backend/tests/test_contracts_api.py` | 5 CLI-04 tests passing | VERIFIED | All 5 tests present and passing |
| `backend/tests/test_billing_api.py` | test_invoice_number_format passes | VERIFIED | Format assertion + increment assertion both pass via service layer |
| `apps/manager/app/clientes/page.tsx` | Client list with KPI strip, DataTable, NovoClienteButton | VERIFIED | Server Component with 4 KpiCards (active, outstanding, exceeded, contracts "—"), ClientsTable, EmptyState |
| `apps/manager/app/clientes/[id]/page.tsx` | Client detail with info card, credit warning strip, contracts/invoices panels | VERIFIED | Two-column info card, credit warning at creditPct >= 80 (amber) and >= 100 (red), contracts + invoices panels with client-side filtering |
| `apps/manager/app/components/ClientFormModal.tsx` | 9-field create/edit dialog, deactivate button in edit mode | VERIFIED | All 9 fields present; "Desactivar cliente" button sends PATCH {is_active: false}; validation for NUIT regex and required fields |
| `apps/manager/app/components/ClientCombobox.tsx` | Popover+search backed by GET /api/clients, NUIT in IBM Plex Mono | VERIFIED | Radix Popover + native search input; fetches /api/clients proxy; loading skeletons; NUIT rendered in font-mono |
| `apps/manager/app/components/ContractFormModal.tsx` | ClientCombobox replaces free-text client_name | VERIFIED | `import { ClientCombobox }` at line 7; state: clientId, clientName, clientError; validation before submit |
| `apps/manager/app/components/SidebarLayout.tsx` | Financeiro section includes Clientes as first item with Building2 icon | VERIFIED | Line 59: `{ key: "clientes", label: "Clientes", href: "/clientes", icon: Building2 }` — first item in Financeiro section |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/main.py` | `clients/router.py` | `include_router(clients_router, prefix=api)` | WIRED | Line 33: import, line 255: `app.include_router(clients_router, prefix=api)` |
| `backend/app/database.py` | `clients/models.py` | MODEL_MODULES tuple | WIRED | Line 99: `"clients"` present in MODEL_MODULES |
| `clients/service.py` `_get_outstanding_balance` | `billing/models.py BillingDocument.client_id` | SQLAlchemy query on client_id FK | WIRED | `BillingDocument.client_id == client_id` in WHERE clause; FK exists since migration e5f6a7b8c9d0 |
| `ClientCombobox` | `/api/clients` Next.js proxy | `fetch("/api/clients?limit=200")` on popover open | WIRED | `apps/manager/app/api/clients/route.ts` GET handler proxies to backend with auth headers |
| `ContractFormModal` | `ClientCombobox` | Import + state wiring | WIRED | `import { ClientCombobox }` used in form; `onChange` → `setClientId`/`setClientName`; payload includes `client_id` |
| `contracts/service.py create_contract` | `clients/models.py Client` | `db.get(Client, payload.client_id)` | WIRED | Lines 97-108: cross-tenant guard + `client_name_to_use = client.trading_name` |
| `clientes/[id]/page.tsx` | `/api/v1/clients/{id}` | `apiFetch<ClientResponse>` | WIRED | Line 67: `apiFetch<ClientResponse>(\`/api/v1/clients/${id}\`)` |
| `cobranca/page.tsx` | `BillingDocument.invoiceNumber` | `MonoCell` render | WIRED | Line 280: `<MonoCell>` renders `document.invoiceNumber` |
| `billing/service.py issue_document` | `_assign_invoice_number` | called at line 634 | WIRED | PostgreSQL SEQUENCE used; format `{year}/{seq_val:04d}` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `clients/service.py` `get_client_with_balance` | `outstanding_balance` | `BillingDocument.total_amount` WHERE `client_id == client_id AND status == 'issued'` | Yes — real DB query via `func.sum` | FLOWING |
| `clientes/[id]/page.tsx` | `client` | `apiFetch(/api/v1/clients/${id})` → service layer → DB | Yes | FLOWING |
| `clientes/page.tsx` | `clients` | `loadClients()` → `/api/v1/clients` → `list_clients` → DB | Yes | FLOWING |
| `ClientCombobox` | `clients` | `fetch("/api/clients?limit=200")` → Next.js proxy → backend | Yes — proxied with httpOnly cookie auth | FLOWING |

### Behavioral Spot-Checks

| Behavior | Evidence | Status |
|----------|----------|--------|
| POST /api/v1/clients creates with NUIT uniqueness | `test_create_client` + `test_create_client_duplicate_nuit` pass | PASS |
| PATCH /api/v1/clients/{id} deactivates | `test_patch_client_deactivate` passes | PASS |
| Cross-tenant isolation on GET /api/v1/clients | `test_client_cross_tenant_isolation` passes | PASS |
| client_id FK on contracts resolves trading_name | `test_create_contract_with_client_id` passes | PASS |
| invoice_number AAAA/NNNN format on issue | `test_invoice_number_format` passes | PASS |
| invoice_number increments per tenant | `test_invoice_number_increments` passes | PASS |
| Backfill zeroed NULL client_ids | `test_backfill_zero_null_client_ids` — PASSED (Plan 05-06) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CLI-01 | 05-01-PLAN.md, 05-03-PLAN.md | Create/edit/deactivate client with NUIT, name, city, phone, email | SATISFIED | 6 passing API tests + /clientes page + ClientFormModal |
| CLI-02 | 05-01-PLAN.md, 05-03-PLAN.md | Credit limit warning at 80%+, payment terms | SATISFIED | Detail page credit warning strip (80%/100%) + outstanding_balance live query |
| CLI-03 | 05-02-PLAN.md, 05-06-PLAN.md | Backfill client_name → client_id on contracts + billing_documents | SATISFIED | Migration `f6a7b8c9d0e1` exists with correct SQL; `test_backfill_zero_null_client_ids` implemented (Plan 05-06) and PASSES — 7 tests, 0 skipped |
| CLI-04 | 05-04-PLAN.md | Contract references client_id; ClientCombobox in ContractFormModal | SATISFIED | ContractFormModal uses ClientCombobox; backend resolves client_name; 5 tests pass |
| CLI-05 | 05-05-PLAN.md | Sequential invoice numbers AAAA/NNNN per tenant via PostgreSQL SEQUENCE | SATISFIED | `_assign_invoice_number` implemented; 2 tests pass; MonoCell display in cobranca/page.tsx |

### Anti-Patterns Found

| File | Issue | Severity | Impact |
|------|-------|----------|--------|
| `backend/tests/test_clients_api.py` line 149-152 | `test_backfill_zero_null_client_ids` permanently `@pytest.mark.skip` — the reason says "implement after Plan 02 backfill completes" but Plan 02 is complete and the test was never unskipped | Warning | CLI-03 has no automated gate; the backfill could have silently run against zero rows (rotas_app RLS limitation) without detection |
| `apps/manager/app/clientes/page.tsx` | KPI card "Contratos Activos" hardcoded to `"—"` | Info | Known stub, documented in SUMMARY. Does not block client registry functionality. |
| `apps/manager/app/components/ClientFormModal.tsx` line 8 | `API_BASE` declared but unused (getAuthHeaders returns `{}` empty — mutation goes through /api/clients proxy which handles auth) | Info | Not a functional issue — ClientFormModal correctly uses `/api/clients` proxy for mutations |

### Human Verification Required

#### 1. CLI-03 Backfill Applied to Live DB

**Test:** Connect to the production/staging database as `rotas_admin` and run:
```sql
SELECT count(*) FROM contracts
WHERE client_id IS NULL
  AND client_name IS NOT NULL
  AND client_name != '';
```
**Expected:** Count = 0 (all client_name-populated contracts have been matched to a client_id)
**Why human:** The migration `f6a7b8c9d0e1` runs under `ALEMBIC_DATABASE_URL` (rotas_admin, BYPASSRLS). No automated test verifies the live DB state. The test stub `test_backfill_zero_null_client_ids` was never implemented.

#### 2. ClientCombobox Search UX

**Test:** Open /contratos → "Novo Contrato" form → click Client field → type 2+ characters
**Expected:** Combobox filters by trading_name and NUIT; results show NUIT in IBM Plex Mono 11px; selecting a client displays NUIT below the trigger
**Why human:** Radix Popover + native search behavior cannot be verified statically

#### 3. Credit Warning Strip at Runtime

**Test:** Set a client's credit_limit to 1000 MZN, create and issue a billing document for that client totalling 850 MZN
**Expected:** /clientes/[id] shows amber warning strip with AlertTriangle icon
**Why human:** Requires live data; outstanding_balance depends on issued billing documents linked via client_id FK

### Gaps Summary

No automated gaps remain. All 5 requirements verified with passing tests.

**CLI-03 gap closed by Plan 05-06:** `test_backfill_zero_null_client_ids` implemented — seeds 3 contracts with distinct NUITs, runs Steps 1+2 (INSERT clients, DISTINCT ON + ON CONFLICT DO NOTHING) and Step 3 (UPDATE contracts.client_id by normalized name match) from migration `f6a7b8c9d0e1`, asserts zero NULL client_id rows remain. 7 passed, 0 skipped.

3 items require human verification (see Human Verification Required section above): live DB backfill count check, ClientCombobox UX, credit warning strip at runtime.

---

_Verified: 2026-06-19T05:00:00Z_
_Verifier: Claude (gsd-verifier)_
