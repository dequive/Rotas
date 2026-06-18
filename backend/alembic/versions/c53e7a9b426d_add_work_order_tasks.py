"""add_work_order_tasks

Revision ID: c53e7a9b426d
Revises: b42d6f8a315c
Create Date: 2026-06-02 11:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c53e7a9b426d"
down_revision: str | None = "b42d6f8a315c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_order_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("completed_by", sa.UUID(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'cancelled')",
            name="chk_work_order_tasks_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_order_tasks_tenant_id", "work_order_tasks", ["tenant_id"])
    op.create_index("ix_work_order_tasks_work_order_id", "work_order_tasks", ["work_order_id"])
    op.create_index("ix_work_order_tasks_status", "work_order_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("work_order_tasks")
