"""add iva_basis to billing_documents and billing_items

Revision ID: iva01a1b2c3d4
Revises: fisc01
Create Date: 2026-06-21

No RLS changes needed — these are new columns on existing RLS-protected tables.
RLS policies filter rows, not columns.
"""

import sqlalchemy as sa

from alembic import op

revision = "iva01a1b2c3d4"
down_revision = "fisc01"
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
