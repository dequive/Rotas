---
phase: quick-260620-cme
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/scripts/billing_iva_backfill.sql
  - backend/app/modules/billing/models.py
  - backend/app/modules/contracts/models.py
  - backend/app/modules/billing/service.py
  - backend/app/modules/billing/schemas.py
  - backend/app/modules/billing/exporters.py
  - backend/app/modules/billing/router.py
  - backend/alembic/versions/<new_migration>.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "DEFAULT_IVA_RATE = Decimal('0.1600') — single constant, zero literal occurrences of 0.1700 in billing module"
    - "BillingDocument.issuer_name and issuer_nuit columns exist in DB and are populated from Tenant on create_document"
    - "Contract.payment_terms_days column exists; issue_document calculates due_date from issued_at + payment_terms_days"
    - "issued billing documents can never be cancelled via state machine"
    - "invoice_number assigned only in issue_document / immediate-issued paths; drafts have NULL invoice_number"
    - "GET /billing/ar/summary returns {current, 1_30, 31_60, 61_90, over_90, total_ar} in MZN"
    - "GET /billing/clients/{client_id}/statement returns balance and document list"
    - "GET /billing/payments returns paginated ClientPayment list"
    - "list_documents accepts document_type and client_id filters and returns total_count"
    - "PDF/XLSX uses document.invoice_number (not UUID prefix); draft shows PROFORMA label; issuer from document columns"
    - "download_job_file uses file_id + Files service, not raw file_path"
    - "list_billable_trips uses a single query with LEFT JOIN waiver (no N+1)"
    - "issue_document validates Σitem.amount == subtotal and subtotal + tax_amount == total_amount"
    - "void_payment response includes allocations loaded before the void"
    - "create_invoice_receipt and create_receipt emit audit log entries"
  artifacts:
    - path: "backend/scripts/billing_iva_backfill.sql"
      provides: "IVA historical backfill script"
    - path: "backend/alembic/versions/<new_migration>.py"
      provides: "issuer_name, issuer_nuit on billing_documents; parent_invoice_number on billing_documents; payment_terms_days on contracts"
  key_links:
    - from: "create_document"
      to: "Tenant.nuit / Tenant.name"
      via: "db.get(Tenant, tenant_id)"
      pattern: "issuer_name.*tenant\\.name"
    - from: "issue_document"
      to: "Contract.payment_terms_days"
      via: "due_date = issued_at + timedelta(days=contract.payment_terms_days)"
      pattern: "due_date.*timedelta"
---

<objective>
Production-harden the billing module across 20 items grouped into 4 thematic waves.

Purpose: Close fiscal correctness gaps (IVA constant, invoice numbering, document type labelling, issuer identity), add missing model fields (issuer_name/nuit, payment_terms_days, parent_invoice_number), fix AR/payment endpoints, eliminate N+1 queries, and add 4 missing endpoints.
Output: Updated billing module with Alembic migration, backfill SQL, corrected exporters, and 4 new router endpoints.
</objective>

<execution_context>
@/c/Users/Quive/.claude/get-shit-done/workflows/execute-plan.md
</execution_context>

<context>
@.planning/STATE.md
@backend/app/modules/billing/models.py
@backend/app/modules/billing/service.py
@backend/app/modules/billing/schemas.py
@backend/app/modules/billing/exporters.py
@backend/app/modules/billing/router.py
@backend/app/modules/billing/domain.py
@backend/app/modules/contracts/models.py
@backend/app/modules/tenants/models.py

<interfaces>
<!-- Key facts extracted from codebase reads -->

Tenant model fields: id, name, slug, plan, nuit (String(20) nullable), currency, timezone, ...

BillingDocument model — currently has:
  invoice_number: String(12) nullable
  document_type: String(30) default="invoice"
  parent_document_id: UUID FK nullable
  client_nuit: String(20) nullable
  iva_rate: Numeric(5,4) nullable
  due_date: DateTime nullable
  issued_at: DateTime nullable
  file_id: UUID FK nullable
  MISSING: issuer_name, issuer_nuit, parent_invoice_number

Contract model — currently has:
  payment_terms_days: MISSING (needs Integer column, default=30)
  client_nuit: String(20) nullable (already exists)

_BILLING_VALID_TRANSITIONS in service.py line 941-947:
  "draft": {"issued", "cancelled"},
  "issued": {"paid", "overdue", "cancelled"},  ← remove "cancelled" from "issued"
  "overdue": {"paid", "cancelled"},
  "paid": set(),
  "cancelled": set(),

create_document (service.py:407) does NOT call _assign_invoice_number — correct.
create_debit_note / create_credit_note / create_invoice_receipt / create_receipt all
  call _assign_invoice_number after flush, and they start in status="issued" — acceptable
  because these are immediate-issued documents by design.

list_billable_trips (service.py:326): N+1 — for each trip, runs a separate scalar()
  waiver query inside the loop at lines 361-370.

void_payment (service.py:1601): returns serialize_payment(payment, []) — empty list.
  Fix: load allocations BEFORE setting status="voided" (line 3 collect allocations is
  already done at 1629-1633; just pass `allocations` to serialize_payment at 1693).

create_invoice_receipt (service.py:1223): no audit log for the note itself.
create_receipt (service.py:1289): no audit log for the note itself.

exporters.py render_billing_export signature:
  issuer_name: str = "ROTAS" (hardcoded default)
  issuer_contact: str | None = None
  — needs to receive issuer_nuit from document and pass through.

PDF doc_number: str(document.id)[:8].upper() → replace with document.invoice_number
PDF status field in metadata block (_meta_row "Estado do documento") → remove
PDF/XLSX IVA fallback: `if document.iva_rate else 17` → raise ApiError if NULL on issued doc

router.py download_job_file (line 234-266):
  currently checks job.file_path and uses FileResponse(path=job.file_path)
  fix: use job.file_id → Files service → storage.py download path

service.py missing endpoints:
  - get_ar_summary(db, tenant_id, as_of) → buckets dict
  - get_client_statement(db, tenant_id, client_id) → {client_id, total_invoiced, total_paid, balance, documents}
  - list_payments(db, tenant_id, client_id, status, value_date_start, value_date_end, limit, offset)
  - list_documents already exists but needs document_type + client_id filters + total_count
</interfaces>
</context>

<tasks>

<!-- ═══════════════════════════════════════════════════════════════════════
     WAVE A — IVA constant + Alembic migration (must run before all else)
     ═══════════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task A1: IVA backfill SQL + DEFAULT_IVA_RATE constant + model columns migration</name>
  <files>
    backend/scripts/billing_iva_backfill.sql
    backend/app/modules/billing/service.py
    backend/app/modules/billing/schemas.py
    backend/app/modules/billing/exporters.py
    backend/app/modules/billing/models.py
    backend/app/modules/contracts/models.py
    backend/alembic/versions/<new_revision>.py
  </files>
  <action>
**Step 1 — Create backend/scripts/billing_iva_backfill.sql**

Write a dry-run + backfill SQL script:

```sql
-- ROTAS billing IVA backfill — 2026-06-20
-- Run in a transaction; ROLLBACK to inspect counts before COMMITting.

BEGIN;

-- 1. Audit: count documents that will be updated
SELECT
  CASE WHEN issued_at < '2023-01-01' THEN 'pre-2023 → 0.1700'
       ELSE 'from-2023 → 0.1600'
  END AS bucket,
  COUNT(*) AS doc_count,
  SUM(total_amount) AS total_exposure_mzn
FROM billing_documents
WHERE iva_rate IS NULL OR iva_rate NOT IN (0.1600, 0.1700)
GROUP BY 1;

-- 2. Backfill pre-2023 documents (IVA 17%)
UPDATE billing_documents
SET iva_rate = 0.1700, updated_at = NOW()
WHERE issued_at < '2023-01-01'
  AND (iva_rate IS NULL OR iva_rate != 0.1700);

-- 3. Backfill 2023+ documents (IVA 16%)
UPDATE billing_documents
SET iva_rate = 0.1600, updated_at = NOW()
WHERE (issued_at >= '2023-01-01' OR issued_at IS NULL)
  AND (iva_rate IS NULL OR iva_rate != 0.1600);

-- 4. Verify zero residual NULLs
SELECT COUNT(*) AS remaining_nulls FROM billing_documents WHERE iva_rate IS NULL;

-- ROLLBACK;  -- uncomment to inspect only
COMMIT;
```

**Step 2 — Replace all 0.1700 literals with DEFAULT_IVA_RATE constant**

In `backend/app/modules/billing/service.py`:
- At top of file (after imports), add:
  ```python
  DEFAULT_IVA_RATE = Decimal("0.1600")
  ```
- Replace ALL occurrences of `Decimal("0.1700")` with `DEFAULT_IVA_RATE`. There are 3 in service.py (in `create_document` item loop, `create_debit_note` default arg, `create_credit_note` default arg).
- The default arg on `create_debit_note` and `create_credit_note` must change:
  ```python
  # Before
  async def create_debit_note(..., iva_rate: Decimal = Decimal("0.1700")) -> dict:
  # After
  async def create_debit_note(..., iva_rate: Decimal = DEFAULT_IVA_RATE) -> dict:
  ```

In `backend/app/modules/billing/schemas.py`:
- Replace both `Decimal("0.1700")` defaults (in `CreateDebitNoteRequest.iva_rate` and `CreateCreditNoteRequest.iva_rate`) with `Decimal("0.1600")`.

In `backend/app/modules/billing/exporters.py`:
- The `iva_pct` fallback on PDF line (~277) and XLSX line (~462):
  ```python
  # Before
  iva_pct = int(float(document.iva_rate) * 100) if document.iva_rate else 17
  # After (both occurrences)
  if document.iva_rate is None:
      raise ValueError("iva_rate is NULL on issued document — cannot render export")
  iva_pct = int(float(document.iva_rate) * 100)
  ```
  This is the "remove fallback 'else 17'" requirement. The caller (export_document in service.py) already guards that status=="issued", so iva_rate will have been set by issue_document's recomputation.

**Step 3 — Add model columns**

In `backend/app/modules/billing/models.py`, add to `BillingDocument` class after `client_nuit`:
```python
issuer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
issuer_nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
parent_invoice_number: Mapped[str | None] = mapped_column(String(12), nullable=True)
```

In `backend/app/modules/contracts/models.py`, add after `notes`:
```python
payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
```
Import `Integer` from sqlalchemy (it is already imported in the file as part of the tuple — check and add if missing).

**Step 4 — Alembic migration**

Generate new revision ID (use a fresh hex, e.g. `b1c2d3e4f5a6`). Set `down_revision` to the current Alembic head (run `alembic heads` or check the latest migration file).

Create `backend/alembic/versions/b1c2d3e4f5a6_billing_issuer_parent_invoice_payment_terms.py`:

```python
"""billing: add issuer_name/issuer_nuit/parent_invoice_number to billing_documents; payment_terms_days to contracts

Revision ID: b1c2d3e4f5a6
Revises: <current_head>
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "<current_head>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_documents",
        sa.Column("issuer_name", sa.String(200), nullable=True),
    )
    op.add_column(
        "billing_documents",
        sa.Column("issuer_nuit", sa.String(20), nullable=True),
    )
    op.add_column(
        "billing_documents",
        sa.Column("parent_invoice_number", sa.String(12), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("billing_documents", "issuer_name")
    op.drop_column("billing_documents", "issuer_nuit")
    op.drop_column("billing_documents", "parent_invoice_number")
    op.drop_column("contracts", "payment_terms_days")
```

To find the correct `down_revision`, run:
```bash
cd backend && python -m alembic heads
```
and use the output revision ID.
  </action>
  <verify>
    <automated>cd backend && python -m ruff check app/modules/billing/service.py app/modules/billing/schemas.py app/modules/billing/exporters.py app/modules/billing/models.py app/modules/contracts/models.py --select E,F,I && python -c "from app.modules.billing.service import DEFAULT_IVA_RATE; from decimal import Decimal; assert DEFAULT_IVA_RATE == Decimal('0.1600'), f'wrong: {DEFAULT_IVA_RATE}'; print('OK')"</automated>
  </verify>
  <done>
    - backend/scripts/billing_iva_backfill.sql exists with COUNT audit + UPDATE blocks
    - DEFAULT_IVA_RATE = Decimal("0.1600") defined in service.py; zero occurrences of Decimal("0.1700") remain in service.py, schemas.py, exporters.py
    - exporters.py raises ValueError (not falls back to 17) when iva_rate is None
    - BillingDocument has issuer_name, issuer_nuit, parent_invoice_number columns in model
    - Contract has payment_terms_days column (Integer, server_default=30)
    - Alembic migration file exists with correct down_revision
    - ruff clean on modified files
  </done>
</task>

<!-- ═══════════════════════════════════════════════════════════════════════
     WAVE B — Service layer fixes (depend on Wave A columns)
     ═══════════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task B1: Service fixes — issuer population, due_date, state machine, invoice numbering, audit logs, void_payment allocations, N+1 fix, issue invariants</name>
  <files>backend/app/modules/billing/service.py</files>
  <action>
Apply the following 9 fixes to service.py in order. Each fix is independent of the others except where noted.

**Fix 1 — Populate issuer_name/issuer_nuit from Tenant in create_document**

In `create_document`, after `contract = await db.get(Contract, payload.contract_id)` validation:
```python
from app.modules.tenants.models import Tenant  # add to top-of-function imports or module level
tenant = await db.get(Tenant, tenant_id)
issuer_name = tenant.name if tenant else "ROTAS"
issuer_nuit = tenant.nuit if tenant else None
```
Then in the `BillingDocument(...)` constructor call, add:
```python
issuer_name=issuer_name,
issuer_nuit=issuer_nuit,
```
Add the import `from app.modules.tenants.models import Tenant` at the module-level import block (top of service.py).

**Fix 2 — Populate parent_invoice_number in create_debit_note, create_credit_note, create_invoice_receipt, create_receipt**

In each of these four functions, after the `BillingDocument(...)` constructor, add:
```python
note.parent_invoice_number = parent.invoice_number
```
(This persists the human-readable parent number on the child document for PDF/XLSX rendering and reporting without a JOIN.)

**Fix 3 — due_date from payment_terms_days in issue_document**

In `issue_document`, after `issued_at = payload.issued_at or datetime.now(UTC)`:
```python
from datetime import timedelta  # already imported via datetime module at top
contract = await db.get(Contract, document.contract_id) if document.contract_id else None
payment_terms = (contract.payment_terms_days if contract else 30) or 30
document.due_date = issued_at + timedelta(days=payment_terms)
```

**Fix 4 — Remove "cancelled" from "issued" transitions**

Change `_BILLING_VALID_TRANSITIONS` (around line 941-947):
```python
_BILLING_VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"issued", "cancelled"},
    "issued": {"paid", "overdue"},          # removed "cancelled"
    "overdue": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}
```

**Fix 5 — Guarantee invoice_number never assigned in create_document**

Verify `create_document` does NOT call `_assign_invoice_number`. It currently does not — confirm by searching for `_assign_invoice_number` in `create_document` body and assert it is absent. No code change needed if absent; add a comment:
```python
# invoice_number intentionally not assigned here — assigned only in issue_document (FISC-01)
```
Add this comment after `document.subtotal = total`.

**Fix 6 — Audit logs in create_invoice_receipt and create_receipt**

In `create_invoice_receipt`, after `await db.commit()` and before the return dict, add:
```python
await record_audit_log(
    db=db,
    tenant_id=tenant_id,
    action="billing.invoice_receipt_created",
    entity_type="billing_document",
    entity_id=note.id,
    new_values={
        "invoice_number": note.invoice_number,
        "parent_id": str(parent_id),
        "parent_invoice_number": parent.invoice_number,
        "total_amount": str(note.total_amount),
        "document_type": "invoice_receipt",
    },
)
```
Note: `record_audit_log` must be called BEFORE `db.commit()` to stay in the same transaction. Move the call to before `await db.commit()` (and after `await db.refresh(note)` is not needed before the log — log before commit, refresh after).

Apply the same pattern in `create_receipt`:
```python
await record_audit_log(
    db=db,
    tenant_id=tenant_id,
    action="billing.receipt_created",
    entity_type="billing_document",
    entity_id=note.id,
    new_values={
        "invoice_number": note.invoice_number,
        "parent_id": str(parent_id),
        "parent_invoice_number": parent.invoice_number,
        "amount_paid": str(note.total_amount),
        "document_type": "receipt",
    },
)
```
Place this BEFORE `await db.commit()`.

**Fix 7 — void_payment: return allocations loaded before void**

The allocations are already fetched at line 1629-1633 into `allocations` variable.
Change the return at the end of `void_payment`:
```python
# Before
return serialize_payment(payment, [])
# After
return serialize_payment(payment, allocations)
```

**Fix 8 — N+1 fix in list_billable_trips**

Replace the per-trip waiver scalar query with a single bulk fetch using an `IN` clause. After `rows = await db.execute(...)` and collecting results into a list, fetch all waiver rows in one query:

```python
rows_list = list(rows)

# Bulk-fetch all waivers for the result set in one query
trip_ids = [row[0].id for row in rows_list]
waiver_map: dict = {}
if trip_ids:
    waiver_rows = await db.execute(
        select(OperationalWaiver)
        .where(
            OperationalWaiver.tenant_id == tenant_id,
            OperationalWaiver.entity_type == "trip",
            OperationalWaiver.entity_id.in_(trip_ids),
            OperationalWaiver.waiver_type == NEGATIVE_MARGIN_APPROVAL_WAIVER,
        )
        .order_by(OperationalWaiver.created_at.desc())
    )
    for w in waiver_rows.scalars():
        # Keep first (most-recent) waiver per trip
        if w.entity_id not in waiver_map:
            waiver_map[w.entity_id] = w

results = []
for trip, proof, contract, vehicle in rows_list:
    waiver = waiver_map.get(trip.id)
    results.append(serialize_billable_trip(trip, proof, contract, vehicle, waiver))
return results
```
Remove the old per-trip `waiver = await db.scalar(...)` inside the loop.

**Fix 9 — Invariant check in issue_document**

Before the `document.status = "issued"` line in `issue_document`, add:
```python
# INVARIANT: verify financial totals are internally consistent
computed_subtotal = sum(item.amount for item in items).quantize(Decimal("0.01"))
computed_tax = sum((item.iva_amount or Decimal("0")) for item in items).quantize(Decimal("0.01"))
computed_total = (computed_subtotal + computed_tax).quantize(Decimal("0.01"))

if document.subtotal and abs(document.subtotal - computed_subtotal) > Decimal("0.01"):
    raise ApiError(
        "billing_total_inconsistency",
        f"Document subtotal {document.subtotal} does not match sum of items {computed_subtotal}",
        status_code=422,
    )
if document.total_amount and abs(document.total_amount - computed_total) > Decimal("0.01"):
    raise ApiError(
        "billing_total_inconsistency",
        f"Document total {document.total_amount} does not match subtotal+tax {computed_total}",
        status_code=422,
    )
```
Place this BEFORE the IVA recomputation block (which will correct the values anyway) — actually place it AFTER the recomputation block (lines 644-650) and BEFORE `document.status = "issued"`, so we validate the computed values:
```python
# After recomputation of subtotal/tax/total:
# Validate internal consistency
if abs(document.subtotal + document.tax_amount - document.total_amount) > Decimal("0.01"):
    raise ApiError(
        "billing_total_inconsistency",
        f"subtotal ({document.subtotal}) + tax ({document.tax_amount}) "
        f"!= total ({document.total_amount})",
        status_code=422,
    )
```
  </action>
  <verify>
    <automated>cd backend && python -m ruff check app/modules/billing/service.py --select E,F,I,B && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
    - create_document populates issuer_name/issuer_nuit from Tenant
    - create_debit_note, create_credit_note, create_invoice_receipt, create_receipt set parent_invoice_number
    - issue_document computes due_date = issued_at + timedelta(days=contract.payment_terms_days)
    - _BILLING_VALID_TRANSITIONS["issued"] = {"paid", "overdue"} (no "cancelled")
    - Comment confirms invoice_number not assigned in create_document
    - create_invoice_receipt and create_receipt emit audit log before commit
    - void_payment returns serialize_payment(payment, allocations) with pre-void allocations
    - list_billable_trips uses single bulk IN query for waivers
    - issue_document validates subtotal + tax_amount == total_amount after recomputation
    - pytest passes (or pre-existing failures only)
    - ruff clean
  </done>
</task>

<!-- ═══════════════════════════════════════════════════════════════════════
     WAVE C — Exporter + router fixes (depend on Wave A columns, parallel with Wave B)
     ═══════════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task C1: Exporter fixes — invoice_number, document type labels, issuer from document, due_date; router download fix</name>
  <files>
    backend/app/modules/billing/exporters.py
    backend/app/modules/billing/router.py
  </files>
  <action>
**Exporter fixes (exporters.py)**

**Fix E1 — doc_number: use document.invoice_number instead of UUID prefix**

In `_render_pdf` and `_render_xlsx`, replace:
```python
doc_number = str(document.id)[:8].upper()
```
with:
```python
doc_number = document.invoice_number or str(document.id)[:8].upper()
```
(Fallback to UUID prefix only if invoice_number is somehow None — should never happen for issued docs but defensive.)

**Fix E2 — Document title: PROFORMA for draft, correct type label per document_type**

Replace the hardcoded `"DOCUMENTO DE COBRANÇA"` string in both `_RotasPDF.header` and `_render_xlsx` title cell with a helper:

```python
_DOC_TYPE_LABELS = {
    "invoice": "FATURA",
    "debit_note": "NOTA DE DÉBITO",
    "credit_note": "NOTA DE CRÉDITO",
    "receipt": "RECIBO",
    "invoice_receipt": "FATURA-RECIBO",
}

def _doc_type_label(document: BillingDocument) -> str:
    if document.status == "draft":
        return "PROFORMA — SEM VALOR FISCAL"
    return _DOC_TYPE_LABELS.get(document.document_type, "DOCUMENTO DE COBRANÇA")
```

Pass this computed label into `_RotasPDF.__init__` as a new `doc_type` parameter (replacing the hardcoded "DOCUMENTO DE COBRANÇA" string in the `header()` method). In `_render_pdf`, pass `doc_type=_doc_type_label(document)` to the constructor. In `_render_xlsx`, compute the title cell value as `f"{issuer_name} — {_doc_type_label(document)}"`.

**Fix E3 — Remove status from PDF/XLSX metadata block**

In `_render_pdf`, delete the line:
```python
_meta_row("Estado do documento", _status_label(document.status))
```

In `_render_xlsx`, delete the `_meta(5, "Estado", _status_label(document.status))` call. Renumber subsequent `_meta` rows if needed.

**Fix E4 — Render client_nuit in metadata block**

In `_render_pdf`, after `_meta_row("Cliente", document.client_name or "—")`, add:
```python
if document.client_nuit:
    _meta_row("NUIT do Cliente", document.client_nuit)
```

In `_render_xlsx`, after `_meta(2, "Cliente", document.client_name or "—")`, add:
```python
if document.client_nuit:
    _meta(3, "NUIT do Cliente", document.client_nuit)
    # shift subsequent _meta row numbers by 1
```

**Fix E5 — issuer_name/issuer_nuit from document columns, not parameter default**

Change `render_billing_export` signature — remove hardcoded defaults and pull from document:
```python
def render_billing_export(
    document: BillingDocument,
    items: list[BillingItem],
    export_format: str,
) -> ExportArtifact:
    issuer_name = document.issuer_name or "ROTAS"
    issuer_nuit = document.issuer_nuit
    issuer_contact = issuer_nuit  # show NUIT as contact line in header/footer
    if export_format == "pdf":
        return _render_pdf(document, items, issuer_name=issuer_name, issuer_contact=issuer_contact)
    return _render_xlsx(document, items, issuer_name=issuer_name)
```
Update all callers in service.py (`export_document`) — remove the `issuer_name=` and `issuer_contact=` keyword args since they're now derived inside `render_billing_export`.

**Fix E6 — due_date in PDF/XLSX metadata block**

In `_render_pdf`, add after the contract/period rows:
```python
if document.due_date:
    _meta_row("Data de vencimento", _date(document.due_date))
```

In `_render_xlsx`, add a corresponding `_meta` row for `due_date`.

**Fix E7 — filename uses invoice_number**

```python
# PDF filename
filename = f"fatura_{document.invoice_number or str(document.id)[:8]}.pdf"
# XLSX filename
filename = f"fatura_{document.invoice_number or str(document.id)[:8]}.xlsx"
```

---

**Router fix (router.py)**

**Fix R1 — download_job_file: use file_id + Files service**

Replace the `download_job_file` handler body (lines 234-266) with:

```python
@router.get("/jobs/{job_id}/download")
async def download_job_file(
    job_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """BILL-01/02: Download completed export file via Files service. Tenant-isolated."""
    from sqlalchemy import select as sa_select
    from app.modules.billing.models import ExportJob
    from app.modules.files.service import get_file_download_url  # or equivalent

    job = await db.scalar(
        sa_select(ExportJob).where(
            ExportJob.id == job_id, ExportJob.tenant_id == principal.tenant_id
        )
    )
    if not job:
        raise ApiError("job_not_found", "Export job not found", status_code=404)
    if job.status != "done":
        raise ApiError(
            "job_not_done",
            f"Job status is '{job.status}' — not ready for download.",
            status_code=409,
        )

    # Prefer file_id (Files service) over legacy file_path
    if job.file_id:
        from app.modules.files.models import File
        file_record = await db.get(File, job.file_id)
        if not file_record or file_record.tenant_id != principal.tenant_id:
            raise ApiError("file_not_found", "Export file record not found.", status_code=404)
        # Redirect to the standard files download endpoint
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=f"/api/v1/files/{file_record.id}/download", status_code=302)

    # Legacy fallback: file_path on disk (backward compat for old jobs)
    if job.file_path:
        from pathlib import Path
        from fastapi.responses import FileResponse
        if not Path(job.file_path).exists():
            raise ApiError("file_not_found", "Export file not found on disk.", status_code=404)
        content_type = (
            "application/pdf"
            if job.job_type == "billing_pdf"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return FileResponse(path=job.file_path, media_type=content_type)

    raise ApiError("file_not_found", "No file associated with this export job.", status_code=404)
```

Check what `get_file_download_url` or the download function is actually named in `backend/app/modules/files/service.py` before using it — use the redirect approach above to avoid importing unstable internals.
  </action>
  <verify>
    <automated>cd backend && python -m ruff check app/modules/billing/exporters.py app/modules/billing/router.py --select E,F,I && python -c "from app.modules.billing.exporters import render_billing_export, _doc_type_label; print('exporters import OK')"</automated>
  </verify>
  <done>
    - PDF/XLSX doc_number uses document.invoice_number (not UUID prefix)
    - Draft documents render "PROFORMA — SEM VALOR FISCAL" as title
    - document_type mapped to Portuguese label (FATURA / NOTA DE CRÉDITO / NOTA DE DÉBITO / RECIBO / FATURA-RECIBO)
    - "Estado do documento" row removed from PDF/XLSX metadata
    - client_nuit rendered in metadata block when present
    - issuer_name/issuer_nuit pulled from document columns (not hardcoded "ROTAS")
    - iva_rate=None on issued doc raises ValueError (no silent fallback to 17)
    - due_date shown in metadata block
    - filename uses invoice_number
    - download_job_file uses file_id redirect to /files/{id}/download with file_path as fallback
    - ruff clean
  </done>
</task>

<!-- ═══════════════════════════════════════════════════════════════════════
     WAVE D — New endpoints + list_documents filter/count (parallel with Wave B/C)
     ═══════════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task D1: New endpoints — AR summary, client statement, payments list; list_documents filters + total_count</name>
  <files>
    backend/app/modules/billing/service.py
    backend/app/modules/billing/router.py
  </files>
  <action>
**Part 1 — list_documents: add document_type + client_id filters and total_count**

In `list_documents` service function, add two new optional parameters:
```python
async def list_documents(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    status_filter: str | None = None,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
    document_type: str | None = None,   # NEW
    client_id: UUID | None = None,       # NEW
    limit: int = 50,
    offset: int = 0,
) -> dict:   # returns {items: [...], total: int}
```

Add filters to query:
```python
if document_type:
    query = query.where(BillingDocument.document_type == document_type)
if client_id:
    query = query.where(BillingDocument.client_id == client_id)
```

Add a separate COUNT query for total:
```python
count_query = (
    select(func.count(BillingDocument.id))
    .where(BillingDocument.tenant_id == tenant_id)
)
# apply same filters as main query (status, period, document_type, client_id)
if status_filter:
    count_query = count_query.where(BillingDocument.status == status_filter)
if period_start:
    count_query = count_query.where(BillingDocument.billing_period_start >= period_start)
if period_end:
    count_query = count_query.where(BillingDocument.billing_period_start < period_end)
if document_type:
    count_query = count_query.where(BillingDocument.document_type == document_type)
if client_id:
    count_query = count_query.where(BillingDocument.client_id == client_id)

total = await db.scalar(count_query) or 0
```

Return: `{"items": [...], "total": int(total)}`

Update the router `list_documents` endpoint to pass the new params and accept the new return shape.

---

**Part 2 — list_ar_documents: add total_count**

Apply same pattern to `list_ar_documents`: add a COUNT query with the same filters (tenant, status IN issued/overdue, due_date not null, document_type=invoice, contract_id if provided). Since `aging_bucket` filtering is done in Python after DB fetch (not in SQL), total_count reflects DB-filtered rows before Python bucket filter. Return `{"items": [...], "total": int(total)}`.

---

**Part 3 — New service function: get_ar_summary**

Add after `list_ar_documents`:

```python
async def get_ar_summary(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict:
    """GET /billing/ar/summary — totals per aging bucket in MZN."""
    stmt = (
        select(BillingDocument)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.status.in_(("issued", "overdue")),
            BillingDocument.due_date.isnot(None),
            BillingDocument.document_type == "invoice",
        )
    )
    result = await db.execute(stmt)
    docs = list(result.scalars())

    today = datetime.now(UTC)
    buckets: dict[str, Decimal] = {
        "current": Decimal("0"),
        "1_30": Decimal("0"),
        "31_60": Decimal("0"),
        "61_90": Decimal("0"),
        "over_90": Decimal("0"),
    }
    for doc in docs:
        aging = _compute_aging(doc, today)
        bucket = aging["aging_bucket"]
        buckets[bucket] = (buckets[bucket] + doc.total_amount).quantize(Decimal("0.01"))

    total_ar = sum(buckets.values()).quantize(Decimal("0.01"))
    return {
        "current": buckets["current"],
        "1_30": buckets["1_30"],
        "31_60": buckets["31_60"],
        "61_90": buckets["61_90"],
        "over_90": buckets["over_90"],
        "total_ar": total_ar,
        "currency": "MZN",
    }
```

---

**Part 4 — New service function: get_client_statement**

```python
async def get_client_statement(
    db: AsyncSession,
    tenant_id: UUID,
    client_id: UUID,
) -> dict:
    """GET /billing/clients/{client_id}/statement"""
    from app.modules.clients.models import Client  # avoid circular at module level

    client = await db.get(Client, client_id)
    if not client or client.tenant_id != tenant_id:
        raise ApiError("client_not_found", "Client not found", status_code=404)

    # Total invoiced = sum of issued/paid/overdue invoice totals
    invoiced_result = await db.execute(
        select(func.coalesce(func.sum(BillingDocument.total_amount), 0))
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.client_id == client_id,
            BillingDocument.document_type == "invoice",
            BillingDocument.status.in_(("issued", "paid", "overdue")),
        )
    )
    total_invoiced = Decimal(str(invoiced_result.scalar_one())).quantize(Decimal("0.01"))

    # Total paid = sum of confirmed payment allocations for this client's invoices
    paid_result = await db.execute(
        select(func.coalesce(func.sum(PaymentAllocation.amount_applied), 0))
        .join(ClientPayment, ClientPayment.id == PaymentAllocation.payment_id)
        .join(BillingDocument, BillingDocument.id == PaymentAllocation.billing_document_id)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.client_id == client_id,
            ClientPayment.status == "confirmed",
        )
    )
    total_paid = Decimal(str(paid_result.scalar_one())).quantize(Decimal("0.01"))

    balance = (total_invoiced - total_paid).quantize(Decimal("0.01"))

    # Recent documents (last 50)
    docs_result = await db.execute(
        select(BillingDocument)
        .where(
            BillingDocument.tenant_id == tenant_id,
            BillingDocument.client_id == client_id,
        )
        .order_by(BillingDocument.created_at.desc())
        .limit(50)
    )
    documents = [
        {
            "id": d.id,
            "invoice_number": d.invoice_number,
            "document_type": d.document_type,
            "status": d.status,
            "total_amount": d.total_amount,
            "currency": d.currency,
            "issued_at": d.issued_at,
            "due_date": d.due_date,
        }
        for d in docs_result.scalars()
    ]

    return {
        "client_id": client_id,
        "client_name": client.name,
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "balance": balance,
        "currency": "MZN",
        "documents": documents,
    }
```

---

**Part 5 — New service function: list_payments**

```python
async def list_payments(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    client_id: UUID | None = None,
    status: str | None = None,
    value_date_start: datetime | None = None,
    value_date_end: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """GET /billing/payments — paginated list with filters."""
    query = (
        select(ClientPayment)
        .where(ClientPayment.tenant_id == tenant_id)
        .order_by(ClientPayment.created_at.desc())
    )
    if client_id:
        query = query.where(ClientPayment.client_id == client_id)
    if status:
        query = query.where(ClientPayment.status == status)
    if value_date_start:
        query = query.where(ClientPayment.value_date >= value_date_start)
    if value_date_end:
        query = query.where(ClientPayment.value_date < value_date_end)

    count_query = select(func.count(ClientPayment.id)).where(ClientPayment.tenant_id == tenant_id)
    if client_id:
        count_query = count_query.where(ClientPayment.client_id == client_id)
    if status:
        count_query = count_query.where(ClientPayment.status == status)
    if value_date_start:
        count_query = count_query.where(ClientPayment.value_date >= value_date_start)
    if value_date_end:
        count_query = count_query.where(ClientPayment.value_date < value_date_end)

    total = await db.scalar(count_query) or 0
    rows = await db.execute(query.limit(limit).offset(offset))
    payments = list(rows.scalars())

    # Fetch allocations for all payments in bulk
    payment_ids = [p.id for p in payments]
    alloc_map: dict = {}
    if payment_ids:
        alloc_rows = await db.execute(
            select(PaymentAllocation).where(PaymentAllocation.payment_id.in_(payment_ids))
        )
        for a in alloc_rows.scalars():
            alloc_map.setdefault(a.payment_id, []).append(a)

    return {
        "items": [serialize_payment(p, alloc_map.get(p.id, [])) for p in payments],
        "total": int(total),
    }
```

---

**Part 6 — Router: wire all 4 new endpoints**

Add to router.py:

```python
@router.get("/ar/summary")
async def get_ar_summary(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """AR aging summary — totals per bucket in MZN."""
    return await service.get_ar_summary(db, principal.tenant_id)


@router.get("/clients/{client_id}/statement")
async def get_client_statement(
    client_id: UUID,
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Client AR statement — total invoiced, paid, balance, recent documents."""
    return await service.get_client_statement(db, principal.tenant_id, client_id)


@router.get("/payments")
async def list_payments(
    principal: Annotated[Principal, Depends(require_roles(*DASHBOARD_ROLES))],
    db: Annotated[AsyncSession, Depends(get_session)],
    client_id: UUID | None = None,
    status: str | None = None,
    value_date_start: datetime | None = None,
    value_date_end: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Paginated list of client payments with optional filters."""
    return await service.list_payments(
        db,
        principal.tenant_id,
        client_id=client_id,
        status=status,
        value_date_start=value_date_start,
        value_date_end=value_date_end,
        limit=limit,
        offset=offset,
    )
```

Also update the existing `list_documents` router endpoint to pass `document_type` and `client_id` query params to the service.
  </action>
  <verify>
    <automated>cd backend && python -m ruff check app/modules/billing/service.py app/modules/billing/router.py --select E,F,I && python -m pytest tests/ -x -q --tb=short -k "billing" 2>&1 | tail -30</automated>
  </verify>
  <done>
    - list_documents accepts document_type and client_id filters; returns {items, total}
    - list_ar_documents returns {items, total}
    - GET /billing/ar/summary endpoint exists and returns {current, 1_30, 31_60, 61_90, over_90, total_ar, currency}
    - GET /billing/clients/{client_id}/statement endpoint returns {client_id, client_name, total_invoiced, total_paid, balance, currency, documents}
    - GET /billing/payments endpoint returns paginated {items, total} with client_id/status/value_date filters
    - ruff clean
    - pytest billing tests pass (or pre-existing failures only)
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run alembic upgrade: `cd backend && python -m alembic upgrade head` — should apply b1c2d3e4f5a6 cleanly
2. Run full test suite: `cd backend && python -m pytest tests/ -x --tb=short` — should pass or show only pre-existing failures
3. Grep for literal 0.1700: `grep -rn "0\.1700" backend/app/modules/billing/` — should return zero results
4. Confirm new endpoints exist: `cd backend && python -c "from app.modules.billing.router import router; routes = [r.path for r in router.routes]; print([r for r in routes if 'ar/summary' in r or 'statement' in r or '/payments' in r])"`
5. Run ruff on all changed files: `cd backend && python -m ruff check app/modules/billing/ app/modules/contracts/models.py --select E,F,I,B`
</verification>

<success_criteria>
- Zero occurrences of Decimal("0.1700") in billing module
- Alembic migration applies cleanly (issuer_name, issuer_nuit, parent_invoice_number, payment_terms_days)
- billing_iva_backfill.sql exists and is syntactically valid SQL
- issued → cancelled transition blocked by state machine (returns 409)
- PDF/XLSX shows PROFORMA for drafts, correct document type label for issued docs
- PDF/XLSX issuer from document.issuer_name/issuer_nuit (not hardcoded "ROTAS")
- download_job_file redirects via Files service for file_id-backed jobs
- GET /billing/ar/summary, GET /billing/clients/{id}/statement, GET /billing/payments all return 200
- list_documents accepts document_type and client_id query params and returns total count
- ruff passes with 0 errors across all modified files
- pytest passes (billing module tests)
</success_criteria>

<output>
After completion, create `.planning/quick/260620-cme-billing-module-production-hardening/260620-cme-SUMMARY.md` with:
- What was changed and in which files
- Migration revision ID used
- Any deviations from plan (e.g. function name differences found in files/service.py)
- Ruff and pytest results
</output>
