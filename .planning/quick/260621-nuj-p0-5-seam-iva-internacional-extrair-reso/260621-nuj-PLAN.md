---
phase: quick-260621-nuj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/modules/billing/domain.py
  - backend/app/modules/billing/models.py
  - backend/app/modules/billing/service.py
  - backend/alembic/versions/iva01_iva_basis_columns.py
  - backend/tests/test_billing_domain.py
autonomous: true
requirements: [IVA-SEAM-01]

must_haves:
  truths:
    - "resolve_iva returns (Decimal('0.1600'), 'standard_16') for domestic trips"
    - "resolve_iva raises 422 ApiError with code 'international_iva_rate_unconfirmed' for international trips with no contract override"
    - "resolve_iva returns contract.iva_rate with basis 'contract_override' when contract has explicit iva_rate"
    - "BillingDocument and BillingItem have iva_basis VARCHAR(40) columns"
    - "create_document persists iva_basis on each BillingItem"
    - "All DEFAULT_IVA_RATE usage in service.py routes through resolve_iva"
  artifacts:
    - path: "backend/app/modules/billing/domain.py"
      provides: "resolve_iva function"
      exports: ["resolve_iva"]
    - path: "backend/alembic/versions/iva01_iva_basis_columns.py"
      provides: "DDL: iva_basis columns on billing_documents and billing_items"
    - path: "backend/tests/test_billing_domain.py"
      provides: "3 new tests for resolve_iva"
  key_links:
    - from: "billing/service.py"
      to: "billing/domain.py:resolve_iva"
      via: "replaces DEFAULT_IVA_RATE at lines 618, 1193, 1280"
      pattern: "resolve_iva"
    - from: "BillingItem constructor"
      to: "iva_basis column"
      via: "iva_basis=iva_basis in BillingItem(...)"
---

<objective>
Extract IVA resolution logic into a `resolve_iva(trip, contract)` seam in domain.py,
add `iva_basis` audit columns to both billing models, write a migration, and wire
all three DEFAULT_IVA_RATE call sites in service.py through the new seam.

Purpose: International trips (is_international=True) currently silently inherit the
domestic 16% IVA rate. Under Mozambican VAT law, international transport is likely
zero-rated. Until legal confirmation arrives, the correct posture is fail-closed:
refuse to invoice international trips unless the contract has an explicit iva_rate
override. This makes the gap visible rather than silently wrong.

Output:
- domain.py: resolve_iva function + IvaResolutionError type (via ApiError)
- models.py: iva_basis Mapped[str | None] on BillingDocument and BillingItem
- alembic migration: ALTER TABLE ... ADD COLUMN iva_basis VARCHAR(40) x2
- service.py: all three DEFAULT_IVA_RATE sites replaced with resolve_iva call
- test_billing_domain.py: 3 new tests covering domestic / international / contract override
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260621-nuj-p0-5-seam-iva-internacional-extrair-reso/260621-nuj-PLAN.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From backend/app/modules/billing/domain.py (existing):
```python
# Already contains: BillableTripCandidate, billing_status_for_candidate,
# can_create_billing_item, belongs_to_billing_period, normalize_period_bounds
# resolve_iva goes HERE (not in service.py)
```

From backend/app/modules/billing/service.py (relevant lines):
```python
DEFAULT_IVA_RATE = Decimal("0.1600")   # line 38 — to KEEP as fallback constant only

# Line 618 (inside create_document trip loop):
iva_rate = DEFAULT_IVA_RATE
iva_amount = (amount * iva_rate).quantize(Decimal("0.01"))
item = BillingItem(..., iva_rate=iva_rate, iva_amount=iva_amount, ...)

# Line 1193 (create_debit_note signature):
async def create_debit_note(..., iva_rate: Decimal = DEFAULT_IVA_RATE) -> dict:

# Line 1280 (create_credit_note signature):
async def create_credit_note(..., iva_rate: Decimal = DEFAULT_IVA_RATE) -> dict:
```

From backend/app/modules/billing/models.py (existing columns):
```python
# BillingDocument already has:
iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
# ADD after it:
iva_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)

# BillingItem already has:
iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
# ADD after it:
iva_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
```

From backend/app/modules/trips/models.py:
```python
is_international: Mapped[bool] = mapped_column(Boolean(), server_default="false",
                                                 nullable=False, default=False)
```

From backend/app/modules/contracts/models.py:
# Contract does NOT have iva_rate — use getattr(contract, "iva_rate", None)

From backend/app/core/errors.py (or equivalent):
# ApiError is imported in service.py — use same import in domain.py
```python
from app.core.errors import ApiError
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: resolve_iva in domain.py + iva_basis columns in models.py + migration</name>
  <files>
    backend/app/modules/billing/domain.py
    backend/app/modules/billing/models.py
    backend/alembic/versions/iva01_iva_basis_columns.py
    backend/tests/test_billing_domain.py
  </files>
  <behavior>
    - resolve_iva(trip, contract) -> tuple[Decimal, str]
    - domestic trip (is_international=False), no contract override: returns (Decimal("0.1600"), "standard_16")
    - international trip (is_international=True), no contract override: raises ApiError("international_iva_rate_unconfirmed", ..., status_code=422)
    - contract with explicit iva_rate (any value, even 0.00): returns (contract.iva_rate, "contract_override") — bypasses both domestic and international checks
    - trip=None falls through to domestic default (safe for debit/credit note callers that pass trip=None)
  </behavior>
  <action>
    **Step A — Write tests first (RED):**

    In `backend/tests/test_billing_domain.py`, add 3 tests at the end of the file
    (after existing tests, keep all existing imports and tests intact):

    ```python
    from dataclasses import dataclass
    from decimal import Decimal
    import pytest
    from app.modules.billing.domain import resolve_iva
    from app.core.errors import ApiError  # adjust import if ApiError lives elsewhere

    @dataclass
    class _FakeTrip:
        is_international: bool = False

    @dataclass
    class _FakeContract:
        iva_rate: Decimal | None = None

    def test_resolve_iva_domestic_returns_standard_16() -> None:
        rate, basis = resolve_iva(_FakeTrip(is_international=False), _FakeContract())
        assert rate == Decimal("0.1600")
        assert basis == "standard_16"

    def test_resolve_iva_international_raises_422() -> None:
        with pytest.raises(ApiError) as exc_info:
            resolve_iva(_FakeTrip(is_international=True), _FakeContract())
        assert exc_info.value.code == "international_iva_rate_unconfirmed"
        assert exc_info.value.status_code == 422

    def test_resolve_iva_contract_override_wins_for_international() -> None:
        rate, basis = resolve_iva(
            _FakeTrip(is_international=True),
            _FakeContract(iva_rate=Decimal("0.00")),
        )
        assert rate == Decimal("0.00")
        assert basis == "contract_override"
    ```

    Run: `cd backend && python -m pytest tests/test_billing_domain.py -x -q 2>&1 | tail -20`
    Tests must FAIL (ImportError or AttributeError on resolve_iva) before proceeding.

    **Step B — Implement resolve_iva in domain.py (GREEN):**

    Add to `backend/app/modules/billing/domain.py`:
    1. Add imports at the top:
       ```python
       from decimal import Decimal
       from app.core.errors import ApiError
       ```
       (check existing imports — Decimal may already be imported)

    2. Add constant after existing module-level constants:
       ```python
       DEFAULT_IVA_RATE: Decimal = Decimal("0.1600")
       ```

    3. Add function at the bottom of domain.py:
       ```python
       def resolve_iva(trip, contract) -> tuple[Decimal, str]:
           """Resolve the applicable IVA rate and legal basis for a billing item.

           Returns (rate, basis) where:
           - rate: Decimal between 0.00 and 1.00
           - basis: short string for audit trail ('standard_16', 'contract_override',
                    'international_pending_legal')

           Fail-closed: international trips without a contract override raise 422.
           The operator must configure contract.iva_rate explicitly to proceed.
           """
           contract_iva = getattr(contract, "iva_rate", None) if contract else None
           if contract_iva is not None:
               return contract_iva, "contract_override"

           if trip and getattr(trip, "is_international", False):
               raise ApiError(
                   "international_iva_rate_unconfirmed",
                   "Taxa IVA para transporte internacional requer confirmação legal. "
                   "Configure a taxa no contrato para emitir este documento.",
                   status_code=422,
               )

           return DEFAULT_IVA_RATE, "standard_16"
       ```

    Run: `cd backend && python -m pytest tests/test_billing_domain.py -x -q 2>&1 | tail -20`
    All 3 new tests must PASS.

    **Step C — Add iva_basis columns to models.py:**

    In `backend/app/modules/billing/models.py`:
    - After `iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)` on
      `BillingDocument` (line 63), add:
      ```python
      iva_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
      ```
    - After `iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)` on
      `BillingItem` (line 138), add:
      ```python
      iva_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
      ```
    - String is already imported — no new import needed.

    **Step D — Write Alembic migration:**

    Create `backend/alembic/versions/iva01_iva_basis_columns.py`:

    ```python
    """add iva_basis to billing_documents and billing_items

    Revision ID: iva01a1b2c3d4
    Revises: <current_head>
    Create Date: 2026-06-21

    No RLS changes needed — these are new columns on existing RLS-protected tables.
    """
    from alembic import op
    import sqlalchemy as sa

    revision = "iva01a1b2c3d4"
    down_revision = None  # EXECUTOR: replace with actual current alembic head
    branch_labels = None
    depends_on = None


    def upgrade() -> None:
        op.add_column(
            "billing_documents",
            sa.Column("iva_basis", sa.String(40), nullable=True),
        )
        op.add_column(
            "billing_items",
            sa.Column("iva_basis", sa.String(40), nullable=True),
        )


    def downgrade() -> None:
        op.drop_column("billing_documents", "iva_basis")
        op.drop_column("billing_items", "iva_basis")
    ```

    IMPORTANT: The executor must set `down_revision` to the actual current Alembic head.
    Run: `cd backend && python -m alembic heads` to find the current head revision,
    then set `down_revision = "<that_revision>"`.

    After setting down_revision, run: `cd backend && python -m alembic upgrade head`
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/test_billing_domain.py -x -q 2>&1 | tail -30</automated>
  </verify>
  <done>
    All billing domain tests pass (including the 3 new resolve_iva tests).
    resolve_iva is importable from app.modules.billing.domain.
    Migration file exists with correct down_revision.
    alembic upgrade head completes without error.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire resolve_iva into service.py — replace all 3 DEFAULT_IVA_RATE call sites</name>
  <files>
    backend/app/modules/billing/service.py
  </files>
  <action>
    **Add import** at the top of service.py where billing domain imports live:
    ```python
    from app.modules.billing.domain import (
        ...existing imports...,
        resolve_iva,
    )
    ```
    Also import DEFAULT_IVA_RATE from domain instead of defining it in service.py:
    ```python
    from app.modules.billing.domain import (
        ...existing imports...,
        DEFAULT_IVA_RATE,
        resolve_iva,
    )
    ```
    Then REMOVE the `DEFAULT_IVA_RATE = Decimal("0.1600")` line from service.py (line 38).

    **Call site 1 — create_document (line ~618, inside the trip loop):**

    Replace:
    ```python
    iva_rate = DEFAULT_IVA_RATE
    iva_amount = (amount * iva_rate).quantize(Decimal("0.01"))
    item = BillingItem(
        ...
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        ...
    )
    ```

    With:
    ```python
    iva_rate, iva_basis = resolve_iva(trip, contract)
    iva_amount = (amount * iva_rate).quantize(Decimal("0.01"))
    item = BillingItem(
        ...
        iva_rate=iva_rate,
        iva_basis=iva_basis,
        iva_amount=iva_amount,
        ...
    )
    ```

    Note: `trip` and `contract` are already in scope at that point in the loop.
    If `contract` is not directly in scope (it may be loaded as `contracts[contract_id]`
    or similar), inspect the surrounding code to find the contract variable name and
    use that.

    **Call site 2 — create_debit_note (line ~1193):**

    The function signature accepts `iva_rate` as a parameter (caller-supplied override).
    Debit notes are created against an already-issued parent document — the trip context
    is no longer available. Keep the parameter but default to calling resolve_iva with
    trip=None (domestic fallback):

    Change signature default from `DEFAULT_IVA_RATE` to remain explicit:
    ```python
    async def create_debit_note(
        db: AsyncSession,
        tenant_id: UUID,
        parent_id: UUID,
        amount: Decimal,
        reason: str,
        iva_rate: Decimal | None = None,
    ) -> dict:
        if iva_rate is None:
            iva_rate, _basis = resolve_iva(trip=None, contract=None)
        # rest of function unchanged
    ```

    Also add `iva_basis` to the BillingDocument constructor call inside this function:
    ```python
    note = BillingDocument(
        ...
        iva_rate=iva_rate,
        iva_basis=_basis if iva_rate is None else "contract_override",
        ...
    )
    ```
    Actually, simpler: always resolve to get the basis:
    ```python
    _resolved_rate, _basis = resolve_iva(trip=None, contract=None)
    effective_rate = iva_rate if iva_rate is not None else _resolved_rate
    effective_basis = "contract_override" if iva_rate is not None else _basis
    # then use effective_rate and effective_basis in BillingDocument(...)
    ```

    **Call site 3 — create_credit_note (line ~1280):**
    Apply the same pattern as create_debit_note.

    After changes, verify no remaining `DEFAULT_IVA_RATE` usage in service.py
    (the constant is now imported from domain, but should not be used directly in any
    calculation — only resolve_iva should be called):
    ```bash
    grep -n "DEFAULT_IVA_RATE" backend/app/modules/billing/service.py
    ```
    This should return zero lines (the import line is gone; the constant is only in domain.py now).

    Run full billing tests to confirm nothing broke:
    ```bash
    cd backend && python -m pytest tests/test_billing_domain.py tests/test_fiscal_documents.py tests/test_fiscal_compliance.py tests/test_cargo_billing_flow.py -x -q 2>&1 | tail -40
    ```
  </action>
  <verify>
    <automated>cd backend && grep -n "DEFAULT_IVA_RATE" backend/app/modules/billing/service.py; echo "---"; python -m pytest tests/test_billing_domain.py tests/test_fiscal_documents.py tests/test_fiscal_compliance.py tests/test_cargo_billing_flow.py -x -q 2>&1 | tail -40</automated>
  </verify>
  <done>
    grep returns zero matches for DEFAULT_IVA_RATE in service.py (constant moved to domain.py only).
    All billing-related tests pass.
    service.py imports resolve_iva and DEFAULT_IVA_RATE from domain.py.
    BillingItem at line ~618 passes iva_basis=iva_basis to the constructor.
  </done>
</task>

</tasks>

<verification>
After both tasks complete:

1. `cd backend && python -m pytest tests/test_billing_domain.py -v 2>&1 | tail -20`
   — All tests pass, including 3 new resolve_iva tests.

2. `cd backend && python -m pytest tests/ -x -q 2>&1 | tail -20`
   — Full test suite green.

3. `cd backend && python -m alembic current`
   — Shows iva01a1b2c3d4 as current head.

4. `cd backend && python -c "from app.modules.billing.domain import resolve_iva; print('ok')"`
   — Imports cleanly.
</verification>

<success_criteria>
- resolve_iva lives in billing/domain.py, exported cleanly
- Domestic trip gets (Decimal("0.1600"), "standard_16") — no behaviour change for 99% of trips
- International trip with no contract override raises 422 "international_iva_rate_unconfirmed"
- Contract with explicit iva_rate gets "contract_override" regardless of trip type
- BillingDocument.iva_basis and BillingItem.iva_basis columns exist in DB after migration
- No DEFAULT_IVA_RATE inline calculation remains in service.py
- All existing billing tests pass unchanged
</success_criteria>

<output>
After completion, create `.planning/quick/260621-nuj-p0-5-seam-iva-internacional-extrair-reso/260621-nuj-SUMMARY.md`

Summary must record:
- What was built (resolve_iva seam, iva_basis columns, migration)
- The 3 basis strings: standard_16, contract_override, international_pending_legal
- That Contract.iva_rate does NOT exist yet — getattr fallback used
- Migration revision ID actually used
- Test count before/after
</output>
