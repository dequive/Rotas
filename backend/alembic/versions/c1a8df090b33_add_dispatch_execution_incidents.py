"""add_dispatch_execution_incidents

Revision ID: c1a8df090b33
Revises: 9b4ad2b7f1c0
Create Date: 2026-05-31 00:10:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "c1a8df090b33"
down_revision: str | None = "9b4ad2b7f1c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dispatch_clearances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("trip_order_id", sa.UUID(), nullable=True),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_checked", sa.Boolean(), nullable=False),
        sa.Column("driver_checked", sa.Boolean(), nullable=False),
        sa.Column("documents_checked", sa.Boolean(), nullable=False),
        sa.Column("load_permit_checked", sa.Boolean(), nullable=False),
        sa.Column("cargo_checked", sa.Boolean(), nullable=False),
        sa.Column("fuel_advance_checked", sa.Boolean(), nullable=False),
        sa.Column("route_risk_checked", sa.Boolean(), nullable=False),
        sa.Column("clearance_status", sa.String(length=30), nullable=False),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "clearance_status IN ('pending', 'approved', 'blocked', 'cancelled')",
            name="chk_dispatch_clearance_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.ForeignKeyConstraint(["trip_order_id"], ["trip_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dispatch_clearances_tenant_id", "dispatch_clearances", ["tenant_id"])
    op.create_index("ix_dispatch_clearances_trip_id", "dispatch_clearances", ["trip_id"])
    op.create_index(
        "ix_dispatch_clearances_trip_order_id",
        "dispatch_clearances",
        ["trip_order_id"],
    )
    op.create_index(
        "ix_dispatch_clearances_clearance_status",
        "dispatch_clearances",
        ["clearance_status"],
    )
    op.create_index(
        "idx_dispatch_clearances_trip",
        "dispatch_clearances",
        ["tenant_id", "trip_id", "clearance_status"],
    )

    op.create_table(
        "trip_execution_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location", sa.JSON(), nullable=True),
        sa.Column("odometer_reading", sa.Numeric(12, 2), nullable=True),
        sa.Column("fuel_level", sa.Numeric(5, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reported_by", sa.UUID(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('dispatched', 'departed_origin', 'arrived_loading_point', "
            "'loading_started', 'loading_completed', 'departed_loading_point', "
            "'arrived_checkpoint', 'delayed', 'incident_reported', 'arrived_destination', "
            "'unloading_started', 'unloading_completed', 'proof_of_delivery_uploaded', 'completed')",
            name="chk_trip_execution_event_type",
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'driver_app', 'gps', 'integration', 'system')",
            name="chk_trip_execution_source",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_execution_events_tenant_id", "trip_execution_events", ["tenant_id"])
    op.create_index("ix_trip_execution_events_trip_id", "trip_execution_events", ["trip_id"])
    op.create_index("ix_trip_execution_events_event_type", "trip_execution_events", ["event_type"])
    op.create_index("ix_trip_execution_events_event_time", "trip_execution_events", ["event_time"])
    op.create_index(
        "idx_trip_execution_events_trip_time",
        "trip_execution_events",
        ["tenant_id", "trip_id", "event_time"],
    )

    op.create_table(
        "trip_incidents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("trip_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=True),
        sa.Column("driver_id", sa.UUID(), nullable=True),
        sa.Column("incident_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("location", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("immediate_action", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("financial_impact_estimate", sa.Numeric(14, 2), nullable=True),
        sa.Column("delay_minutes", sa.Integer(), nullable=True),
        sa.Column("reported_by", sa.UUID(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "incident_type IN ('accident', 'breakdown', 'police_stop', 'border_delay', "
            "'client_delay', 'loading_delay', 'unloading_delay', 'theft', 'cargo_damage', "
            "'route_blocked', 'fuel_issue', 'document_issue', 'other')",
            name="chk_trip_incident_type",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="chk_trip_incident_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'resolved', 'closed')",
            name="chk_trip_incident_status",
        ),
        sa.ForeignKeyConstraint(["driver_id"], ["drivers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_incidents_tenant_id", "trip_incidents", ["tenant_id"])
    op.create_index("ix_trip_incidents_trip_id", "trip_incidents", ["trip_id"])
    op.create_index("ix_trip_incidents_vehicle_id", "trip_incidents", ["vehicle_id"])
    op.create_index("ix_trip_incidents_driver_id", "trip_incidents", ["driver_id"])
    op.create_index("ix_trip_incidents_incident_type", "trip_incidents", ["incident_type"])
    op.create_index("ix_trip_incidents_severity", "trip_incidents", ["severity"])
    op.create_index("ix_trip_incidents_status", "trip_incidents", ["status"])
    op.create_index("ix_trip_incidents_occurred_at", "trip_incidents", ["occurred_at"])
    op.create_index(
        "idx_trip_incidents_status",
        "trip_incidents",
        ["tenant_id", "status", "severity"],
    )


def downgrade() -> None:
    op.drop_index("idx_trip_incidents_status", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_occurred_at", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_status", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_severity", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_incident_type", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_driver_id", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_vehicle_id", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_trip_id", table_name="trip_incidents")
    op.drop_index("ix_trip_incidents_tenant_id", table_name="trip_incidents")
    op.drop_table("trip_incidents")

    op.drop_index("idx_trip_execution_events_trip_time", table_name="trip_execution_events")
    op.drop_index("ix_trip_execution_events_event_time", table_name="trip_execution_events")
    op.drop_index("ix_trip_execution_events_event_type", table_name="trip_execution_events")
    op.drop_index("ix_trip_execution_events_trip_id", table_name="trip_execution_events")
    op.drop_index("ix_trip_execution_events_tenant_id", table_name="trip_execution_events")
    op.drop_table("trip_execution_events")

    op.drop_index("idx_dispatch_clearances_trip", table_name="dispatch_clearances")
    op.drop_index("ix_dispatch_clearances_clearance_status", table_name="dispatch_clearances")
    op.drop_index("ix_dispatch_clearances_trip_order_id", table_name="dispatch_clearances")
    op.drop_index("ix_dispatch_clearances_trip_id", table_name="dispatch_clearances")
    op.drop_index("ix_dispatch_clearances_tenant_id", table_name="dispatch_clearances")
    op.drop_table("dispatch_clearances")
