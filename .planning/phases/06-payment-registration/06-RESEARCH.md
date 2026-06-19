# Phase 6: Payment Registration — Research

**Researched:** 2026-06-19
**Domain:** FastAPI + SQLAlchemy 2.0 async + PostgreSQL (payment recording, allocation logic, idempotency) + Next.js 14 App Router
**Confidence:** HIGH

---

## Summary

Phase 6 is a pure service + router + frontend phase. The schema is already live in the database. Both `client_payments` and `payment_allocations` were created in Phase 5 migration (d) — revision `a7b8c9d0e1f2` — with RLS policies, GRANT statements, and indexes already applied. The ORM models (`ClientPayment`, `PaymentAllocation`) are already declared in `backend/app/modules/billing/models.py`. No new Alembic migration is required unless the schema needs adjustment (it does not — the scaffold matches the architecture constraints exactly).

The work in Phase 6 is: (1) implement the service functions for payment registration, allocation, voiding, and the client statement query; (2) add the router endpoints for payments; (3) extend `GET /clients/{id}` to reflect payment-based balance; (4) build the payment registration modal in the `/cobranca` and `/clientes/[id]` pages.

The primary design challenge is the balance computation: outstanding balance per invoice is `total_amount - SUM(payment_allocations.amount_applied WHERE billing_document_id = X AND payment.status = 'confirmed')`. The current `_get_outstanding_balance` in `clients/service.py` sums raw `BillingDocument.total_amount` — it must be updated post-Phase 6 to subtract confirmed allocations, or Phase 7 (AR) handles this. The architecture constraint says `GET /clients/{id}/statement` must reflect updates within the same request — meaning the balance calculation must be synchronous, not cached.

**Primary recommendation:** Implement three service functions (`register_payment`, `void_payment`, `get_client_statement`) and two router endpoints (`POST /billing/payments`, `DELETE /billing/payments/{id}` → void). Extend `clients/service.py` `_get_outstanding_balance` to subtract confirmed allocations. Build a `PaymentModal` in the frontend that works from both the `/cobranca` invoice list and the `/clientes/[id]` detail page.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PAY-01 | Gestor pode registar um pagamento total ou parcial contra uma fatura com data valor e método de pagamento (transferência bancária, cheque, numerário) | `POST /api/v1/billing/payments` with `billing_document_id`, `amount`, `value_date`, `payment_method`; creates `ClientPayment` + `PaymentAllocation`; idempotency key required |
| PAY-02 | Sistema suporta adiantamentos de cliente aplicáveis a faturas futuras do mesmo cliente | `billing_document_id` is nullable on `ClientPayment` — advance has no allocation rows at creation; separate `POST /billing/payments/{id}/apply` endpoint applies advance to a specific invoice |
| PAY-03 | Após registo de pagamento, o saldo em aberto da fatura e o saldo do cliente são actualizados imediatamente | `_get_outstanding_balance` in `clients/service.py` must subtract confirmed allocations from `BillingDocument.total_amount`; `GET /clients/{id}/statement` is computed synchronously from DB, not cached |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

### Stack
- FastAPI + Next.js + Vite/React + PostgreSQL — stack is locked, no substitutions
- SQLAlchemy 2.0 async with `AsyncSession`; Alembic for all migrations
- Python 3.11+ (actual installed: 3.13 based on `.pyc` files)
- Next.js 14 App Router; React 18; `@tanstack/react-query ^5.0.0`

### v2.0 Migration Rules (mandatory for every new `tenant_id` table)
Every CREATE TABLE migration for a table with `tenant_id` MUST include in the same file:
```sql
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON {table}
    USING (tenant_id::text = current_setting('app.tenant_id', true));
GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app;
```
**Phase 6 note:** Both `client_payments` and `payment_allocations` already have these policies applied in migration `a7b8c9d0e1f2`. No new migration needed. If any schema adjustment is required (it is not expected), a new migration must follow this pattern.

### Multitenancy Safety
- Every query must filter by `tenant_id` — never remove this filter
- `tenant_id` extracted from JWT by `get_current_principal` — never from request body
- Payment registration must verify `billing_document.client_id == payment.client_id` AND same `tenant_id` — mismatch returns HTTP 409

### Service Layer
- Services return `dict`, never raw ORM objects
- Services call `record_audit_log` inside same DB session before commit
- Services accept `db: AsyncSession` — session opened by router via `Depends(get_session)`

### Financial Data
- All monetary columns use `Numeric(14, 2)` — never `float`
- Balance computations use `Decimal` with `.quantize(Decimal("0.01"))`

### Payments — Immutability Rule
- Payments are **never hard-deleted** — void via `status = "voided"` with `voided_by` and `void_reason`
- Audit log entry required for every void

---

## Existing Scaffold Audit

### What Already Exists (no re-implementation needed)

| Artifact | Location | Status |
|----------|----------|--------|
| `ClientPayment` ORM model | `backend/app/modules/billing/models.py` lines 149-183 | Complete |
| `PaymentAllocation` ORM model | `backend/app/modules/billing/models.py` lines 186-204 | Complete |
| `client_payments` migration DDL | `backend/alembic/versions/a7b8c9d0e1f2_scaffold_payments_tables.py` | Applied |
| `payment_allocations` migration DDL | Same migration | Applied |
| RLS policies on both tables | Same migration | Applied |
| GRANT to `rotas_app` on both tables | Same migration | Applied |
| Indexes on `tenant_id`, `client_id`, `billing_document_id`, `payment_id` | Same migration | Applied |
| `billing_documents.paid_at` field | `billing_documents` table | Exists |
| `billing_documents.due_date` field | `billing_documents` table | Exists (added Phase 5) |
| Idempotency infrastructure | `backend/app/core/idempotency.py` | Complete |
| `execute_http_idempotent()` helper | `backend/app/core/idempotency.py` | Complete |
| Audit log infrastructure | `backend/app/modules/audit/service.py` | Complete |
| `SM-01` state machine (`transition_billing_document`) | `billing/service.py` lines 944-997 | Complete |
| `mark_billing_document_paid()` | `billing/service.py` lines 1000-1019 | Complete |

### What Does NOT Exist (Phase 6 must build)

| Artifact | Where to Build |
|----------|---------------|
| `register_payment()` service function | `billing/service.py` |
| `void_payment()` service function | `billing/service.py` |
| `get_client_statement()` service function | `clients/service.py` |
| `_get_payment_adjusted_balance()` (replacing current simple sum) | `clients/service.py` |
| `apply_advance_to_invoice()` service function | `billing/service.py` |
| `POST /api/v1/billing/payments` endpoint | `billing/router.py` |
| `POST /api/v1/billing/payments/{id}/void` endpoint | `billing/router.py` |
| `POST /api/v1/billing/payments/{id}/apply` endpoint | `billing/router.py` |
| `GET /api/v1/clients/{id}/statement` endpoint | `clients/router.py` |
| `ClientPaymentCreate` Pydantic schema | `billing/schemas.py` |
| `VoidPaymentRequest` Pydantic schema | `billing/schemas.py` |
| `ApplyAdvanceRequest` Pydantic schema | `billing/schemas.py` |
| `PaymentModal` frontend component | `apps/manager/app/components/` |
| Payment list section in `/clientes/[id]` | `apps/manager/app/clientes/[id]/page.tsx` |
| Payment registration action in `/cobranca` | `apps/manager/app/cobranca/page.tsx` |
| `billing-api.ts` payment functions | `apps/manager/app/lib/billing-api.ts` |
| Tests for PAY-01, PAY-02, PAY-03 | `backend/tests/test_payments.py` |

---

## Standard Stack

### Core (no new packages required)
| Library | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `>=0.111` | Router, dependencies |
| `sqlalchemy[asyncio]` | `>=2.0` | Async ORM queries |
| `pydantic` | `>=2.0` | Schema validation |
| `python-decimal` | stdlib | `Numeric(14,2)` operations |

**No new pip packages needed for Phase 6.** All dependencies are already installed.

### Frontend (no new npm packages required)
| Library | Version | Purpose |
|---------|---------|---------|
| `next` | `^14.2.0` | Server + Client Components |
| `@tanstack/react-query` | `^5.0.0` | Client-side data fetching for PaymentModal |
| `lucide-react` | `^0.468.0` | Icons |

**No new npm packages needed for Phase 6.** Existing shadcn/ui components cover all UI needs.

---

## Architecture Patterns

### Payment Registration Flow

```
POST /api/v1/billing/payments
  Header: Idempotency-Key (required — same pattern as billing document creation)
  Body: {
    client_id: UUID,
    billing_document_id: UUID | null,  # null = advance payment
    amount: Decimal,
    value_date: datetime,
    payment_method: "bank_transfer" | "cheque" | "cash",
    reference: str | null,
    notes: str | null
  }

Service: register_payment()
  1. Fetch client — verify tenant_id match
  2. If billing_document_id provided:
     a. Fetch billing_document — verify tenant_id match
     b. Verify billing_document.client_id == payment.client_id → HTTP 409 if mismatch
     c. Verify billing_document.status in ("issued", "overdue") → HTTP 409 otherwise
     d. Compute remaining balance = total_amount - SUM(existing confirmed allocations)
     e. If amount > remaining_balance → HTTP 409 "payment_exceeds_balance"
  3. Create ClientPayment (status="confirmed")
  4. If billing_document_id provided:
     a. Create PaymentAllocation (payment_id, billing_document_id, amount_applied=amount)
     b. Check if SUM(all allocations) >= billing_document.total_amount
     c. If yes: update billing_document.paid_at = value_date (denormalized cache)
     d. Call transition_billing_document() → "paid" if document is "issued" or "overdue"
  5. record_audit_log(action="payment.created")
  6. Return serialized payment
```

### Advance Payment Flow

```
# Advance payment: no billing_document_id
POST /api/v1/billing/payments
  { client_id, amount, value_date, payment_method, billing_document_id: null }
  → Creates ClientPayment with status="confirmed", no PaymentAllocation rows

# Apply advance to invoice later
POST /api/v1/billing/payments/{payment_id}/apply
  { billing_document_id: UUID, amount_applied: Decimal }
  → Verifies: payment.client_id == billing_doc.client_id AND same tenant_id
  → Verifies: payment.billing_document_id IS NULL (advance, not already allocated payment)
  → Verifies: amount_applied <= unallocated remainder of payment
  → Creates PaymentAllocation row
  → If invoice fully covered: updates paid_at, transitions to "paid"
```

### Void Payment Flow

```
POST /api/v1/billing/payments/{payment_id}/void
  Body: { void_reason: str }
  Roles: ADMIN_ROLES only (owner, admin)

Service: void_payment()
  1. Fetch payment — verify tenant_id
  2. Verify payment.status == "confirmed" → HTTP 409 if already voided
  3. Set payment.status = "voided", voided_at = now(), voided_by = user_id, void_reason
  4. Reverse any paid_at denormalization:
     a. For each allocation: check if billing_document is now underpaid
     b. If billing_document.paid_at was set and is now underpaid: clear paid_at, revert to "issued"
  5. record_audit_log(action="payment.voided")
  6. Return serialized payment
```

### Client Statement Query

```
GET /api/v1/clients/{id}/statement
  Query params: period_start (optional), period_end (optional)

Returns:
  {
    client: { id, trading_name, nuit, ... },
    documents: [
      {
        id, invoice_number, billing_period_start, billing_period_end,
        total_amount, amount_paid, outstanding_balance,
        due_date, status, issued_at
      }
    ],
    payments: [
      { id, amount, value_date, payment_method, reference, status, allocations: [...] }
    ],
    summary: {
      total_invoiced, total_paid, total_outstanding,
      advance_balance  # SUM(unallocated confirmed payment amounts)
    }
  }
```

### Balance Computation (PAY-03)

The current `_get_outstanding_balance` in `clients/service.py` sums `BillingDocument.total_amount WHERE status = 'issued'`. After Phase 6, this must be corrected to subtract confirmed payment allocations:

```python
async def _get_outstanding_balance(db, client_id, tenant_id) -> Decimal:
    # Gross outstanding: sum of issued/overdue invoice totals
    gross = await db.execute(
        select(func.coalesce(func.sum(BillingDocument.total_amount), 0))
        .where(
            BillingDocument.client_id == client_id,
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status.in_(("issued", "overdue")),
        )
    )
    # Confirmed allocations against those documents
    paid = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0))
        .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
        .join(BillingDocument, BillingDocument.id == PaymentAllocation.billing_document_id)
        .where(
            ClientPayment.tenant_id == tenant_id,
            ClientPayment.client_id == client_id,
            ClientPayment.status == "confirmed",
            BillingDocument.status.in_(("issued", "overdue")),
        )
    )
    return (Decimal(str(gross.scalar_one())) - Decimal(str(paid.scalar_one()))).quantize(Decimal("0.01"))
```

### Recommended Project Structure Changes

```
backend/app/modules/billing/
├── models.py          # Already has ClientPayment + PaymentAllocation
├── schemas.py         # Add: ClientPaymentCreate, VoidPaymentRequest, ApplyAdvanceRequest
├── service.py         # Add: register_payment(), void_payment(), apply_advance_to_invoice()
└── router.py          # Add: POST /payments, POST /payments/{id}/void, POST /payments/{id}/apply

backend/app/modules/clients/
├── service.py         # Update: _get_outstanding_balance() to subtract allocations
│                      # Add: get_client_statement()
└── router.py          # Add: GET /{id}/statement

backend/tests/
└── test_payments.py   # New: PAY-01, PAY-02, PAY-03 tests

apps/manager/app/
├── components/
│   └── PaymentModal.tsx        # New: modal for registering payment
├── lib/
│   └── billing-api.ts         # Add: registerPayment(), voidPayment(), getClientStatement()
├── cobranca/
│   └── page.tsx               # Add: "Registar Pagamento" button on issued documents
└── clientes/
    └── [id]/
        └── page.tsx           # Add: payments section + "Registar Adiantamento" button
```

### Idempotency Pattern (PAY-01 requirement)

The existing `execute_http_idempotent()` in `backend/app/core/idempotency.py` handles this. It is already used for billing document creation. The payment endpoint uses the same pattern:

```python
@router.post("/payments", status_code=201)
async def register_payment(
    payload: schemas.ClientPaymentCreate,
    principal: Annotated[Principal, Depends(require_roles(*WRITE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    return await execute_http_idempotent(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="billing.payment.register",
        entity_type="client_payment",
        payload=payload,
        handler=lambda: service.register_payment(db, principal.tenant_id, principal.user_id, payload),
    )
```

TTL for `client_payment` entity type: the `ttl_for()` function in `idempotency.py` only extends TTL to 90 days for `billing_document` and `billing_item`. Payments can use 30-day TTL (default) or be extended — the roadmap does not specify, so 30-day default is acceptable.

### Frontend Pattern

The `/cobranca/page.tsx` is a Server Component that renders billing documents. Adding payment registration requires a Client Component (`PaymentModal`) that uses `useRouter()` to refresh after registration. The pattern in this codebase:

- Server Component page renders data server-side (no React Query needed for initial load)
- Client Component modal opens on button click, submits via `fetch()` to Next.js route handler
- Route handler reads httpOnly cookies and forwards to backend API (same pattern as `ClientCombobox` in Phase 5-04)
- Next.js `router.refresh()` after success to revalidate server component data

The `/clientes/[id]/page.tsx` follows the same pattern: it is a Server Component that fetches client + contracts + billing documents. Adding a payment section and PaymentModal follows the same architecture.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| Idempotency | Custom dedup table | `execute_http_idempotent()` already in `app/core/idempotency.py` |
| Audit trail | Custom event logging | `record_audit_log()` in `app/modules/audit/service.py` |
| State machine transition | Manual status checks | `transition_billing_document()` in `billing/service.py` |
| Decimal arithmetic | Python float operations | `Decimal` with `.quantize(Decimal("0.01"))` |
| Auth/tenant extraction | Manual header parsing | `get_current_principal` dependency |
| Cross-tenant guard | Manual tenant_id comparisons | Pattern: `if entity.tenant_id != tenant_id: raise ApiError(404)` |
| Cookie forwarding in Next.js | Custom middleware | Next.js route handler with `apiFetch()` from `app/lib/api.ts` |

---

## Common Pitfalls

### Pitfall 1: Over-allocating a Payment
**What goes wrong:** Service allows `amount > remaining_balance` — this would make the allocation `SUM > total_amount`, corrupting the balance.
**Why it happens:** Missing validation before writing `PaymentAllocation`.
**How to avoid:** Before writing allocation: `remaining = total_amount - SUM(existing_confirmed_allocations)`. Raise `ApiError("payment_exceeds_invoice_balance", ..., 409)` if `amount > remaining`.
**Warning signs:** `outstanding_balance` goes negative for a client.

### Pitfall 2: Cross-Client Payment Mismatch
**What goes wrong:** Payment registered for Client A gets allocated to an invoice belonging to Client B.
**Why it happens:** Only checking `tenant_id` on the billing document, not `client_id`.
**How to avoid:** Explicitly verify `billing_document.client_id == payment.client_id` in `register_payment()`. Return HTTP 409 with code `payment_client_mismatch` if they differ.
**Warning signs:** Client A's statement shows payments they did not make.

### Pitfall 3: Voiding Without Reversing paid_at
**What goes wrong:** A payment is voided, but `billing_document.paid_at` is not cleared and `billing_document.status` remains "paid". The invoice appears paid even though the payment was voided.
**Why it happens:** `void_payment()` sets `payment.status = "voided"` but does not check downstream effects.
**How to avoid:** In `void_payment()`, after voiding, re-compute `SUM(confirmed allocations)` for each affected billing document. If `SUM < total_amount`, clear `paid_at` and transition document back to "issued" (or "overdue" if past due_date).
**Warning signs:** A paid invoice is voided but balance still shows as zero.

### Pitfall 4: Advance Applied Twice
**What goes wrong:** The same advance payment is applied to two different invoices, with `amount_applied` exceeding the original payment `amount`.
**Why it happens:** `apply_advance_to_invoice()` does not check existing allocation total against original payment amount.
**How to avoid:** Before creating allocation: `existing_applied = SUM(payment_allocations.amount_applied WHERE payment_id = X)`. Verify `existing_applied + new_amount_applied <= payment.amount`. Raise HTTP 409 if exceeded.
**Warning signs:** A client's advance balance goes negative.

### Pitfall 5: Statement Balance Inconsistency (PAY-03 violation)
**What goes wrong:** `GET /clients/{id}/statement` is called immediately after `POST /billing/payments` but returns the old balance because the response is cached or the `_get_outstanding_balance` function reads from a stale read replica.
**Why it happens:** Using Redis cache for balance OR using async read replicas with replication lag.
**How to avoid:** No caching on balance computations. The current codebase does not use read replicas. The `_get_outstanding_balance` function reads from the same `AsyncSession` as the request — this is synchronous consistency within the same request. No action needed beyond removing any Redis caching that might be added later.

### Pitfall 6: `billing_document_id` Not Nullable on Advance
**What goes wrong:** Advance payment fails at the DB level because `billing_document_id` is erroneously set as NOT NULL.
**Why it happens:** Confusion between the `ClientPayment.billing_document_id` field and the `PaymentAllocation.billing_document_id` field.
**How to avoid:** Confirm: `ClientPayment.billing_document_id` is **nullable** (allows advance payments). `PaymentAllocation.billing_document_id` is **NOT NULL** (every allocation row must reference a specific invoice). Verified in migration `a7b8c9d0e1f2` — this is correct.

### Pitfall 7: No Idempotency Key Sent by Frontend
**What goes wrong:** Manager double-clicks "Registar Pagamento" — two payment records created for the same amount.
**Why it happens:** Frontend does not generate or send `Idempotency-Key` header.
**How to avoid:** `PaymentModal` component generates `crypto.randomUUID()` when the modal opens (not on button click). The UUID is stored in component state. Every submit sends the same UUID. On success, a new UUID is generated if the modal is reopened.

---

## Code Examples

### Serialize Payment (billing/service.py pattern)

```python
# Source: existing serialize_billing_document in billing/service.py
def serialize_payment(payment: ClientPayment, allocations: list[PaymentAllocation]) -> dict:
    return {
        "id": payment.id,
        "tenant_id": payment.tenant_id,
        "client_id": payment.client_id,
        "billing_document_id": payment.billing_document_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "value_date": payment.value_date,
        "payment_method": payment.payment_method,
        "reference": payment.reference,
        "notes": payment.notes,
        "status": payment.status,
        "voided_at": payment.voided_at,
        "voided_by": payment.voided_by,
        "void_reason": payment.void_reason,
        "created_by": payment.created_by,
        "created_at": payment.created_at,
        "allocations": [
            {
                "id": a.id,
                "billing_document_id": a.billing_document_id,
                "amount_applied": a.amount_applied,
                "created_at": a.created_at,
            }
            for a in allocations
        ],
    }
```

### Register Payment Core Logic

```python
# Source: architecture constraints in ROADMAP.md Phase 6
async def register_payment(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    payload: ClientPaymentCreate,
) -> dict:
    # 1. Verify client
    client = await db.get(Client, payload.client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError("client_not_found", "Client not found", status_code=404)

    billing_doc = None
    if payload.billing_document_id:
        # 2. Verify document
        billing_doc = await db.get(BillingDocument, payload.billing_document_id)
        if not billing_doc or billing_doc.tenant_id != tenant_id:
            raise ApiError("billing_document_not_found", "Invoice not found", status_code=404)
        # 3. Cross-client mismatch guard (CRITICAL)
        if billing_doc.client_id != payload.client_id:
            raise ApiError("payment_client_mismatch",
                "Payment client does not match invoice client", status_code=409)
        if billing_doc.status not in ("issued", "overdue"):
            raise ApiError("invoice_not_payable",
                f"Invoice status '{billing_doc.status}' does not accept payments", status_code=409)
        # 4. Over-allocation guard
        existing_paid = await _sum_confirmed_allocations(db, tenant_id, billing_doc.id)
        remaining = billing_doc.total_amount - existing_paid
        if payload.amount > remaining:
            raise ApiError("payment_exceeds_invoice_balance",
                "Payment amount exceeds remaining invoice balance", status_code=409,
                details={"remaining": str(remaining), "requested": str(payload.amount)})

    # 5. Create payment
    payment = ClientPayment(
        tenant_id=tenant_id,
        client_id=payload.client_id,
        billing_document_id=payload.billing_document_id,
        amount=payload.amount,
        currency=payload.currency or "MZN",
        value_date=payload.value_date,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        status="confirmed",
        created_by=user_id,
    )
    db.add(payment)
    await db.flush()

    allocations = []
    if billing_doc:
        # 6. Create allocation
        alloc = PaymentAllocation(
            tenant_id=tenant_id,
            payment_id=payment.id,
            billing_document_id=billing_doc.id,
            amount_applied=payload.amount,
        )
        db.add(alloc)
        allocations.append(alloc)
        await db.flush()

        # 7. Update denormalized paid_at if fully covered
        new_total_paid = existing_paid + payload.amount
        if new_total_paid >= billing_doc.total_amount:
            await transition_billing_document(
                db, document=billing_doc, new_status="paid",
                user_id=user_id, tenant_id=tenant_id,
                paid_at=payload.value_date,
            )

    await record_audit_log(
        db, tenant_id=tenant_id, user_id=user_id,
        action="payment.created", entity_type="client_payment",
        entity_id=payment.id,
        new_values={
            "client_id": str(payload.client_id),
            "billing_document_id": str(payload.billing_document_id) if payload.billing_document_id else None,
            "amount": str(payload.amount),
            "payment_method": payload.payment_method,
        },
    )
    await db.commit()
    await db.refresh(payment)
    return serialize_payment(payment, allocations)
```

### Pydantic Schemas to Add

```python
# Source: existing schema pattern in billing/schemas.py
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field

class ClientPaymentCreate(BaseModel):
    client_id: UUID
    billing_document_id: UUID | None = None  # None = advance payment
    amount: Decimal = Field(..., gt=0)
    currency: str = "MZN"
    value_date: datetime
    payment_method: str = Field(..., pattern="^(bank_transfer|cheque|cash)$")
    reference: str | None = None
    notes: str | None = None

class VoidPaymentRequest(BaseModel):
    void_reason: str = Field(..., min_length=5, max_length=500)

class ApplyAdvanceRequest(BaseModel):
    billing_document_id: UUID
    amount_applied: Decimal = Field(..., gt=0)
```

### Frontend Route Handler (Next.js pattern from Phase 5-04)

```typescript
// apps/manager/app/api/payments/route.ts
// Source: same pattern as apps/manager/app/api/clients/route.ts (Phase 5-04)
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const cookieStore = await cookies();
  const token = cookieStore.get("rotas_access_token")?.value;
  const tenantId = cookieStore.get("rotas_tenant_id")?.value;
  const idempotencyKey = request.headers.get("Idempotency-Key");

  if (!token || !tenantId) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const apiBase = process.env.ROTAS_API_BASE_URL;
  const res = await fetch(`${apiBase}/api/v1/billing/payments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Tenant-Id": tenantId,
      "Content-Type": "application/json",
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact on Phase 6 |
|--------------|-----------------|-------------------|
| `billing_document.paid_at` as sole payment truth | `paid_at` as denormalized cache; `SUM(payment_allocations)` as source of truth | Must update both when payment is registered |
| `_get_outstanding_balance` sums `total_amount WHERE status=issued` | Must subtract confirmed allocations | Service function update required |
| No payment allocation table | `payment_allocations` junction table already created | No migration needed |

---

## Environment Availability

Step 2.6: SKIPPED — Phase 6 is a pure code/service/router phase. All external dependencies (PostgreSQL, Redis, Python runtime) are pre-existing and already verified working by Phase 5.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.2 + pytest-asyncio 0.23 (`asyncio_mode = "auto"`) |
| Config file | `backend/pyproject.toml` |
| Quick run command | `cd backend && python -m pytest tests/test_payments.py -x -q` |
| Full suite command | `cd backend && python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PAY-01 | Register full payment against issued invoice; allocation created; paid_at updated | unit/integration | `pytest tests/test_payments.py::test_register_full_payment -x` | ❌ Wave 0 |
| PAY-01 | Register partial payment; invoice remains "issued"; balance reduced | unit/integration | `pytest tests/test_payments.py::test_register_partial_payment -x` | ❌ Wave 0 |
| PAY-01 | Idempotency key replay returns same payment | unit/integration | `pytest tests/test_payments.py::test_payment_idempotency -x` | ❌ Wave 0 |
| PAY-01 | Cross-client payment mismatch returns 409 | unit/integration | `pytest tests/test_payments.py::test_payment_client_mismatch -x` | ❌ Wave 0 |
| PAY-01 | Payment amount exceeds remaining balance returns 409 | unit/integration | `pytest tests/test_payments.py::test_payment_exceeds_balance -x` | ❌ Wave 0 |
| PAY-02 | Advance payment (no billing_document_id) creates payment with no allocations | unit/integration | `pytest tests/test_payments.py::test_advance_payment -x` | ❌ Wave 0 |
| PAY-02 | Apply advance to invoice creates allocation; invoice balance reduced | unit/integration | `pytest tests/test_payments.py::test_apply_advance -x` | ❌ Wave 0 |
| PAY-02 | Applying advance beyond payment amount returns 409 | unit/integration | `pytest tests/test_payments.py::test_advance_over_applied -x` | ❌ Wave 0 |
| PAY-03 | After payment registration, `_get_outstanding_balance` reflects reduced balance | unit/integration | `pytest tests/test_payments.py::test_balance_updated_after_payment -x` | ❌ Wave 0 |
| PAY-03 | Voiding a payment restores invoice balance | unit/integration | `pytest tests/test_payments.py::test_void_restores_balance -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && python -m pytest tests/test_payments.py -x -q`
- **Per wave merge:** `cd backend && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_payments.py` — all 10 tests listed above (Wave 0: stubs with `pytest.mark.skip` or failing `assert False`)
- [ ] No new conftest fixtures needed — existing `db`, `tenant_id`, `auth_headers` fixtures in `conftest.py` are sufficient. Need to add helper functions for creating test invoices in `test_payments.py` directly (same pattern as `test_billing_api.py`).

---

## Open Questions

1. **Should `void_payment` be a `POST /payments/{id}/void` or `PATCH /payments/{id}` with `status=voided`?**
   - What we know: The roadmap says "use `status = voided`"; the existing state machine pattern uses PATCH endpoints for transitions; but voiding is a one-way terminal action
   - Recommendation: Use `POST /payments/{id}/void` (explicit action endpoint) — consistent with `/documents/{id}/cancel` and `/documents/{id}/mark-paid` patterns in `billing/router.py`

2. **Does `GET /clients/{id}/statement` belong in the clients router or billing router?**
   - What we know: The Phase 7 AR dashboard will also have `GET /clients/{id}/statement`; the data is about billing documents per client
   - Recommendation: Add to `clients/router.py` (since it is keyed by client_id and returns client context). Phase 7 can extend it without moving it.

3. **Should the frontend `PaymentModal` use React Query or raw fetch?**
   - What we know: The manager app uses React Query for data fetching; the existing modal pattern (e.g., `ClientFormModal`, `WaiverModal`) uses direct `fetch()` calls in Client Components; `router.refresh()` triggers Server Component re-render
   - Recommendation: Use raw `fetch()` to the Next.js route handler + `router.refresh()` after success. Consistent with the established modal pattern in this codebase. React Query is overkill for a write-only modal.

4. **What RBAC role is required to register a payment? What about voiding?**
   - What we know: `WRITE_ROLES = {owner, admin, manager}`; `ADMIN_ROLES = {owner, admin}`; billing document issue uses `WRITE_ROLES`; cancel uses `ADMIN_ROLES`
   - Recommendation: Payment registration → `WRITE_ROLES` (manager can register payment on behalf of client); void payment → `ADMIN_ROLES` (irreversible financial action)

---

## Sources

### Primary (HIGH confidence)
- Direct code audit: `backend/app/modules/billing/models.py` — ORM scaffold for `ClientPayment` and `PaymentAllocation` confirmed complete
- Direct code audit: `backend/alembic/versions/a7b8c9d0e1f2_scaffold_payments_tables.py` — DDL migration confirmed applied with RLS + GRANT
- Direct code audit: `backend/app/modules/billing/service.py` — existing patterns for `register_payment`, `execute_http_idempotent`, state machine transitions
- Direct code audit: `backend/app/modules/clients/service.py` — `_get_outstanding_balance` confirmed as naive sum, needs update post-Phase 6
- Direct code audit: `backend/app/core/idempotency.py` — idempotency infrastructure confirmed complete
- Direct code audit: `backend/app/core/permissions.py` — WRITE_ROLES and ADMIN_ROLES confirmed

### Secondary (MEDIUM confidence)
- `ROADMAP.md` Phase 6 architecture constraints — authoritative for this project's design decisions

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all existing infrastructure confirmed by direct code audit
- Architecture: HIGH — scaffold already in place; design decisions locked in ROADMAP
- Pitfalls: HIGH — derived from direct code reading + established project patterns
- Test strategy: HIGH — follows existing test patterns in `test_billing_api.py` and `test_billing_domain.py`

**Research date:** 2026-06-19
**Valid until:** 2026-08-19 (stable domain — no external dependencies)
