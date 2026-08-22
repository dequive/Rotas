"""Ensure supplier payments are linked to their source invoice.

Revision ID: rec10
Revises: rec09
Create Date: 2026-07-26 00:30:00+02:00

Some legacy databases created ``supplier_payments`` from an older ORM snapshot
without ``invoice_id`` while their Alembic history later advanced to head.
This reconciliation is additive and safe on both those databases and canonical
databases where the column, index, and foreign key already exist.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "rec10"
down_revision: str | None = "rec09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"] for column in inspector.get_columns("supplier_payments")
    }
    if "invoice_id" not in columns:
        op.add_column(
            "supplier_payments",
            sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=True),
        )

    inspector = sa.inspect(op.get_bind())
    indexes = {
        index["name"] for index in inspector.get_indexes("supplier_payments")
    }
    if "ix_supplier_payments_invoice_id" not in indexes:
        op.create_index(
            "ix_supplier_payments_invoice_id",
            "supplier_payments",
            ["invoice_id"],
        )

    foreign_keys = inspector.get_foreign_keys("supplier_payments")
    if not any(
        foreign_key["constrained_columns"] == ["invoice_id"]
        and foreign_key["referred_table"] == "supplier_invoices"
        for foreign_key in foreign_keys
    ):
        op.create_foreign_key(
            "fk_supplier_payments_invoice_id_supplier_invoices",
            "supplier_payments",
            "supplier_invoices",
            ["invoice_id"],
            ["id"],
        )


def downgrade() -> None:
    # Reconciliation migrations do not destructively remove a column that may
    # have predated this revision on canonical databases.
    pass
