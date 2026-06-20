---
phase: quick
plan: 260620-sik
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/alembic/versions/a3b4c5d6e7f8_add_tenant_document_profiles.py
  - backend/alembic/versions/c5d6e7f8a9b0_add_billing_document_issuer_fields.py
  - backend/app/modules/tenants/models.py
  - backend/app/modules/tenants/schemas.py
  - backend/app/modules/tenants/service.py
  - backend/app/modules/tenants/router.py
  - backend/app/modules/billing/models.py
  - backend/app/modules/billing/service.py
  - backend/app/modules/billing/exporters.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Tenant can configure legal name, address, NUIT, phone, email, bank details via PUT /api/v1/tenants/me/document-profile"
    - "Billing PDF rendered with PHC-style 2-column header (issuer left, client box right)"
    - "PDF metadata bar shows document number prominently at right; totals split IVA table (left) vs summary (right)"
    - "Invoice number format respects invoice_prefix, invoice_seq_padding from profile; fallback YYYY/NNNN preserved when no profile"
    - "BillingDocument snapshot captures issuer_address, issuer_bank_details, payment_conditions at creation time"
    - "Existing tests (test_billing_api, test_fiscal_compliance, test_ar_phase7) continue to pass"
  artifacts:
    - path: "backend/alembic/versions/a3b4c5d6e7f8_add_tenant_document_profiles.py"
      provides: "Migration A: tenant_document_profiles table + RLS + GRANT"
    - path: "backend/alembic/versions/c5d6e7f8a9b0_add_billing_document_issuer_fields.py"
      provides: "Migration B: new snapshot columns on billing_documents"
    - path: "backend/app/modules/tenants/models.py"
      provides: "TenantDocumentProfile SQLAlchemy model"
    - path: "backend/app/modules/billing/exporters.py"
      provides: "Redesigned _RotasPDF with PHC reference layout"
  key_links:
    - from: "billing/service.py _assign_invoice_number"
      to: "tenants TenantDocumentProfile"
      via: "db.scalar(select(TenantDocumentProfile))"
      pattern: "TenantDocumentProfile"
    - from: "billing/service.py create_document"
      to: "BillingDocument issuer_address/payment_conditions"
      via: "_snapshot_profile"
      pattern: "issuer_address"
    - from: "billing/exporters.py _render_pdf"
      to: "document.issuer_address/issuer_bank_details"
      via: "direct column reads"
      pattern: "issuer_address"
---

<objective>
Implement per-tenant document profile system and redesign billing PDF exporter to match PHC Software / Digitus reference layout.

Purpose: Faturas geradas pelo ROTAS devem ter aparência profissional com logótipo, morada, dados bancários e layout de totais IVA compatível com referência fiscal moçambicana.
Output: Nova tabela tenant_document_profiles, 2 colunas novas em billing_documents, endpoints GET/PUT /document-profile, e exporters.py completamente redesenhado.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260620-sik-tenant-document-profiles-redesenho-expor/260620-sik-PLAN.md

<interfaces>
<!-- Extracted from existing code — do NOT re-read these files for interface discovery -->

From backend/app/modules/billing/models.py — BillingDocument existing columns:
```python
issuer_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
issuer_nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
parent_invoice_number: Mapped[str | None] = mapped_column(String(12), nullable=True)
client_nuit: Mapped[str | None] = mapped_column(String(20), nullable=True)
invoice_number: Mapped[str | None] = mapped_column(String(12), nullable=True)
iva_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
document_type: Mapped[str] = mapped_column(String(30), default="invoice")
due_date: Mapped[datetime | None]
```

From backend/app/modules/billing/exporters.py — current public signature (MUST NOT change):
```python
def render_billing_export(
    document: BillingDocument,
    items: list[BillingItem],
    export_format: str,
) -> ExportArtifact:
```

Current _render_pdf reads: document.issuer_name, document.issuer_nuit, document.invoice_number,
document.iva_rate (raises ValueError if None), document.subtotal, document.tax_amount, document.total_amount

From backend/app/modules/billing/service.py — existing _assign_invoice_number pattern:
```python
year = datetime.now(UTC).year
tid_clean = str(tenant_id).replace("-", "")
seq_name = f"invoice_seq_{tid_clean}_{year}"
await db.execute(text(f'CREATE SEQUENCE IF NOT EXISTS "{seq_name}" START 1 ...'))
result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
seq_val = result.scalar_one()
invoice_number = f"{year}/{seq_val:04d}"
```

From backend/app/modules/tenants/router.py — RLS pattern for dashboard endpoints:
```python
# Uses AsyncSessionLocal() with set_rls_tenant(str(effective_tenant_id)) before/after
# Simple dashboard-only route uses: Depends(require_permission(ADMIN_USERS)) + Depends(get_session)
# The /me/limits route is the simplest model to follow for new document-profile endpoints
```

Alembic head chain (most recent migrations):
- b1c2d3e4f5a6 — billing issuer/parent_invoice_number (Revises: restore_composite_indexes)
- e1f2a3b4c5d6 — add_vehicle_insurance (Revises: e1a2b3c4d5f6)
- tp11 — immutability_triggers (Revises: tp10)

There are multiple heads. New migrations must pick the correct down_revision. Check actual heads
by reading the most recent migration files: b1c2d3e4f5a6 and e1f2a3b4c5d6 both appear to be
recent leaf nodes. Use a merge migration if needed, or set down_revision to the most recent
single head (e1f2a3b4c5d6 for Migration A, then a3b4c5d6e7f8 for Migration B).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Alembic migrations — tenant_document_profiles + billing_documents new columns</name>
  <files>
    backend/alembic/versions/a3b4c5d6e7f8_add_tenant_document_profiles.py
    backend/alembic/versions/c5d6e7f8a9b0_add_billing_document_issuer_fields.py
  </files>
  <action>
Create two Alembic migration files.

**Migration A** — `a3b4c5d6e7f8_add_tenant_document_profiles.py`:

Before writing, determine down_revision: read the last few migration files in backend/alembic/versions/ to find the current single head (or heads). If there are multiple heads, set down_revision to the one that is NOT already a parent (i.e., a leaf). If truly ambiguous, pick `e1f2a3b4c5d6` (add_vehicle_insurance) which appears to be a recent leaf.

```python
"""add tenant_document_profiles table

Revision ID: a3b4c5d6e7f8
Revises: <determined above>
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a3b4c5d6e7f8"
down_revision = "<determined>"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tenant_document_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, unique=True),
        sa.Column("logo_file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("address_line1", sa.String(160), nullable=True),
        sa.Column("address_line2", sa.String(160), nullable=True),
        sa.Column("city", sa.String(80), nullable=True),
        sa.Column("province", sa.String(80), nullable=True),
        sa.Column("country", sa.String(80), nullable=False, server_default="Moçambique"),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(120), nullable=True),
        sa.Column("website", sa.String(160), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("bank_account", sa.String(60), nullable=True),
        sa.Column("bank_nib", sa.String(60), nullable=True),
        sa.Column("invoice_prefix", sa.String(10), nullable=False, server_default=""),
        sa.Column("invoice_seq_padding", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("invoice_start_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("per_type_sequences", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("payment_conditions", sa.String(80), nullable=False, server_default="Pronto"),
        sa.Column("invoice_footer", sa.Text(), nullable=True),
        sa.Column("show_bank_details", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_logo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_tenant_document_profiles_tenant_id", "tenant_document_profiles", ["tenant_id"])
    # v2.0 Migration Rules — MANDATORY RLS + GRANT in same migration as CREATE TABLE
    op.execute("ALTER TABLE tenant_document_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_document_profiles FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY rls_tenant_document_profiles ON tenant_document_profiles
            USING (tenant_id::text = current_setting('app.tenant_id', true))
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_document_profiles TO rotas_app")

def downgrade():
    op.execute("DROP POLICY IF EXISTS rls_tenant_document_profiles ON tenant_document_profiles")
    op.drop_index("ix_tenant_document_profiles_tenant_id", table_name="tenant_document_profiles")
    op.drop_table("tenant_document_profiles")
```

**Migration B** — `c5d6e7f8a9b0_add_billing_document_issuer_fields.py`:
down_revision = "a3b4c5d6e7f8"

Add these columns to billing_documents:
- `issuer_address` Text nullable
- `issuer_phone` VARCHAR(40) nullable
- `issuer_email` VARCHAR(120) nullable
- `issuer_city` VARCHAR(80) nullable
- `issuer_bank_details` Text nullable
- `payment_conditions` VARCHAR(80) nullable
- `commercial_discount` NUMERIC(5,4) nullable server_default "0"
- `financial_discount` NUMERIC(5,4) nullable server_default "0"

Use op.add_column for each. downgrade drops all 8 columns.
  </action>
  <verify>
    <automated>cd /c/Users/Quive/OneDrive/Documents/Rotas/backend && python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config('alembic.ini'); s=ScriptDirectory.from_config(c); print('heads:', [r.revision for r in s.get_revisions('heads')])"</automated>
  </verify>
  <done>Both migration files parse without error; a3b4c5d6e7f8 creates tenant_document_profiles with RLS; c5d6e7f8a9b0 adds 8 columns to billing_documents</done>
</task>

<task type="auto">
  <name>Task 2: TenantDocumentProfile model + schemas + service + router endpoints</name>
  <files>
    backend/app/modules/tenants/models.py
    backend/app/modules/tenants/schemas.py
    backend/app/modules/tenants/service.py
    backend/app/modules/tenants/router.py
  </files>
  <action>
**models.py** — append TenantDocumentProfile after Tenant class:

```python
class TenantDocumentProfile(Base):
    __tablename__ = "tenant_document_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), unique=True, index=True)
    logo_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(String(160), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(160), nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    province: Mapped[str | None] = mapped_column(String(80), nullable=True)
    country: Mapped[str] = mapped_column(String(80), default="Moçambique")
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(160), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bank_nib: Mapped[str | None] = mapped_column(String(60), nullable=True)
    invoice_prefix: Mapped[str] = mapped_column(String(10), default="")
    invoice_seq_padding: Mapped[int] = mapped_column(Integer, default=4)
    invoice_start_seq: Mapped[int] = mapped_column(Integer, default=1)
    per_type_sequences: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_conditions: Mapped[str] = mapped_column(String(80), default="Pronto")
    invoice_footer: Mapped[str | None] = mapped_column(Text, nullable=True)
    show_bank_details: Mapped[bool] = mapped_column(Boolean, default=True)
    show_logo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Add missing imports to models.py: `Boolean, ForeignKey, Integer, Text` (check what's already imported from sqlalchemy and add only missing ones).

**schemas.py** — append two new schemas:

```python
from uuid import UUID as UUIDType

class TenantDocumentProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUIDType
    tenant_id: UUIDType
    logo_file_id: UUIDType | None = None
    legal_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    province: str | None = None
    country: str = "Moçambique"
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bank_nib: str | None = None
    invoice_prefix: str = ""
    invoice_seq_padding: int = 4
    invoice_start_seq: int = 1
    per_type_sequences: bool = False
    payment_conditions: str = "Pronto"
    invoice_footer: str | None = None
    show_bank_details: bool = True
    show_logo: bool = True
    created_at: datetime
    updated_at: datetime

class TenantDocumentProfileUpdate(BaseModel):
    logo_file_id: UUIDType | None = None
    legal_name: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    bank_name: str | None = None
    bank_account: str | None = None
    bank_nib: str | None = None
    invoice_prefix: str | None = None
    invoice_seq_padding: int | None = None
    invoice_start_seq: int | None = None
    per_type_sequences: bool | None = None
    payment_conditions: str | None = None
    invoice_footer: str | None = None
    show_bank_details: bool | None = None
    show_logo: bool | None = None
```

**service.py** — add two functions after `_require_active_tenant`:

```python
from sqlalchemy import select
from app.modules.tenants.models import TenantDocumentProfile

def _serialize_document_profile(p: TenantDocumentProfile) -> dict:
    return {
        "id": p.id, "tenant_id": p.tenant_id, "logo_file_id": p.logo_file_id,
        "legal_name": p.legal_name, "address_line1": p.address_line1,
        "address_line2": p.address_line2, "city": p.city, "province": p.province,
        "country": p.country, "phone": p.phone, "email": p.email, "website": p.website,
        "bank_name": p.bank_name, "bank_account": p.bank_account, "bank_nib": p.bank_nib,
        "invoice_prefix": p.invoice_prefix, "invoice_seq_padding": p.invoice_seq_padding,
        "invoice_start_seq": p.invoice_start_seq, "per_type_sequences": p.per_type_sequences,
        "payment_conditions": p.payment_conditions, "invoice_footer": p.invoice_footer,
        "show_bank_details": p.show_bank_details, "show_logo": p.show_logo,
        "created_at": p.created_at, "updated_at": p.updated_at,
    }

async def get_document_profile(db: AsyncSession, tenant_id: UUID) -> dict | None:
    profile = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == tenant_id)
    )
    return _serialize_document_profile(profile) if profile else None

async def upsert_document_profile(
    db: AsyncSession, tenant_id: UUID, data: dict, *, actor_id: UUID | None = None
) -> dict:
    profile = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == tenant_id)
    )
    if profile is None:
        profile = TenantDocumentProfile(tenant_id=tenant_id)
        db.add(profile)
    for field, value in data.items():
        if value is not None or field in data:
            setattr(profile, field, value)
    await db.flush()
    await db.refresh(profile)
    await db.commit()
    await db.refresh(profile)
    return _serialize_document_profile(profile)
```

Note: `select` is already imported in service.py but import `TenantDocumentProfile` at top of service.py.

**router.py** — add two routes after the existing `/me/limits` route:

```python
from app.modules.tenants.schemas import TenantDocumentProfileUpdate

@router.get("/me/document-profile")
async def get_my_document_profile(
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    result = await service.get_document_profile(db, principal.tenant_id)
    return result or {}

@router.put("/me/document-profile")
async def put_my_document_profile(
    payload: TenantDocumentProfileUpdate,
    principal: Annotated[Principal, Depends(require_permission(ADMIN_USERS))],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    # Only owner/admin — ADMIN_USERS covers this per existing pattern
    data = payload.model_dump(exclude_unset=True)
    return await service.upsert_document_profile(
        db, principal.tenant_id, data, actor_id=principal.user_id
    )
```

Note: `ADMIN_USERS` already enforces owner/admin only (same as /me/limits). Import `TenantDocumentProfileUpdate` at top of router.py where schemas imports are.

Also add `TenantDocumentProfile` to the MODEL_MODULES list in `backend/app/database.py` if there is a `MODEL_MODULES` or `import_all_models` function that lists tenant models — check database.py and add `"app.modules.tenants.models"` only if it's not already there (it should be).
  </action>
  <verify>
    <automated>cd /c/Users/Quive/OneDrive/Documents/Rotas/backend && python -c "from app.modules.tenants.models import TenantDocumentProfile; from app.modules.tenants.service import get_document_profile, upsert_document_profile; print('OK')"</automated>
  </verify>
  <done>TenantDocumentProfile importable; GET/PUT /me/document-profile routes registered in router; ruff check passes on tenants/ module</done>
</task>

<task type="auto">
  <name>Task 3: billing/service.py — configurable invoice numbering + profile snapshot on create_document</name>
  <files>
    backend/app/modules/billing/service.py
    backend/app/modules/billing/models.py
  </files>
  <action>
**Step A — Update BillingDocument model** (`billing/models.py`):

Add 8 new columns to BillingDocument class (matching Migration B):
```python
issuer_address: Mapped[str | None] = mapped_column(Text, nullable=True)
issuer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
issuer_email: Mapped[str | None] = mapped_column(String(120), nullable=True)
issuer_city: Mapped[str | None] = mapped_column(String(80), nullable=True)
issuer_bank_details: Mapped[str | None] = mapped_column(Text, nullable=True)
payment_conditions: Mapped[str | None] = mapped_column(String(80), nullable=True)
commercial_discount: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
financial_discount: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
```

**Step B — Update `_assign_invoice_number`** in `billing/service.py`:

Replace the function body with profile-aware version. Add import at top:
```python
from app.modules.tenants.models import TenantDocumentProfile
```

New function:
```python
async def _assign_invoice_number(
    db: AsyncSession,
    document: "BillingDocument",
    tenant_id: UUID,
) -> str:
    """Assign sequential invoice number using per-tenant profile settings.

    Falls back to YYYY/NNNN (prefix="", padding=4) when no profile exists —
    preserving the format used by all existing documents.
    """
    if document.invoice_number:
        return document.invoice_number

    year = datetime.now(UTC).year
    tid_clean = str(tenant_id).replace("-", "")

    # Load profile for configurable numbering; None = use defaults
    profile = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == tenant_id)
    )
    prefix = (profile.invoice_prefix or "").strip() if profile else ""
    padding = profile.invoice_seq_padding if profile else 4
    start_seq = profile.invoice_start_seq if profile else 1
    per_type = profile.per_type_sequences if profile else False

    if per_type and document.document_type:
        seq_name = f"invoice_seq_{tid_clean}_{year}_{document.document_type}"
    else:
        seq_name = f"invoice_seq_{tid_clean}_{year}"

    await db.execute(
        text(
            f'CREATE SEQUENCE IF NOT EXISTS "{seq_name}" '
            f"START {start_seq} INCREMENT 1 NO MINVALUE NO MAXVALUE CACHE 1"
        )
    )
    result = await db.execute(text(f"SELECT nextval('{seq_name}')"))
    seq_val = result.scalar_one()

    if prefix:
        invoice_number = f"{prefix} {year}/{seq_val:0{padding}d}"
    else:
        invoice_number = f"{year}/{seq_val:0{padding}d}"

    document.invoice_number = invoice_number
    return invoice_number
```

**Step C — Add `_format_address` helper** and **`_snapshot_profile`** to service.py:

```python
def _format_address(profile: "TenantDocumentProfile") -> str:
    parts = [p for p in [profile.address_line1, profile.address_line2] if p]
    if profile.city:
        city_part = profile.city
        if profile.country:
            city_part = f"{city_part} — {profile.country}"
        parts.append(city_part)
    return ", ".join(parts) if parts else ""

async def _snapshot_profile(db: AsyncSession, document: "BillingDocument", tenant_id: UUID) -> None:
    """Copy TenantDocumentProfile fields into BillingDocument snapshot columns at creation time."""
    profile = await db.scalar(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == tenant_id)
    )
    if not profile:
        return
    document.issuer_address = _format_address(profile) or None
    document.issuer_phone = profile.phone
    document.issuer_email = profile.email
    document.issuer_city = profile.city
    document.payment_conditions = profile.payment_conditions
    if profile.show_bank_details and profile.bank_name:
        legal = profile.legal_name or document.issuer_name or "—"
        document.issuer_bank_details = (
            f"Banco {profile.bank_name} | Titular: {legal} "
            f"| Conta: {profile.bank_account or '—'} | NIB: {profile.bank_nib or '—'}"
        )
```

**Step D — Call `_snapshot_profile` in `create_document`**:

In the `create_document` function, after `db.add(document)` and `await db.flush()` (line ~482), add:
```python
    await _snapshot_profile(db, document, tenant_id)
```

Also call `_snapshot_profile` in `create_debit_note`, `create_credit_note`, and `create_invoice_receipt` (FDOC functions) if they exist in service.py — search for those functions and add the same snapshot call after `db.add(document); await db.flush()`.

Ensure `TenantDocumentProfile` is imported at top of billing/service.py (add to existing tenant model import line).
  </action>
  <verify>
    <automated>cd /c/Users/Quive/OneDrive/Documents/Rotas/backend && python -c "from app.modules.billing.service import _assign_invoice_number, _snapshot_profile, _format_address; from app.modules.billing.models import BillingDocument; print('OK')"</automated>
  </verify>
  <done>_assign_invoice_number uses profile settings with fallback; _snapshot_profile sets issuer_address/bank_details/payment_conditions; BillingDocument has 8 new mapped columns; ruff check passes</done>
</task>

<task type="auto">
  <name>Task 4: Redesign exporters.py PDF to PHC reference layout</name>
  <files>
    backend/app/modules/billing/exporters.py
  </files>
  <action>
Replace `_RotasPDF` class and `_render_pdf` function entirely. Keep unchanged: `ExportArtifact` dataclass, `render_billing_export`, `_money`, `_money_val`, `_date`, `_status_label`, `_doc_type_label`, `_render_xlsx`, all XLSX helpers, color constants, font constants.

**New `_RotasPDF` class** — A4 portrait, margins 15mm, header/footer only:

```python
class _RotasPDF(FPDF):
    """FPDF2 subclass — PHC-style header/footer. Body rendered in _render_pdf."""

    def __init__(self, total_pages_ref: list[int]):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._total_pages_ref = total_pages_ref  # mutated after rendering
        self.add_font("DejaVu", "", str(FONTS_DIR / "DejaVuSans.ttf"))
        self.add_font("DejaVu", "B", str(FONTS_DIR / "DejaVuSans-Bold.ttf"))
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=15, top=15, right=15)

    def header(self):
        # Header is rendered manually in _render_pdf on first page.
        # On continuation pages, add a minimal top-rule.
        if self.page_no() > 1:
            self.set_draw_color(*_LINE)
            self.set_line_width(0.3)
            self.line(15, 15, 195, 15)
            self.set_y(18)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*_LINE)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_y(-12)
        self.set_font("DejaVu", "", 7)
        self.set_text_color(*_MUTED)
        self.cell(80, 5, "Documento Processado por Computador", align="L")
        self.set_font("DejaVu", "B", 7)
        self.cell(50, 5, "ROTAS", align="C")
        self.set_font("DejaVu", "", 7)
        total = self._total_pages_ref[0] if self._total_pages_ref else "?"
        self.cell(0, 5, f"Página {self.page_no()} de {total}", align="R")
```

**New `_render_pdf` function** — full PHC layout:

```python
def _render_pdf(
    document: BillingDocument,
    items: list[BillingItem],
    *,
    issuer_name: str = "ROTAS",
    issuer_contact: str | None = None,
) -> ExportArtifact:
    currency = document.currency or "MZN"
    doc_number = document.invoice_number or str(document.id)[:8].upper()
    issue_date = _date(document.issued_at or document.created_at)
    doc_label = _doc_type_label(document)

    # Compute totals
    if document.iva_rate is None:
        raise ValueError("iva_rate is NULL on issued document — cannot render export")
    iva_rate = float(document.iva_rate)
    iva_pct = int(iva_rate * 100)
    subtotal = _money_val(document.subtotal)
    tax_amount = _money_val(document.tax_amount)
    total_amount = _money_val(document.total_amount) if document.total_amount else subtotal + tax_amount
    commercial_disc = _money_val(getattr(document, "commercial_discount", None) or 0)
    financial_disc = _money_val(getattr(document, "financial_discount", None) or 0)

    total_pages_ref = [1]
    pdf = _RotasPDF(total_pages_ref)
    pdf.add_page()

    # ── HEADER: 2-column layout ───────────────────────────────────────────────
    # Left column (110mm): issuer identity
    # Right column (70mm): client box with border

    LEFT_W = 110.0
    RIGHT_W = 70.0
    header_y_start = pdf.get_y()

    # --- Left: Logo (optional) + issuer text ---
    x_left = 15.0
    pdf.set_xy(x_left, header_y_start)

    # Try to load logo
    logo_loaded = False
    logo_file_id = getattr(document, "logo_file_id", None)
    # Logo loading: only attempted if logo_file_id exists on document (future extension)
    # For now skip — logo_file_id is not yet on BillingDocument model
    # When available: try: pdf.image(logo_path, x=x_left, y=header_y_start, w=25, h=25); logo_loaded=True; except: pass

    logo_h = 0
    if logo_loaded:
        logo_h = 26

    text_y = header_y_start + logo_h
    pdf.set_xy(x_left, text_y)
    pdf.set_font("DejaVu", "B", 12)
    pdf.set_text_color(*_INK)
    issuer_display = getattr(document, "issuer_name", None) or issuer_name
    pdf.cell(LEFT_W, 6, issuer_display, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    issuer_nuit = getattr(document, "issuer_nuit", None)
    if issuer_nuit:
        pdf.set_xy(x_left, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(LEFT_W, 5, f"NUIT: {issuer_nuit}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    issuer_address = getattr(document, "issuer_address", None)
    if issuer_address:
        pdf.set_xy(x_left, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(LEFT_W, 4, issuer_address, align="L")

    issuer_phone = getattr(document, "issuer_phone", None)
    issuer_email = getattr(document, "issuer_email", None)
    contact_parts = [p for p in [issuer_phone, issuer_email] if p]
    if contact_parts:
        pdf.set_xy(x_left, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(LEFT_W, 4, "  |  ".join(contact_parts), align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    issuer_bottom = pdf.get_y()

    # --- Right: Client info box with border ---
    x_right = 15.0 + LEFT_W
    box_y = header_y_start
    box_h = 34.0  # fixed height box

    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.4)
    pdf.rect(x_right, box_y, RIGHT_W, box_h)

    pdf.set_xy(x_right + 3, box_y + 3)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    client_name = document.client_name or "—"
    pdf.cell(RIGHT_W - 6, 5, client_name[:40], align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Client NUIT
    client_nuit = getattr(document, "client_nuit", None)
    if isinstance(client_nuit, str) and client_nuit:
        pdf.set_xy(x_right + 3, pdf.get_y())
        pdf.set_font("DejaVu", "", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(RIGHT_W - 6, 4, f"NUIT: {client_nuit}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    header_bottom = max(issuer_bottom, box_y + box_h) + 4
    pdf.set_y(header_bottom)

    # ── METADATA BAR ─────────────────────────────────────────────────────────
    # Horizontal band with light grey fill
    bar_y = pdf.get_y()
    bar_h = 10.0
    pdf.set_fill_color(240, 242, 245)
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.rect(15, bar_y, 180, bar_h, "FD")

    # Left side: metadata cells
    pdf.set_xy(17, bar_y + 2)
    pdf.set_font("DejaVu", "", 7)
    pdf.set_text_color(*_MUTED)

    payment_conds = getattr(document, "payment_conditions", None) or "—"
    due = _date(document.due_date) if isinstance(document.due_date, datetime) else "—"
    meta_str = f"Data: {issue_date}  |  Vencimento: {due}  |  Condições: {payment_conds}  |  Moeda: {currency}"
    pdf.cell(110, 6, meta_str, align="L")

    # Right side: document number bold and prominent
    pdf.set_xy(125, bar_y + 1.5)
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    display_doc = f"{doc_label} N.º {doc_number} ORIGINAL"
    pdf.cell(68, 7, display_doc, align="R")

    pdf.set_y(bar_y + bar_h + 4)

    # ── ITEMS TABLE ───────────────────────────────────────────────────────────
    USABLE = 180.0
    # Cols: Ref | Designação | Quant | Pr.Unit | IVA% | Total
    COL_W_RAW = [20, 72, 14, 28, 14, 32]
    scale = USABLE / sum(COL_W_RAW)
    COL_W = [round(w * scale, 1) for w in COL_W_RAW]
    HEADERS_T = ["Referência", "Designação", "Quant.", "Pr.Unitário", "IVA%", f"Total {currency}"]
    ALIGNS_T = ["C", "L", "C", "R", "C", "R"]

    # Header row
    pdf.set_fill_color(*_NAV)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("DejaVu", "B", 7.5)
    for w, label, align in zip(COL_W, HEADERS_T, ALIGNS_T, strict=False):
        pdf.cell(w, 7, label, border=0, fill=True, align=align, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    # Data rows
    pdf.set_font("DejaVu", "", 7.5)
    grand_total = Decimal(0)

    for idx, item in enumerate(items):
        fill = idx % 2 == 0
        pdf.set_fill_color(*(_SOFT if fill else _WHITE))
        pdf.set_text_color(*_INK)

        amount = _money_val(item.amount)
        grand_total += amount
        iva_rate_item = float(item.iva_rate or 0) if item.iva_rate is not None else iva_rate
        iva_pct_item = int(iva_rate_item * 100)

        ref_val = (item.client_reference or "—")[:14]
        origin = item.origin or ""
        dest = item.destination or ""
        desig = f"{origin} → {dest}" if (origin or dest) else "—"
        if item.cargo_description:
            desig = f"{desig}\n{item.cargo_description[:40]}"
        desig = desig[:60]

        values_row = [
            (ref_val, "C"),
            (desig[:40], "L"),
            (str(item.quantity or 1), "C"),
            (_money(item.unit_price, ""), "R"),
            (f"{iva_pct_item}%", "C"),
            (_money(amount, ""), "R"),
        ]
        row_h = 6
        for w, (text_val, align) in zip(COL_W, values_row, strict=False):
            pdf.cell(
                w, row_h, text_val, border=0, fill=fill, align=align,
                new_x=XPos.RIGHT, new_y=YPos.TOP,
            )
        pdf.ln()

    pdf.ln(3)

    # ── BANK DETAILS LINE ─────────────────────────────────────────────────────
    issuer_bank = getattr(document, "issuer_bank_details", None)
    if issuer_bank:
        pdf.set_draw_color(*_LINE)
        pdf.set_line_width(0.3)
        pdf.line(15, pdf.get_y(), 195, pdf.get_y())
        pdf.ln(2)
        pdf.set_font("DejaVu", "", 7)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(180, 4, f"Dados Bancários: {issuer_bank}", align="L")
        pdf.ln(2)

    # ── TOTALS ZONE: 2 columns side by side ───────────────────────────────────
    pdf.set_draw_color(*_LINE)
    pdf.set_line_width(0.3)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(3)

    totals_y = pdf.get_y()
    LEFT_TOT = 88.0
    RIGHT_TOT = 87.0
    GAP = 5.0
    x_left_tot = 15.0
    x_right_tot = 15.0 + LEFT_TOT + GAP

    # --- Left totals: IVA breakdown table ---
    pdf.set_xy(x_left_tot, totals_y)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_WHITE)
    pdf.set_fill_color(*_NAV)
    col3 = [LEFT_TOT / 3] * 3
    for lbl in ["Taxa", "Base de Incidência", "Valor do IVA"]:
        pdf.cell(col3[0] if lbl == "Taxa" else col3[1], 6, lbl, fill=True, align="C",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    # IVA data rows (one row per IVA rate — currently one rate per document)
    pdf.set_xy(x_left_tot, pdf.get_y())
    pdf.set_font("DejaVu", "", 7.5)
    pdf.set_text_color(*_INK)
    pdf.set_fill_color(*_SOFT)
    pdf.cell(col3[0], 5, f"{iva_pct}%", fill=True, align="C", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col3[1], 5, f"{subtotal:,.2f}", fill=True, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col3[2], 5, f"{tax_amount:,.2f}", fill=True, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # IVA total row (bold)
    iva_row_y = pdf.get_y()
    pdf.set_xy(x_left_tot, iva_row_y)
    pdf.set_font("DejaVu", "B", 7.5)
    pdf.set_text_color(*_INK)
    pdf.cell(col3[0], 6, "Total de IVA", fill=False, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col3[1], 6, f"{subtotal:,.2f}", fill=False, align="R", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(col3[2], 6, f"{tax_amount:,.2f}", fill=False, align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    left_bottom = pdf.get_y()

    # --- Right totals: Valores do Documento ---
    pdf.set_xy(x_right_tot, totals_y)
    pdf.set_font("DejaVu", "B", 8)
    pdf.set_text_color(*_WHITE)
    pdf.set_fill_color(*_NAV)
    pdf.cell(RIGHT_TOT, 6, "Valores do Documento", fill=True, align="C",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def _right_row(label: str, value: Decimal, bold: bool = False):
        pdf.set_xy(x_right_tot, pdf.get_y())
        lw = RIGHT_TOT * 0.65
        vw = RIGHT_TOT * 0.35
        pdf.set_font("DejaVu", "B" if bold else "", 8)
        pdf.set_text_color(*_INK)
        pdf.cell(lw, 5, label, align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.cell(vw, 5, f"{value:,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    _right_row("Total antes de descontos:", subtotal + tax_amount)
    disc_pct = int(float(commercial_disc / (subtotal or Decimal(1))) * 100) if commercial_disc else 0
    _right_row(f"Desconto Comercial {disc_pct}%:", commercial_disc)
    _right_row("Desconto Financeiro:", financial_disc)
    _right_row("Total de IVA:", tax_amount)

    # TOTAL line — bold, larger
    pdf.set_xy(x_right_tot, pdf.get_y() + 1)
    pdf.set_draw_color(*_LINE)
    pdf.line(x_right_tot, pdf.get_y(), x_right_tot + RIGHT_TOT, pdf.get_y())
    pdf.ln(1)
    pdf.set_xy(x_right_tot, pdf.get_y())
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(*_INK)
    lw = RIGHT_TOT * 0.55
    vw = RIGHT_TOT * 0.45
    pdf.cell(lw, 7, f"TOTAL ({currency}):", align="L", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(vw, 7, f"{total_amount:,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    right_bottom = pdf.get_y()

    pdf.set_y(max(left_bottom, right_bottom) + 4)

    # Optional invoice_footer from profile (future: stored on document)
    # Not stored on BillingDocument yet — skip for now

    # Patch total page count
    total_pages_ref[0] = pdf.pages
    filename = f"fatura_{document.invoice_number or str(document.id)[:8]}.pdf"
    return ExportArtifact(filename=filename, content_type="application/pdf", content=pdf.output())
```

Key compatibility constraints to verify before writing:
- `render_billing_export` function signature UNCHANGED
- The `if document.iva_rate is None: raise ValueError(...)` check PRESERVED in new _render_pdf
- `_doc_type_label` function UNCHANGED
- `_render_xlsx` function and XLSX helpers UNCHANGED
- `ExportArtifact` dataclass UNCHANGED
- The `datetime` import must be present (already in file)
- `XPos` and `YPos` from `fpdf.enums` already imported
  </action>
  <verify>
    <automated>cd /c/Users/Quive/OneDrive/Documents/Rotas/backend && python -c "
from unittest.mock import MagicMock
from decimal import Decimal
from datetime import datetime
from app.modules.billing.exporters import render_billing_export, ExportArtifact

doc = MagicMock()
doc.invoice_number = '2026/0001'
doc.issued_at = datetime(2026, 6, 20)
doc.created_at = datetime(2026, 6, 20)
doc.billing_period_start = datetime(2026, 6, 1)
doc.billing_period_end = datetime(2026, 6, 30)
doc.currency = 'MZN'
doc.status = 'issued'
doc.document_type = 'invoice'
doc.client_name = 'TSM Engineering Lda'
doc.client_nuit = '400123456'
doc.contract_reference = 'CTR-001'
doc.subtotal = Decimal('10000.00')
doc.tax_amount = Decimal('1600.00')
doc.total_amount = Decimal('11600.00')
doc.iva_rate = Decimal('0.1600')
doc.due_date = datetime(2026, 7, 20)
doc.issuer_name = 'ROTAS Transportes'
doc.issuer_nuit = '400000001'
doc.issuer_address = 'Av. Julius Nyerere, 123, Maputo — Moçambique'
doc.issuer_phone = '+258 84 000 0000'
doc.issuer_email = 'faturas@rotas.co.mz'
doc.issuer_bank_details = 'Banco BCI | Titular: ROTAS | Conta: 12345678 | NIB: 000300000123456789'
doc.payment_conditions = '30 dias'
doc.commercial_discount = Decimal('0')
doc.financial_discount = Decimal('0')

item = MagicMock()
item.client_reference = 'REF-001'
item.origin = 'Maputo'
item.destination = 'Beira'
item.cargo_description = 'Cimento'
item.quantity = Decimal('1')
item.unit_price = Decimal('10000.00')
item.amount = Decimal('10000.00')
item.iva_rate = Decimal('0.1600')
item.delivered_at = datetime(2026, 6, 15)

result = render_billing_export(doc, [item], 'pdf')
assert isinstance(result, ExportArtifact)
assert result.content_type == 'application/pdf'
assert len(result.content) > 1000
print('PDF render OK, size:', len(result.content))
"</automated>
  </verify>
  <done>render_billing_export returns valid PDF bytes with PHC layout; MagicMock smoke test passes; ruff check on exporters.py passes with 0 errors</done>
</task>

</tasks>

<verification>
After all 4 tasks complete:

1. `python -c "from app.modules.tenants.models import TenantDocumentProfile; print('model OK')"` — no ImportError
2. `python -c "from app.modules.billing.service import _snapshot_profile, _assign_invoice_number; print('service OK')"` — no ImportError
3. `ruff check backend/app/modules/tenants/ backend/app/modules/billing/` — 0 errors (warnings acceptable)
4. PDF smoke test (Task 4 verify command) — returns ExportArtifact with PDF bytes
5. Alembic script parse: `python -c "from alembic.script import ScriptDirectory; from alembic.config import Config; c=Config('alembic.ini'); s=ScriptDirectory.from_config(c); print(list(s.walk_revisions())[:3])"` — no syntax errors in new migrations
</verification>

<success_criteria>
- tenant_document_profiles table definida com RLS + GRANT obrigatórios (v2.0 Migration Rules)
- BillingDocument tem 8 novas colunas de snapshot (Migration B)
- GET/PUT /api/v1/tenants/me/document-profile funcionais (owner/admin only)
- _assign_invoice_number usa invoice_prefix e invoice_seq_padding do perfil; fallback YYYY/NNNN quando sem perfil
- create_document chama _snapshot_profile após db.flush()
- PDF renderiza layout PHC: header 2 colunas, barra metadados com doc number em destaque, tabela 6 colunas, linha dados bancários, totais em 2 colunas side-by-side
- Assinatura render_billing_export inalterada; iva_rate=None continua a levantar ValueError
- XLSX não é alterado
</success_criteria>

<output>
After completion, create `.planning/quick/260620-sik-tenant-document-profiles-redesenho-expor/260620-sik-SUMMARY.md` with:
- What was implemented
- New columns added to BillingDocument
- New endpoints registered
- Alembic migration IDs: a3b4c5d6e7f8 + c5d6e7f8a9b0
- Any deviations from the plan
</output>
