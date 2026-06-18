"""add_workshop_expansion

Phase 13.5 — Workshop Operations Expansion (Wave 1: Schema)

Adds new columns to existing tables and creates three new tables:
  - workshop_staff_rates (labor cost tracking per mechanic)
  - tool_calibrations (calibration history per tool)
  - spare_part_serial_items (per-serial-number lifecycle tracking)

All three new tables include RLS ENABLE, FORCE, tenant_isolation policy,
and GRANT to rotas_app in the same migration (v2.0 mandatory rule).

Revision ID: a8f3b2c1d4e5
Revises: f4c8a12d9b30
Create Date: 2026-06-19 00:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8f3b2c1d4e5"
down_revision: str | None = "f4c8a12d9b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # ALTER TABLE — work_order_tasks: 3 new nullable columns + FK
    # -------------------------------------------------------------------------
    op.add_column("work_order_tasks", sa.Column("assigned_to", sa.UUID(), nullable=True))
    op.add_column("work_order_tasks", sa.Column("estimated_minutes", sa.Integer(), nullable=True))
    op.add_column("work_order_tasks", sa.Column("actual_minutes", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_work_order_tasks_assigned_to_users",
        "work_order_tasks",
        "users",
        ["assigned_to"],
        ["id"],
        ondelete="SET NULL",
    )

    # -------------------------------------------------------------------------
    # ALTER TABLE — work_orders: labor_cost column (NOT NULL with DEFAULT 0)
    # -------------------------------------------------------------------------
    op.add_column(
        "work_orders",
        sa.Column(
            "labor_cost",
            sa.Numeric(precision=14, scale=2),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    # -------------------------------------------------------------------------
    # ALTER TABLE — workshop_tools: 6 new nullable columns
    # -------------------------------------------------------------------------
    op.add_column("workshop_tools", sa.Column("category", sa.String(40), nullable=True))
    op.add_column("workshop_tools", sa.Column("location", sa.String(120), nullable=True))
    op.add_column("workshop_tools", sa.Column("serial_number", sa.String(80), nullable=True))
    op.add_column("workshop_tools", sa.Column("purchase_date", sa.Date(), nullable=True))
    op.add_column(
        "workshop_tools",
        sa.Column("purchase_cost", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "workshop_tools", sa.Column("calibration_interval_days", sa.Integer(), nullable=True)
    )

    # -------------------------------------------------------------------------
    # ALTER TABLE — spare_parts_inventory: 5 new nullable columns
    # -------------------------------------------------------------------------
    op.add_column("spare_parts_inventory", sa.Column("category", sa.String(40), nullable=True))
    op.add_column(
        "spare_parts_inventory", sa.Column("shelf_location", sa.String(80), nullable=True)
    )
    op.add_column(
        "spare_parts_inventory", sa.Column("supplier_name", sa.String(160), nullable=True)
    )
    op.add_column(
        "spare_parts_inventory", sa.Column("lead_time_days", sa.Integer(), nullable=True)
    )
    op.add_column(
        "spare_parts_inventory", sa.Column("reorder_quantity", sa.Integer(), nullable=True)
    )

    # -------------------------------------------------------------------------
    # CREATE TABLE — workshop_staff_rates
    # -------------------------------------------------------------------------
    op.create_table(
        "workshop_staff_rates",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workshop_staff_rates_tenant_id", "workshop_staff_rates", ["tenant_id"]
    )
    op.create_index(
        "ix_workshop_staff_rates_user_id", "workshop_staff_rates", ["user_id"]
    )
    op.execute("ALTER TABLE workshop_staff_rates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workshop_staff_rates FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_workshop_staff_rates ON workshop_staff_rates "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON workshop_staff_rates TO rotas_app"
    )

    # -------------------------------------------------------------------------
    # CREATE TABLE — tool_calibrations
    # -------------------------------------------------------------------------
    op.create_table(
        "tool_calibrations",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tool_id", sa.UUID(), nullable=False),
        sa.Column("calibrated_by", sa.UUID(), nullable=True),
        sa.Column("calibrated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["tool_id"], ["workshop_tools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tool_calibrations_tenant_id", "tool_calibrations", ["tenant_id"]
    )
    op.create_index(
        "ix_tool_calibrations_tool_id", "tool_calibrations", ["tool_id"]
    )
    op.execute("ALTER TABLE tool_calibrations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tool_calibrations FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_tool_calibrations ON tool_calibrations "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON tool_calibrations TO rotas_app"
    )

    # -------------------------------------------------------------------------
    # CREATE TABLE — spare_part_serial_items
    # -------------------------------------------------------------------------
    op.create_table(
        "spare_part_serial_items",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("part_id", sa.UUID(), nullable=False),
        sa.Column("serial_number", sa.String(120), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'in_stock'"),
        ),
        sa.Column("vehicle_id", sa.UUID(), nullable=True),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scrapped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["part_id"], ["spare_parts_inventory.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "serial_number",
            name="uq_spare_part_serial_items_tenant_serial",
        ),
    )
    op.create_index(
        "ix_spare_part_serial_items_tenant_part",
        "spare_part_serial_items",
        ["tenant_id", "part_id"],
    )
    op.create_index(
        "ix_spare_part_serial_items_tenant_vehicle",
        "spare_part_serial_items",
        ["tenant_id", "vehicle_id"],
        postgresql_where=sa.text("vehicle_id IS NOT NULL"),
    )
    op.execute("ALTER TABLE spare_part_serial_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE spare_part_serial_items FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_spare_part_serial_items ON spare_part_serial_items "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON spare_part_serial_items TO rotas_app"
    )


def downgrade() -> None:
    # Drop new tables in reverse dependency order
    op.drop_table("spare_part_serial_items")
    op.drop_table("tool_calibrations")
    op.drop_table("workshop_staff_rates")

    # Remove columns from spare_parts_inventory
    op.drop_column("spare_parts_inventory", "reorder_quantity")
    op.drop_column("spare_parts_inventory", "lead_time_days")
    op.drop_column("spare_parts_inventory", "supplier_name")
    op.drop_column("spare_parts_inventory", "shelf_location")
    op.drop_column("spare_parts_inventory", "category")

    # Remove columns from workshop_tools
    op.drop_column("workshop_tools", "calibration_interval_days")
    op.drop_column("workshop_tools", "purchase_cost")
    op.drop_column("workshop_tools", "purchase_date")
    op.drop_column("workshop_tools", "serial_number")
    op.drop_column("workshop_tools", "location")
    op.drop_column("workshop_tools", "category")

    # Remove column from work_orders
    op.drop_column("work_orders", "labor_cost")

    # Remove FK + columns from work_order_tasks
    op.drop_constraint(
        "fk_work_order_tasks_assigned_to_users", "work_order_tasks", type_="foreignkey"
    )
    op.drop_column("work_order_tasks", "actual_minutes")
    op.drop_column("work_order_tasks", "estimated_minutes")
    op.drop_column("work_order_tasks", "assigned_to")
