"""fiscal_counter_gap_free

Revision ID: fisc01
Revises: b8a041cfa791
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "fisc01"
down_revision: str | None = "b8a041cfa791"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── fiscal_counters ───────────────────────────────────────────────────────
    op.create_table(
        "fiscal_counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("doc_type", sa.String(30), nullable=False, server_default=""),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "fiscal_year", "doc_type", name="uq_fiscal_counter_key"),
    )

    op.execute("ALTER TABLE fiscal_counters ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE fiscal_counters FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_fiscal_counters ON fiscal_counters "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON fiscal_counters TO rotas_app")

    # ── widen invoice_number columns from String(12) → String(30) ─────────────
    op.alter_column(
        "billing_documents",
        "invoice_number",
        existing_type=sa.String(12),
        type_=sa.String(30),
        existing_nullable=True,
    )
    op.alter_column(
        "billing_documents",
        "parent_invoice_number",
        existing_type=sa.String(12),
        type_=sa.String(30),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "billing_documents",
        "parent_invoice_number",
        existing_type=sa.String(30),
        type_=sa.String(12),
        existing_nullable=True,
    )
    op.alter_column(
        "billing_documents",
        "invoice_number",
        existing_type=sa.String(30),
        type_=sa.String(12),
        existing_nullable=True,
    )
    op.execute("DROP POLICY IF EXISTS rls_fiscal_counters ON fiscal_counters")
    op.drop_table("fiscal_counters")
