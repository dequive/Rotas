"""harden_fuel_stock_controls

Revision ID: a31c5e7f204b
Revises: e9a61bd4027c
Create Date: 2026-05-31 22:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a31c5e7f204b"
down_revision: str | None = "e9a61bd4027c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_fuel_receipts_tenant_purchase_delivery_note",
        "fuel_receipts",
        ["tenant_id", "purchase_id", "delivery_note_number"],
        unique=True,
        postgresql_where=sa.text("delivery_note_number IS NOT NULL"),
    )
    op.add_column(
        "fuel_stock_counts",
        sa.Column(
            "adjustment_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "fuel_stock_counts",
        sa.Column("adjustment_movement_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "fuel_stock_counts",
        sa.Column("adjustment_approved_by", sa.UUID(), nullable=True),
    )
    op.add_column(
        "fuel_stock_counts",
        sa.Column("adjustment_approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "chk_fuel_stock_counts_adjustment_status",
        "fuel_stock_counts",
        "adjustment_status IN ('pending', 'not_required', 'approved')",
    )
    op.create_index(
        "ix_fuel_stock_counts_adjustment_status",
        "fuel_stock_counts",
        ["adjustment_status"],
    )
    op.create_foreign_key(
        "fk_fuel_stock_counts_adjustment_movement_id",
        "fuel_stock_counts",
        "fuel_movements",
        ["adjustment_movement_id"],
        ["id"],
        use_alter=True,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_fuel_stock_counts_adjustment_movement_id",
        "fuel_stock_counts",
        type_="foreignkey",
    )
    op.drop_index("ix_fuel_stock_counts_adjustment_status", table_name="fuel_stock_counts")
    op.drop_constraint(
        "chk_fuel_stock_counts_adjustment_status",
        "fuel_stock_counts",
        type_="check",
    )
    op.drop_column("fuel_stock_counts", "adjustment_approved_at")
    op.drop_column("fuel_stock_counts", "adjustment_approved_by")
    op.drop_column("fuel_stock_counts", "adjustment_movement_id")
    op.drop_column("fuel_stock_counts", "adjustment_status")
    op.drop_index(
        "uq_fuel_receipts_tenant_purchase_delivery_note",
        table_name="fuel_receipts",
    )
