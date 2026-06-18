"""add_workshop_operations

Revision ID: b42d6f8a315c
Revises: a31c5e7f204b
Create Date: 2026-06-02 10:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "b42d6f8a315c"
down_revision: str | None = "a31c5e7f204b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_requests",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=True),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("request_type", sa.String(length=40), nullable=False),
        sa.Column("priority", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("odometer_reading", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "request_type IN ('corrective', 'preventive', 'inspection', 'breakdown')",
            name="chk_maintenance_requests_type",
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="chk_maintenance_requests_priority",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'triaged', 'converted', 'closed', 'cancelled')",
            name="chk_maintenance_requests_status",
        ),
        sa.ForeignKeyConstraint(["incident_id"], ["trip_incidents.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_requests_tenant_id", "maintenance_requests", ["tenant_id"])
    op.create_index("ix_maintenance_requests_vehicle_id", "maintenance_requests", ["vehicle_id"])
    op.create_index("ix_maintenance_requests_trip_id", "maintenance_requests", ["trip_id"])
    op.create_index("ix_maintenance_requests_incident_id", "maintenance_requests", ["incident_id"])
    op.create_index("ix_maintenance_requests_request_type", "maintenance_requests", ["request_type"])
    op.create_index("ix_maintenance_requests_priority", "maintenance_requests", ["priority"])
    op.create_index("ix_maintenance_requests_status", "maintenance_requests", ["status"])
    op.create_index("ix_maintenance_requests_requested_at", "maintenance_requests", ["requested_at"])

    op.create_table(
        "work_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("maintenance_request_id", sa.UUID(), nullable=True),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("work_order_number", sa.String(length=80), nullable=False),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("planned_work", sa.Text(), nullable=False),
        sa.Column("estimated_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("actual_cost", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_by", sa.UUID(), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'in_progress', 'quality_check', 'closed', 'cancelled')",
            name="chk_work_orders_status",
        ),
        sa.ForeignKeyConstraint(["maintenance_request_id"], ["maintenance_requests.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "work_order_number", name="uq_work_orders_tenant_number"),
    )
    op.create_index("ix_work_orders_tenant_id", "work_orders", ["tenant_id"])
    op.create_index("ix_work_orders_maintenance_request_id", "work_orders", ["maintenance_request_id"])
    op.create_index("ix_work_orders_vehicle_id", "work_orders", ["vehicle_id"])
    op.create_index("ix_work_orders_work_order_number", "work_orders", ["work_order_number"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])


def downgrade() -> None:
    op.drop_table("work_orders")
    op.drop_table("maintenance_requests")
