"""add_spare_part_movements

Revision ID: d64f8bac537e
Revises: c53e7a9b426d
Create Date: 2026-06-02 12:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "d64f8bac537e"
down_revision: str | None = "c53e7a9b426d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "spare_parts_inventory",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("unit", sa.String(length=30), nullable=False),
        sa.Column("current_quantity", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("average_unit_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("current_quantity >= 0", name="chk_spare_parts_current_quantity"),
        sa.CheckConstraint("minimum_quantity >= 0", name="chk_spare_parts_minimum_quantity"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="chk_spare_parts_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_spare_parts_inventory_tenant_sku"),
    )
    op.create_index("ix_spare_parts_inventory_tenant_id", "spare_parts_inventory", ["tenant_id"])
    op.create_index("ix_spare_parts_inventory_sku", "spare_parts_inventory", ["sku"])
    op.create_index("ix_spare_parts_inventory_status", "spare_parts_inventory", ["status"])

    op.create_table(
        "spare_part_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("inventory_id", sa.UUID(), nullable=False),
        sa.Column("movement_type", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("balance_after_quantity", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("request_reference", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("direction IN ('in', 'out')", name="chk_spare_part_movements_direction"),
        sa.CheckConstraint("quantity > 0", name="chk_spare_part_movements_quantity"),
        sa.CheckConstraint("balance_after_quantity >= 0", name="chk_spare_part_movements_balance"),
        sa.ForeignKeyConstraint(["inventory_id"], ["spare_parts_inventory.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_spare_part_movements_tenant_request_reference",
        ),
    )
    op.create_index("ix_spare_part_movements_tenant_id", "spare_part_movements", ["tenant_id"])
    op.create_index("ix_spare_part_movements_inventory_id", "spare_part_movements", ["inventory_id"])
    op.create_index("ix_spare_part_movements_movement_type", "spare_part_movements", ["movement_type"])
    op.create_index("ix_spare_part_movements_direction", "spare_part_movements", ["direction"])
    op.create_index("ix_spare_part_movements_request_reference", "spare_part_movements", ["request_reference"])
    op.create_index("ix_spare_part_movements_source_type", "spare_part_movements", ["source_type"])
    op.create_index("ix_spare_part_movements_source_id", "spare_part_movements", ["source_id"])
    op.create_index("ix_spare_part_movements_occurred_at", "spare_part_movements", ["occurred_at"])

    op.create_table(
        "maintenance_parts_used",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=False),
        sa.Column("inventory_id", sa.UUID(), nullable=False),
        sa.Column("movement_id", sa.UUID(), nullable=True),
        sa.Column("request_reference", sa.String(length=120), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("issued_by", sa.UUID(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["inventory_id"], ["spare_parts_inventory.id"]),
        sa.ForeignKeyConstraint(["movement_id"], ["spare_part_movements.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_maintenance_parts_used_tenant_request_reference",
        ),
    )
    op.create_index("ix_maintenance_parts_used_tenant_id", "maintenance_parts_used", ["tenant_id"])
    op.create_index("ix_maintenance_parts_used_work_order_id", "maintenance_parts_used", ["work_order_id"])
    op.create_index("ix_maintenance_parts_used_inventory_id", "maintenance_parts_used", ["inventory_id"])
    op.create_index("ix_maintenance_parts_used_movement_id", "maintenance_parts_used", ["movement_id"])
    op.create_index("ix_maintenance_parts_used_request_reference", "maintenance_parts_used", ["request_reference"])


def downgrade() -> None:
    op.drop_table("maintenance_parts_used")
    op.drop_table("spare_part_movements")
    op.drop_table("spare_parts_inventory")
