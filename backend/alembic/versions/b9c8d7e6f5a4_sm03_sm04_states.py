"""SM-03 SM-04: delivery proof and dispatch clearance state fields

Revision ID: b2c3d4e5f6a7
Revises: e9f8d7c6b5a4
Create Date: 2026-06-18
"""

import sqlalchemy as sa

from alembic import op

revision = "b9c8d7e6f5a4"
down_revision = "e9f8d7c6b5a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SM-03: DeliveryProof — add accepted/disputed/resolved states and audit fields
    # status already exists (default='pending') — add new timestamps
    op.add_column(
        "delivery_proofs", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("delivery_proofs", sa.Column("accepted_by", sa.UUID(), nullable=True))
    op.add_column(
        "delivery_proofs", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("delivery_proofs", sa.Column("rejected_by", sa.UUID(), nullable=True))
    op.add_column("delivery_proofs", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column(
        "delivery_proofs", sa.Column("dispute_opened_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "delivery_proofs", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("delivery_proofs", sa.Column("resolved_by", sa.UUID(), nullable=True))

    # SM-04: TripOrder (DispatchClearance) — add rejected/escalated states
    op.add_column("trip_orders", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column(
        "trip_orders", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("trip_orders", sa.Column("rejected_by", sa.UUID(), nullable=True))
    op.add_column(
        "trip_orders", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("trip_orders", sa.Column("clearance_sla_hours", sa.Integer(), nullable=True))

    # trips: add billing_status if not exists
    # we first check if the column exists to make it idempotent
    conn = op.get_bind()
    from sqlalchemy import inspect

    inspector = inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("trips")]
    if "billing_status" not in columns:
        op.add_column(
            "trips",
            sa.Column("billing_status", sa.String(30), nullable=True, server_default="pending"),
        )


def downgrade() -> None:
    for col in [
        "accepted_at",
        "accepted_by",
        "rejected_at",
        "rejected_by",
        "rejection_reason",
        "dispute_opened_at",
        "resolved_at",
        "resolved_by",
    ]:
        op.drop_column("delivery_proofs", col)
    for col in [
        "rejection_reason",
        "rejected_at",
        "rejected_by",
        "escalated_at",
        "clearance_sla_hours",
    ]:
        op.drop_column("trip_orders", col)
    op.drop_column("trips", "billing_status")
