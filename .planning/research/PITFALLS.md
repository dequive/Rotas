# Pitfalls Research

**Domain:** Client registry and accounts receivable on existing multi-tenant billing SaaS (FastAPI + PostgreSQL)
**Researched:** 2026-06-06
**Confidence:** HIGH — based on direct codebase analysis of billing/contracts models, Alembic migration history, RLS migration, and billing service layer

---

## Critical Pitfalls

---

### PITFALL-01: Fuzzy Deduplication During client_name → client_id Migration

**What goes wrong:**
The migration script creates one `Client` per distinct `(tenant_id, client_name)` pair. Because `client_name` is a free-text `String(160)` field shared across `contracts.client_name` and `billing_documents.client_name`, the same real-world company can appear as "CIMENTOS DE MOÇAMBIQUE", "Cimentos de Mocambique", and "Cimentos Moçambique, Lda" — three rows, three separate Client entities, split billing history.

**Why it happens:**
`client_name` was indexed but never normalized. The `ix_contracts_client_name` index and `ix_billing_documents_client_name` index are case-sensitive by default in PostgreSQL. No NUIT (tax ID) or external identifier was ever required, so there is no collision key. The developer running the migration assumes `SELECT DISTINCT client_name` is safe without auditing the data first.

**How to avoid:**
Run the audit query before writing a single line of migration code:
```sql
SELECT tenant_id, lower(trim(client_name)), count(*) AS variants
FROM contracts
GROUP BY 1, 2
HAVING count(*) > 1
ORDER BY 3 DESC;
```
Export the variant groups. Create the `clients` table with both `canonical_name` and `name_aliases TEXT[]`. Let the migration script produce candidate groups for human review — do not auto-merge. Treat NUIT as the deduplication key where available; for legacy rows without NUIT, flag `client_unresolved = true` and block new invoices until resolved, rather than silently creating duplicates.

**Warning signs:**
- AR dashboard shows the same company with two separate balances
- Payment registered against Client A but the invoice lives under Client B (same company, different string variant)
- `clients` table row count exceeds the tenant's known customer count

**Phase to address:**
Client registry phase — before any FK backfill migration is written. The audit query is a pre-condition.

---

### PITFALL-02: Backfilling billing_documents.client_id Without a Dual-Write Window Leaves Orphaned Records

**What goes wrong:**
The migration adds `billing_documents.client_id` as a nullable FK, runs `UPDATE billing_documents SET client_id = (SELECT id FROM clients WHERE ...)`, then treats the column as populated. Any document where `client_name` had no exact match in the new `clients` table gets `client_id = NULL`. Service queries that filter on `client_id` silently exclude those documents from AR totals, statements, and aging — with no error raised.

**Why it happens:**
The one-shot backfill SQL joins on exact string match. Legacy documents with fuzzy names or case variants that did not match the canonical client record end up with `client_id = NULL`. Because the column must be nullable to not break existing rows, no constraint catches the gap.

**How to avoid:**
1. Add `client_id` as nullable — deploy, run in production.
2. Add a dual-write period: every time a `BillingDocument` is created or updated, also populate `client_id` if resolvable from `contract.client_id`.
3. Run the backfill in batches with an explicit completeness check:
   `SELECT count(*) FROM billing_documents WHERE client_id IS NULL AND tenant_id IS NOT NULL`
   must reach zero before proceeding.
4. Only then consider adding a `NOT NULL` constraint — or accept nullable permanently and treat NULL as pre-migration legacy (documented, not silent).
5. Never drop `client_name` from `BillingDocument` — it is a snapshot of the client name at invoice time and has independent archival and legal value, regardless of whether `client_id` is set.

**Warning signs:**
- Aging totals do not reconcile with the sum of all issued `billing_documents` for a client
- `GET /clients/{id}/statement` returns fewer invoices than the billing list filtered by that client name
- Any issued document has `client_id IS NULL` after the backfill migration ran

**Phase to address:**
Client registry phase — the migration step. Must be validated against production-like data (with realistic name variants) before deploying.

---

### PITFALL-03: Using billing_documents.paid_at and status="paid" Instead of a Payments Table

**What goes wrong:**
`BillingDocument` already has `paid_at: Mapped[datetime | None]` and a `status` column. The temptation is to set `paid_at = now()` and `status = "paid"` when a payment is registered. This works for a single full payment on one invoice. It breaks for:
- Partial payments (50% received today, remainder next month)
- Multiple payments against one large invoice
- Payment reversals
- Overpayments that become credit against future invoices
- Advance payments before the invoice is issued

The existing billing state machine (`draft → issued`) already uses `status` as a one-way transition. Extending it to `paid` via a timestamp creates an irreversible state change with no payment audit trail.

**How to avoid:**
Create a `client_payments` table as a first-class entity:
```
id, tenant_id, client_id, amount, currency,
payment_date (value date), received_at (bank date),
payment_method, reference, notes,
registered_by, created_at
```
Keep `billing_documents.paid_at` as a denormalized cache (set when `balance_due <= 0`), not the source of truth. Compute `amount_paid` as `SUM(allocations WHERE billing_document_id = X)`. Use a `payment_allocations` junction table (see PITFALL-05 below). The "paid" status becomes a derived assertion, not a stored mutation.

**Warning signs:**
- "Can I record a partial payment?" becomes a blocker question mid-implementation
- A manager needs to reverse a payment — there is no record to reverse
- AR dashboard shows a document as "paid" but the client still owes a remaining balance

**Phase to address:**
Payment registration phase — do not extend the existing status machine; design a new entity from the start.

---

### PITFALL-04: Aging Calculation Without an Explicit due_date Column or Timezone-Anchored Reference Date

**What goes wrong:**
Aging buckets (current / 30 / 60 / 90+ days overdue) are computed as `(NOW() - billing_period_end)` or `(NOW() - issued_at)`. In Mozambique the server runs UTC (`Africa/Maputo` is UTC+2). `issued_at` is stored as `DateTime(timezone=True)` but the "due date" is never modeled — it is implied as `issued_at + payment_terms_days`. If `payment_terms_days` is on the `Client` entity and the aging query does arithmetic using Python's `datetime.now()` without explicit UTC, documents flip buckets mid-day depending on the execution context.

**How to avoid:**
- Store `due_date` explicitly on `BillingDocument` at issue time: `due_date = issued_at + timedelta(days=client.payment_terms_days)`. Column type: `DateTime(timezone=True)`, not nullable after issue.
- Run all aging SQL using `NOW() AT TIME ZONE 'Africa/Maputo'` or pass an explicit `?as_of=YYYY-MM-DD` parameter from the API layer.
- The statement endpoint must accept and document an `as_of` date — this makes aging testable without time mocking and allows retrospective statement generation.
- Never compute aging in a browser component using `new Date()` — the manager's browser timezone may differ from Africa/Maputo.

**Warning signs:**
- AR totals change between morning and evening refresh without any new activity
- A document shows "30+ days overdue" on the server but "current" in the UI
- Tests pass locally (UTC+1 or UTC-5 developer) but aging buckets are off in production (UTC+2)

**Phase to address:**
Client registry phase — model `due_date` in the same migration that adds `client_id` to `BillingDocument`, not in a separate aging phase.

---

### PITFALL-05: Payment Allocation Breaks Multi-Contract Invoices (Missing Junction Table)

**What goes wrong:**
The milestone goal includes "faturas por cliente agregando múltiplos contratos no mesmo período" — a single invoice covering trips from multiple contracts. If `client_payments.billing_document_id` is a direct FK to `billing_documents`, the model cannot express:
- One payment covering invoice A and invoice B from the same client
- A single bank transfer that partially covers a large invoice
- An advance that sits unallocated until invoices are created

The missing abstraction is payment allocation.

**How to avoid:**
Two-level payment model:
- `client_payments` — the cash receipt (amount, date, reference, method). No `billing_document_id` FK on this table.
- `payment_allocations` — junction: `(payment_id, billing_document_id, amount_applied, created_at)`.

One payment → many allocations. One document's `amount_paid = SUM(allocations WHERE billing_document_id = X)`. Unapplied credit: payment rows with no allocation rows. This is the standard AR pattern across every accounting system — the complexity at schema design time is low; the refactor cost after data is in production is high.

**Warning signs:**
- "How do I register one payment against two invoices?" appears during implementation
- A `billing_document_id NOT NULL` constraint is proposed on `client_payments` — this closes off multi-invoice payments forever

**Phase to address:**
Payment registration phase — schema design decision before the first payment row is recorded.

---

### PITFALL-06: New clients Table Deployed Without RLS — Multi-Tenant Isolation Gap

**What goes wrong:**
The existing RLS infrastructure (`4b0a7802dc3c_add_rls_policies.py`) uses a hardcoded `TENANT_SCOPED_TABLES` Python list. A new `clients` table created in a later migration is NOT covered by that migration and will NOT have RLS unless the new migration explicitly runs:
```sql
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON clients USING (
    tenant_id = current_setting('app.tenant_id')::uuid
);
GRANT SELECT, INSERT, UPDATE, DELETE ON clients TO rotas_app;
```
Without this, the application-level `WHERE tenant_id = ?` filter is the only isolation barrier. A single bug in any service function would expose all tenants' clients.

**Why it happens:**
The developer creates the `clients` table migration, runs `alembic autogenerate`, and deploys. The RLS policy and grant are not in the auto-generated output and must be added manually. There is no enforcement mechanism that catches missing RLS on new tenant-scoped tables.

**How to avoid:**
Every migration that creates a tenant-scoped table must include the three SQL blocks above (ENABLE, CREATE POLICY, GRANT) in the same migration file. Add a test that queries `pg_catalog.pg_policies` to verify `clients` and `client_payments` have the `tenant_isolation` policy. The `4b0a7802dc3c` migration is the correct template — copy the pattern exactly.

**Warning signs:**
- `\d+ clients` in psql shows `Row Security: disabled`
- A cross-tenant integration test for client lookup returns 200 instead of 404
- `pg_catalog.pg_policies` has no row for `tablename = 'clients'`

**Phase to address:**
Client registry phase — in the `CREATE TABLE clients` migration, not a follow-up patch.

---

### PITFALL-07: list_billable_trips Filter by client_name Breaks After Migration

**What goes wrong:**
`billing/service.py:list_billable_trips` contains:
```python
if client_name:
    query = query.where(Contract.client_name.ilike(f"%{client_name}%"))
```
After migration, the UI selects clients from the registry (dropdown by `client_id`). If this function is not updated to accept `client_id: UUID | None`, the new client entity and the old string filter create two inconsistent lookup paths. Worse: a query by `client_id` that joins through `Contract.client_id` will miss contracts where the FK was not backfilled (NULL), silently excluding their trips from billing queues.

**How to avoid:**
When adding `client_id` to `Contract`, update `list_billable_trips` to accept `client_id: UUID | None` and filter via `Contract.client_id == client_id`. Keep `client_name` as a deprecated fallback during the dual-write window only. Document which parameter takes precedence when both are passed. Remove the string filter after backfill is validated.

**Warning signs:**
- `list_billable_trips(client_id=X)` returns fewer trips than `list_billable_trips(client_name="X's name")`
- Billing dashboard shows a client with 0 pending trips but the trips list (filtered by name) shows pending trips

**Phase to address:**
Client registry phase — service layer update in the same PR as the FK backfill migration.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Keep `client_name` snapshot on BillingDocument after adding `client_id` | No display migration needed | Two fields exist; minor redundancy | Always keep the snapshot — it is legally correct at issue time |
| Compute aging in Python instead of SQL | Easier to read and test | Inconsistent results across timezones; no single query for the dashboard | Never in production — use SQL with explicit `as_of` |
| Use `billing_documents.status = "paid"` as payment signal | Simple state machine | Cannot model partial payments or reversals | Only if multi-contract invoicing and partial payments are formally and permanently out of scope |
| Skip `payment_allocations`, use direct `billing_document_id` FK on payments | Simpler schema | Cannot apply one payment to multiple invoices | Acceptable only if multi-invoice billing is explicitly deferred to a later version |
| Auto-merge duplicate clients by lowercased name during backfill | Faster migration | Merges genuinely different clients with similar names | Never — always require human confirmation for merges |
| Deploy `clients` without RLS, rely only on service-layer filter | One fewer step | Single service bug exposes all tenants' client data | Never — RLS is non-negotiable for a multi-tenant SaaS |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Existing `serialize_billing_document` | Adding `client_id` to the response without a fallback for pre-migration documents | Keep `client_name` in the response always; add `client_id` as an additional nullable field |
| Existing `create_document` service | Continues to pull `client_name` from `contract.client_name` after migration | After migration, resolve `client.name` from `contract.client_id`; fall back to `contract.client_name` during dual-write window |
| RLS `SET LOCAL app.tenant_id` per transaction | New `clients` table created without `GRANT ... TO rotas_app` | Every new tenant-scoped table needs an explicit GRANT in the same migration — auto-generate does not add this |
| `BillingDocumentCreate` Pydantic schema | `client_name` is required; after migration it should be derived from the client entity | Make `client_name` optional in the schema; derive from `client.name` at document creation time; keep backward compat during transition |
| Export / PDF render | PDF renders `document.client_name` — the snapshot | This is correct; do not change it to read from the Client entity live. The snapshot is the legally correct value at time of issue. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Aging query with no index on `due_date` | Statement page takes 5+ seconds for clients with 100+ invoices | Composite index `(tenant_id, client_id, due_date)` on `billing_documents` | ~200 invoices per client |
| `SUM(payments)` recomputed on every statement request | AR dashboard slow when many clients have many payments | Denormalize `amount_paid` on `BillingDocument`; cache AR KPIs in Redis (already provisioned) | ~50 active clients with 30+ payments each |
| `list_documents` loads all documents per tenant to compute AR totals | Memory spike; service layer aggregates in Python | Add `client_id` filter to `list_documents`; aggregate in SQL not Python | ~500 documents per tenant |
| N+1 queries in statement generation | Statement endpoint slow for clients with 20+ invoices | Single JOIN across `billing_documents`, `payment_allocations`, `client_payments` | ~20 invoices per client statement |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Accepting `client_id` in request body without verifying tenant ownership | Tenant A registers a payment against Tenant B's client, corrupting Tenant B's AR | Always resolve: `client = await db.get(Client, client_id); assert client.tenant_id == tenant_id` |
| Returning client NUIT (tax ID) in paginated list endpoints without RBAC | NUIT is sensitive fiscal data; viewer roles should not access it | Gate NUIT fields behind `owner/admin` roles in the serializer; omit from `viewer` responses |
| Allowing payment deletion (hard delete) without audit trail | Financial records become mutable with no trace | Payments must never be hard-deleted; use `status = "reversed"` with `reversal_reason` and `reversed_by` FK |
| Missing RLS on `clients` or `client_payments` | Cross-tenant financial data exposure if any service function has a filter bug | Every tenant-scoped table needs both RLS and an application-layer filter — defense in depth |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Building full client management (contacts, credit limits, payment terms, attachments) in the same phase as the AR dashboard | Scope explosion; neither feature ships | Phase 1: client registry (name, NUIT, payment terms only). Phase 2: AR dashboard + aging. Phase 3: credit limits, contact persons, full statement history. |
| Showing aging buckets without a visible reference date | Manager believes aging is wrong when server and browser are in different timezones | Always display "a partir de [data]" next to aging totals; derive date from server, not browser |
| Free-text client input in payment registration | Manager types partial name, gets 3 variants of the same company, registers payment against the wrong one | Payment registration must use a dropdown backed by the clients registry — no free-text client entry after migration |
| Combining "record payment" and "allocate to invoices" in one complex form | Hard to implement correctly; cascade interaction errors confuse users | Two-step UX: Step 1 records the cash receipt. Step 2 allocates it to invoices. The receipt is valid even before allocation. |
| Showing "Outstanding Balance" as a single aggregate number | Manager cannot act on an aggregate; needs to know which specific invoices are overdue | Default view: list of overdue invoices with aging bucket. The aggregate KPI is secondary. |

---

## "Looks Done But Isn't" Checklist

- [ ] **Client migration:** `SELECT count(*) FROM billing_documents WHERE client_id IS NULL` is zero (or the remaining NULL count is documented as accepted legacy)
- [ ] **Client migration:** `SELECT count(*) FROM contracts WHERE client_id IS NULL` is zero or documented
- [ ] **RLS:** `\d+ clients` in psql shows `Row Security: enabled`
- [ ] **RLS:** `\d+ client_payments` in psql shows `Row Security: enabled`
- [ ] **RLS:** `SELECT * FROM pg_catalog.pg_policies WHERE tablename = 'clients'` returns the `tenant_isolation` policy
- [ ] **Payment model:** A payment for less than `billing_document.total_amount` is accepted without error
- [ ] **Payment model:** Two payments against the same invoice produce the correct combined `amount_paid`
- [ ] **Aging:** `due_date` is a stored column on `BillingDocument`, populated at issue time
- [ ] **Aging:** `GET /clients/{id}/statement?as_of=2026-01-01` returns historically correct buckets (testable without time mocking)
- [ ] **Cross-tenant:** Creating a client in tenant A, then querying with tenant B's JWT returns 404
- [ ] **Cross-tenant:** Registering a payment with a `billing_document_id` from a different tenant returns 404
- [ ] **Audit:** Payment reversal creates an audit log entry with `old_values` and `new_values`
- [ ] **Deduplication:** Two contracts with similar but distinct client names remain as separate clients — no auto-merge occurred
- [ ] **Backward compat:** Existing `serialize_billing_document` works correctly for documents where `client_id IS NULL` (pre-migration documents)
- [ ] **list_billable_trips:** `list_billable_trips(client_id=X)` returns the same trip count as the equivalent name-filtered query against the same contracts

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Duplicate clients from auto-merge | HIGH | Build a merge tool: reassign all FK references (contracts, billing_documents, payments, allocations) from duplicate to canonical; soft-delete the duplicate; record merge in audit log |
| Orphaned billing_documents with NULL client_id after bad backfill | MEDIUM | Re-run backfill with corrected matching logic; manually assign ambiguous cases; document each assignment in audit log |
| Payment registered against wrong billing_document | MEDIUM | Reverse the allocation (status="reversed"), create correct allocation; if already reported to client, add reconciliation note |
| clients table deployed without RLS | CRITICAL | Emergency migration to enable RLS immediately; audit all queries that ran between deploy and fix for cross-tenant data; notify affected tenants |
| Aging calculations wrong due to timezone bug | MEDIUM | Re-run aging calculation with server-side `as_of` date; no data corruption — purely display layer fix; correct due_date values in DB if stored without timezone |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Fuzzy deduplication during migration | Client registry (schema + migration) | Pre-migration audit query produces zero unreviewed variant groups |
| NULL client_id after backfill | Client registry (migration step) | `SELECT count(*) FROM billing_documents WHERE client_id IS NULL` = 0 or documented |
| payments on status timestamp instead of payments table | Payment registration (schema design) | `client_payments` table exists; partial payment test passes |
| Aging timezone drift / missing due_date | Client registry (add due_date column in same migration) | `GET /statement?as_of=X` integration test passes from UTC+0 and UTC+2 execution contexts |
| clients table missing RLS | Client registry (CREATE TABLE migration) | `pg_policies` check + cross-tenant integration test returns 404 |
| Single-document payment FK blocks multi-invoice allocation | Payment registration (schema design) | `payment_allocations` junction table exists; test: one payment applied to two invoices |
| list_billable_trips string filter stale after migration | Client registry (service layer update) | `list_billable_trips(client_id=X)` count matches manual FK join through contracts |

---

## Sources

- Direct analysis of `backend/app/modules/billing/models.py` — `BillingDocument.client_name` String(160), `paid_at` as single timestamp, no `due_date` column, no `client_id` FK
- Direct analysis of `backend/app/modules/contracts/models.py` — `Contract.client_name` String(160), no `client_id` FK, free-text since initial schema
- Direct analysis of `backend/app/modules/billing/service.py` — `list_billable_trips` string-based client filter, `create_document` copies `contract.client_name` directly to document
- Direct analysis of `backend/alembic/versions/4b0a7802dc3c_add_rls_policies.py` — hardcoded `TENANT_SCOPED_TABLES` list, explicit GRANT per table, manual pattern required for new tables
- Direct analysis of `backend/alembic/versions/813e78af3d00_add_contracts.py` — confirms `client_name` was free text from the contracts feature introduction; `client_id` FK was never added to contracts
- Standard AR module design patterns (HIGH confidence) — payments entity, payment allocation junction, due_date as stored not derived
- PostgreSQL RLS documentation (HIGH confidence) — each table requires explicit `ENABLE ROW LEVEL SECURITY` + policy creation; not inherited across tables

---
*Pitfalls research for: adding client registry and accounts receivable to existing multi-tenant billing SaaS*
*Researched: 2026-06-06*
