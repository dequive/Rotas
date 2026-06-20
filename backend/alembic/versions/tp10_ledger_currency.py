"""add_currency_to_supplier_ledger_entries

Revision ID: tp10
Revises: b4f2c9d8a1e6
Branch_labels: None
Depends_on: None
"""

import sqlalchemy as sa

from alembic import op

revision = "tp10"
down_revision = "b4f2c9d8a1e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "supplier_ledger_entries",
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="MZN",
        ),
    )
    op.create_check_constraint(
        "ck_sle_currency",
        "supplier_ledger_entries",
        "currency IN ('MZN', 'USD', 'ZAR', 'EUR')",
    )
    op.create_index(
        "ix_sle_currency",
        "supplier_ledger_entries",
        ["tenant_id", "third_party_id", "currency"],
    )


def downgrade() -> None:
    op.drop_index("ix_sle_currency", table_name="supplier_ledger_entries")
    op.drop_constraint("ck_sle_currency", "supplier_ledger_entries", type_="check")
    op.drop_column("supplier_ledger_entries", "currency")
