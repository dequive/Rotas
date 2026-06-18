"""add_workshop_tool_checkouts

Revision ID: e75a9cbd648f
Revises: d64f8bac537e
Create Date: 2026-06-02 13:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e75a9cbd648f"
down_revision: str | None = "d64f8bac537e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workshop_tools",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_critical", sa.Boolean(), nullable=False),
        sa.Column("calibration_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('available', 'checked_out', 'damaged', 'lost', 'retired')",
            name="chk_workshop_tools_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_workshop_tools_tenant_code"),
    )
    op.create_index("ix_workshop_tools_tenant_id", "workshop_tools", ["tenant_id"])
    op.create_index("ix_workshop_tools_code", "workshop_tools", ["code"])
    op.create_index("ix_workshop_tools_calibration_due_at", "workshop_tools", ["calibration_due_at"])
    op.create_index("ix_workshop_tools_status", "workshop_tools", ["status"])

    op.create_table(
        "tool_checkouts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("checkout_reference", sa.String(length=120), nullable=False),
        sa.Column("checked_out_by", sa.UUID(), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("return_reference", sa.String(length=120), nullable=True),
        sa.Column("returned_by", sa.UUID(), nullable=True),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_condition", sa.String(length=30), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('checked_out', 'returned')",
            name="chk_tool_checkouts_status",
        ),
        sa.CheckConstraint(
            "return_condition IS NULL OR return_condition IN ('available', 'damaged', 'lost', 'retired')",
            name="chk_tool_checkouts_return_condition",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tool_id"], ["workshop_tools.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "checkout_reference",
            name="uq_tool_checkouts_tenant_checkout_reference",
        ),
    )
    op.create_index("ix_tool_checkouts_tenant_id", "tool_checkouts", ["tenant_id"])
    op.create_index("ix_tool_checkouts_tool_id", "tool_checkouts", ["tool_id"])
    op.create_index("ix_tool_checkouts_work_order_id", "tool_checkouts", ["work_order_id"])
    op.create_index("ix_tool_checkouts_checkout_reference", "tool_checkouts", ["checkout_reference"])
    op.create_index("ix_tool_checkouts_checked_out_at", "tool_checkouts", ["checked_out_at"])
    op.create_index("ix_tool_checkouts_due_at", "tool_checkouts", ["due_at"])
    op.create_index("ix_tool_checkouts_status", "tool_checkouts", ["status"])
    op.create_index("ix_tool_checkouts_return_reference", "tool_checkouts", ["return_reference"])
    op.create_index(
        "uq_tool_checkouts_active_tool",
        "tool_checkouts",
        ["tenant_id", "tool_id"],
        unique=True,
        postgresql_where=sa.text("status = 'checked_out'"),
    )


def downgrade() -> None:
    op.drop_table("tool_checkouts")
    op.drop_table("workshop_tools")
