"""add_trip_orders

Revision ID: 9b4ad2b7f1c0
Revises: 6278288d5cd8
Create Date: 2026-05-31 00:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "9b4ad2b7f1c0"
down_revision: str | None = "6278288d5cd8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


ACTIVE_TRIP_STATUS_SQL = (
    "status IN ('planned', 'dispatch_pending', 'dispatched', 'in_progress', 'delayed', 'incident')"
)


def upgrade() -> None:
    op.create_table(
        "trip_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=True),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("customer_reference", sa.String(length=160), nullable=True),
        sa.Column("origin", sa.String(length=160), nullable=False),
        sa.Column("destination", sa.String(length=160), nullable=False),
        sa.Column("cargo_type", sa.String(length=120), nullable=True),
        sa.Column("cargo_description", sa.Text(), nullable=True),
        sa.Column("estimated_weight", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_volume", sa.Numeric(12, 2), nullable=True),
        sa.Column("cargo_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("cargo_risk_level", sa.String(length=30), nullable=False),
        sa.Column("requested_pickup_date", sa.Date(), nullable=False),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("sla_pickup_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_delivery_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_vehicle_id", sa.UUID(), nullable=True),
        sa.Column("assigned_driver_id", sa.UUID(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_by", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("estimated_distance_km", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_fuel_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_toll_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("estimated_revenue", sa.Numeric(12, 2), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("load_permit_id", sa.UUID(), nullable=True),
        sa.Column("requires_load_permit", sa.Boolean(), nullable=False),
        sa.Column("requires_police_clearance", sa.Boolean(), nullable=False),
        sa.Column("requires_customs_clearance", sa.Boolean(), nullable=False),
        sa.Column("operational_notes", sa.Text(), nullable=True),
        sa.Column("commercial_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'confirmed', 'planning', 'assigned', 'dispatch_pending', "
            "'dispatched', 'in_execution', 'delivered', 'closed', 'cancelled', 'expired', 'rejected')",
            name="chk_trip_orders_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="chk_trip_orders_priority",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'contract_schedule', 'client_request')",
            name="chk_trip_orders_source",
        ),
        sa.CheckConstraint(
            "cargo_risk_level IN ('low', 'normal', 'high', 'critical')",
            name="chk_trip_orders_cargo_risk",
        ),
        sa.ForeignKeyConstraint(["assigned_driver_id"], ["drivers.id"]),
        sa.ForeignKeyConstraint(["assigned_vehicle_id"], ["vehicles.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"]),
        sa.ForeignKeyConstraint(["load_permit_id"], ["load_permits.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_orders_tenant_id", "trip_orders", ["tenant_id"])
    op.create_index("ix_trip_orders_status", "trip_orders", ["status"])
    op.create_index("ix_trip_orders_priority", "trip_orders", ["priority"])
    op.create_index("ix_trip_orders_requested_pickup_date", "trip_orders", ["requested_pickup_date"])
    op.create_index("ix_trip_orders_contract_id", "trip_orders", ["contract_id"])
    op.create_index("ix_trip_orders_client_id", "trip_orders", ["client_id"])
    op.create_index("ix_trip_orders_customer_reference", "trip_orders", ["customer_reference"])
    op.create_index("ix_trip_orders_assigned_vehicle_id", "trip_orders", ["assigned_vehicle_id"])
    op.create_index("ix_trip_orders_assigned_driver_id", "trip_orders", ["assigned_driver_id"])
    op.create_index("ix_trip_orders_load_permit_id", "trip_orders", ["load_permit_id"])
    op.create_index(
        "idx_trip_orders_status_date",
        "trip_orders",
        ["tenant_id", "status", "requested_pickup_date"],
    )
    op.create_index(
        "idx_trip_orders_assigned_vehicle",
        "trip_orders",
        ["tenant_id", "assigned_vehicle_id"],
        postgresql_where=sa.text("assigned_vehicle_id IS NOT NULL"),
    )
    op.create_index(
        "idx_trip_orders_assigned_driver",
        "trip_orders",
        ["tenant_id", "assigned_driver_id"],
        postgresql_where=sa.text("assigned_driver_id IS NOT NULL"),
    )

    op.add_column("trips", sa.Column("trip_order_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_trips_trip_order_id",
        "trips",
        "trip_orders",
        ["trip_order_id"],
        ["id"],
    )
    op.create_index("ix_trips_trip_order_id", "trips", ["trip_order_id"])
    op.create_index(
        "uniq_trips_trip_order",
        "trips",
        ["trip_order_id"],
        unique=True,
        postgresql_where=sa.text("trip_order_id IS NOT NULL"),
    )
    op.create_index(
        "uniq_active_vehicle_trip",
        "trips",
        ["tenant_id", "vehicle_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_TRIP_STATUS_SQL),
    )
    op.create_index(
        "uniq_active_driver_trip",
        "trips",
        ["tenant_id", "driver_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_TRIP_STATUS_SQL),
    )


def downgrade() -> None:
    op.drop_index("uniq_active_driver_trip", table_name="trips")
    op.drop_index("uniq_active_vehicle_trip", table_name="trips")
    op.drop_index("uniq_trips_trip_order", table_name="trips")
    op.drop_index("ix_trips_trip_order_id", table_name="trips")
    op.drop_constraint("fk_trips_trip_order_id", "trips", type_="foreignkey")
    op.drop_column("trips", "trip_order_id")

    op.drop_index("idx_trip_orders_assigned_driver", table_name="trip_orders")
    op.drop_index("idx_trip_orders_assigned_vehicle", table_name="trip_orders")
    op.drop_index("idx_trip_orders_status_date", table_name="trip_orders")
    op.drop_index("ix_trip_orders_load_permit_id", table_name="trip_orders")
    op.drop_index("ix_trip_orders_assigned_driver_id", table_name="trip_orders")
    op.drop_index("ix_trip_orders_assigned_vehicle_id", table_name="trip_orders")
    op.drop_index("ix_trip_orders_customer_reference", table_name="trip_orders")
    op.drop_index("ix_trip_orders_client_id", table_name="trip_orders")
    op.drop_index("ix_trip_orders_contract_id", table_name="trip_orders")
    op.drop_index("ix_trip_orders_requested_pickup_date", table_name="trip_orders")
    op.drop_index("ix_trip_orders_priority", table_name="trip_orders")
    op.drop_index("ix_trip_orders_status", table_name="trip_orders")
    op.drop_index("ix_trip_orders_tenant_id", table_name="trip_orders")
    op.drop_table("trip_orders")
