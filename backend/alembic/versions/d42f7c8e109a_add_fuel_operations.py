"""add_fuel_operations

Revision ID: d42f7c8e109a
Revises: f18a4b6d2e90
Create Date: 2026-05-31 20:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d42f7c8e109a"
down_revision: str | None = "f18a4b6d2e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fuel_tanks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("fuel_type", sa.String(length=30), nullable=False),
        sa.Column("capacity_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("minimum_stock_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("current_stock_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("average_unit_cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("capacity_liters > 0", name="chk_fuel_tanks_positive_capacity"),
        sa.CheckConstraint(
            "minimum_stock_liters >= 0 AND minimum_stock_liters <= capacity_liters",
            name="chk_fuel_tanks_minimum_stock",
        ),
        sa.CheckConstraint(
            "current_stock_liters >= 0 AND current_stock_liters <= capacity_liters",
            name="chk_fuel_tanks_current_stock",
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="chk_fuel_tanks_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_fuel_tanks_tenant_code"),
    )
    op.create_index("ix_fuel_tanks_tenant_id", "fuel_tanks", ["tenant_id"])
    op.create_index("ix_fuel_tanks_code", "fuel_tanks", ["code"])
    op.create_index("ix_fuel_tanks_fuel_type", "fuel_tanks", ["fuel_type"])
    op.create_index("ix_fuel_tanks_status", "fuel_tanks", ["status"])

    op.create_table(
        "fuel_purchases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("supplier_name", sa.String(length=160), nullable=False),
        sa.Column("purchase_reference", sa.String(length=100), nullable=False),
        sa.Column("fuel_type", sa.String(length=30), nullable=False),
        sa.Column("ordered_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("ordered_liters > 0", name="chk_fuel_purchases_positive_liters"),
        sa.CheckConstraint("unit_price >= 0", name="chk_fuel_purchases_unit_price"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'cancelled', 'received')",
            name="chk_fuel_purchases_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "purchase_reference",
            name="uq_fuel_purchases_tenant_reference",
        ),
    )
    op.create_index("ix_fuel_purchases_tenant_id", "fuel_purchases", ["tenant_id"])
    op.create_index(
        "ix_fuel_purchases_purchase_reference", "fuel_purchases", ["purchase_reference"]
    )
    op.create_index("ix_fuel_purchases_fuel_type", "fuel_purchases", ["fuel_type"])
    op.create_index("ix_fuel_purchases_status", "fuel_purchases", ["status"])

    op.create_table(
        "fuel_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tank_id", sa.UUID(), nullable=False),
        sa.Column("movement_type", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=False),
        sa.Column("liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("balance_after_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("direction IN ('in', 'out')", name="chk_fuel_movements_direction"),
        sa.CheckConstraint("liters > 0", name="chk_fuel_movements_positive_liters"),
        sa.CheckConstraint("balance_after_liters >= 0", name="chk_fuel_movements_balance"),
        sa.ForeignKeyConstraint(["tank_id"], ["fuel_tanks.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_movements_tenant_id", "fuel_movements", ["tenant_id"])
    op.create_index("ix_fuel_movements_tank_id", "fuel_movements", ["tank_id"])
    op.create_index("ix_fuel_movements_movement_type", "fuel_movements", ["movement_type"])
    op.create_index("ix_fuel_movements_direction", "fuel_movements", ["direction"])
    op.create_index("ix_fuel_movements_source_type", "fuel_movements", ["source_type"])
    op.create_index("ix_fuel_movements_source_id", "fuel_movements", ["source_id"])
    op.create_index("ix_fuel_movements_occurred_at", "fuel_movements", ["occurred_at"])

    op.create_table(
        "fuel_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("purchase_id", sa.UUID(), nullable=False),
        sa.Column("tank_id", sa.UUID(), nullable=False),
        sa.Column("received_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivery_note_number", sa.String(length=120), nullable=True),
        sa.Column("delivery_note_file_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("movement_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("received_liters > 0", name="chk_fuel_receipts_positive_liters"),
        sa.CheckConstraint("status IN ('verified', 'disputed')", name="chk_fuel_receipts_status"),
        sa.ForeignKeyConstraint(["delivery_note_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["movement_id"], ["fuel_movements.id"]),
        sa.ForeignKeyConstraint(["purchase_id"], ["fuel_purchases.id"]),
        sa.ForeignKeyConstraint(["tank_id"], ["fuel_tanks.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_receipts_tenant_id", "fuel_receipts", ["tenant_id"])
    op.create_index("ix_fuel_receipts_purchase_id", "fuel_receipts", ["purchase_id"])
    op.create_index("ix_fuel_receipts_tank_id", "fuel_receipts", ["tank_id"])
    op.create_index("ix_fuel_receipts_received_at", "fuel_receipts", ["received_at"])
    op.create_index("ix_fuel_receipts_status", "fuel_receipts", ["status"])

    op.create_table(
        "vehicle_refuels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tank_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("driver_id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=True),
        sa.Column("liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("odometer_reading", sa.Integer(), nullable=False),
        sa.Column("refueled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total_cost", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("movement_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("liters > 0", name="chk_vehicle_refuels_positive_liters"),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"]),
        sa.ForeignKeyConstraint(["movement_id"], ["fuel_movements.id"]),
        sa.ForeignKeyConstraint(["tank_id"], ["fuel_tanks.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicle_refuels_tenant_id", "vehicle_refuels", ["tenant_id"])
    op.create_index("ix_vehicle_refuels_tank_id", "vehicle_refuels", ["tank_id"])
    op.create_index("ix_vehicle_refuels_vehicle_id", "vehicle_refuels", ["vehicle_id"])
    op.create_index("ix_vehicle_refuels_driver_id", "vehicle_refuels", ["driver_id"])
    op.create_index("ix_vehicle_refuels_trip_id", "vehicle_refuels", ["trip_id"])
    op.create_index("ix_vehicle_refuels_refueled_at", "vehicle_refuels", ["refueled_at"])

    op.create_table(
        "fuel_stock_counts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("tank_id", sa.UUID(), nullable=False),
        sa.Column("theoretical_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("measured_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("variance_liters", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("counted_by", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("measured_liters >= 0", name="chk_fuel_stock_counts_measured"),
        sa.ForeignKeyConstraint(["tank_id"], ["fuel_tanks.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_stock_counts_tenant_id", "fuel_stock_counts", ["tenant_id"])
    op.create_index("ix_fuel_stock_counts_tank_id", "fuel_stock_counts", ["tank_id"])
    op.create_index("ix_fuel_stock_counts_counted_at", "fuel_stock_counts", ["counted_at"])


def downgrade() -> None:
    op.drop_table("fuel_stock_counts")
    op.drop_table("vehicle_refuels")
    op.drop_table("fuel_receipts")
    op.drop_table("fuel_movements")
    op.drop_table("fuel_purchases")
    op.drop_table("fuel_tanks")
