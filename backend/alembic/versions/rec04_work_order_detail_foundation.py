"""Add work-order detail, QC and net-parts accounting fields.

Revision ID: rec04
Revises: rec03
Create Date: 2026-07-22 23:30:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rec04"
down_revision: str | None = "rec03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def upgrade() -> None:
    _add_column_if_missing("work_orders", sa.Column("quality_checked_by", sa.UUID(), nullable=True))
    _add_column_if_missing(
        "work_orders", sa.Column("quality_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    _add_column_if_missing("work_orders", sa.Column("quality_notes", sa.Text(), nullable=True))
    _add_column_if_missing(
        "work_orders",
        sa.Column("billing_status", sa.String(length=30), server_default="not_required", nullable=False),
    )
    _add_column_if_missing(
        "work_orders", sa.Column("billing_document_id", sa.UUID(), nullable=True)
    )
    _add_column_if_missing("work_orders", sa.Column("billing_error", sa.Text(), nullable=True))

    op.execute("UPDATE work_orders SET billing_status = 'not_required' WHERE billing_status IS NULL")
    op.alter_column(
        "work_orders",
        "billing_status",
        existing_type=sa.String(length=30),
        nullable=False,
        server_default="not_required",
    )

    work_order_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("work_orders")}
    if "ix_work_orders_billing_status" not in work_order_indexes:
        op.create_index("ix_work_orders_billing_status", "work_orders", ["billing_status"])
    if "ix_work_orders_billing_document_id" not in work_order_indexes:
        op.create_index("ix_work_orders_billing_document_id", "work_orders", ["billing_document_id"])

    billing_document_fk_exists = any(
        foreign_key.get("constrained_columns") == ["billing_document_id"]
        for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys("work_orders")
    )
    if not billing_document_fk_exists:
        op.create_foreign_key(
            "fk_work_orders_billing_document_id",
            "work_orders",
            "billing_documents",
            ["billing_document_id"],
            ["id"],
            ondelete="SET NULL",
        )

    _add_column_if_missing(
        "maintenance_parts_used",
        sa.Column("returned_quantity", sa.Numeric(15, 3), server_default="0", nullable=False),
    )
    _add_column_if_missing(
        "maintenance_parts_used",
        sa.Column("net_total_cost", sa.Numeric(16, 2), nullable=True),
    )
    op.execute(
        "UPDATE maintenance_parts_used SET returned_quantity = 0 WHERE returned_quantity IS NULL"
    )
    op.alter_column(
        "maintenance_parts_used",
        "returned_quantity",
        existing_type=sa.Numeric(15, 3),
        nullable=False,
        server_default="0",
    )
    op.execute(
        "UPDATE maintenance_parts_used SET net_total_cost = COALESCE(total_cost, 0) "
        "WHERE net_total_cost IS NULL"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE maintenance_parts_used DROP COLUMN IF EXISTS net_total_cost")
    op.execute("ALTER TABLE maintenance_parts_used DROP COLUMN IF EXISTS returned_quantity")
    op.execute(
        "ALTER TABLE work_orders DROP CONSTRAINT IF EXISTS fk_work_orders_billing_document_id"
    )
    op.execute("DROP INDEX IF EXISTS ix_work_orders_billing_document_id")
    op.execute("DROP INDEX IF EXISTS ix_work_orders_billing_status")
    op.execute("ALTER TABLE work_orders DROP COLUMN IF EXISTS billing_error")
    op.execute("ALTER TABLE work_orders DROP COLUMN IF EXISTS billing_document_id")
    op.execute("ALTER TABLE work_orders DROP COLUMN IF EXISTS billing_status")
    op.execute("ALTER TABLE work_orders DROP COLUMN IF EXISTS quality_notes")
    op.execute("ALTER TABLE work_orders DROP COLUMN IF EXISTS quality_checked_at")
    op.execute("ALTER TABLE work_orders DROP COLUMN IF EXISTS quality_checked_by")
