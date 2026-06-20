"""add_supplier_ledger_entries

Revision ID: tp08
Revises: tp07
Branch_labels: None
Depends_on: None
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "tp08"
down_revision = "tp07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_ledger_entries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("entry_type", sa.String(10), nullable=False),  # 'debit' | 'credit'
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        # source_type values: manual_payment | fuel_purchase | work_order | invoice | adjustment
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("entry_type IN ('debit', 'credit')", name="ck_sle_entry_type"),
        sa.CheckConstraint("amount > 0", name="ck_sle_amount_positive"),
    )
    op.create_index(
        "ix_sle_tenant_party",
        "supplier_ledger_entries",
        ["tenant_id", "third_party_id"],
    )
    op.create_index(
        "ix_sle_entry_date",
        "supplier_ledger_entries",
        ["tenant_id", "entry_date"],
    )

    # v2.0 RLS rules
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON supplier_ledger_entries TO rotas_app")
    op.execute("ALTER TABLE supplier_ledger_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE supplier_ledger_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON supplier_ledger_entries
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON supplier_ledger_entries")
    op.drop_index("ix_sle_entry_date", table_name="supplier_ledger_entries")
    op.drop_index("ix_sle_tenant_party", table_name="supplier_ledger_entries")
    op.drop_table("supplier_ledger_entries")
