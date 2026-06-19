"""add_trip_cost_reconciliation

Revision ID: f86badce759a
Revises: e75a9cbd648f
Create Date: 2026-06-02 14:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f86badce759a"
down_revision: str | None = "e75a9cbd648f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column(
            "actual_revenue", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "trips",
        sa.Column(
            "actual_margin", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "trips",
        sa.Column("costs_reconciled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "trip_costs", sa.Column("request_reference", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "trip_costs",
        sa.Column("source_type", sa.String(length=40), server_default="manual", nullable=False),
    )
    op.add_column("trip_costs", sa.Column("source_id", sa.UUID(), nullable=True))
    op.add_column("trip_costs", sa.Column("created_by", sa.UUID(), nullable=True))
    op.execute("UPDATE trip_costs SET request_reference = 'legacy:' || id::text")
    op.alter_column("trip_costs", "request_reference", nullable=False)
    op.create_unique_constraint(
        "uq_trip_costs_tenant_request_reference",
        "trip_costs",
        ["tenant_id", "request_reference"],
    )
    op.create_index("ix_trip_costs_request_reference", "trip_costs", ["request_reference"])
    op.create_index("ix_trip_costs_source_type", "trip_costs", ["source_type"])
    op.create_index("ix_trip_costs_source_id", "trip_costs", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_trip_costs_source_id", table_name="trip_costs")
    op.drop_index("ix_trip_costs_source_type", table_name="trip_costs")
    op.drop_index("ix_trip_costs_request_reference", table_name="trip_costs")
    op.drop_constraint(
        "uq_trip_costs_tenant_request_reference",
        "trip_costs",
        type_="unique",
    )
    op.drop_column("trip_costs", "created_by")
    op.drop_column("trip_costs", "source_id")
    op.drop_column("trip_costs", "source_type")
    op.drop_column("trip_costs", "request_reference")
    op.drop_column("trips", "costs_reconciled_at")
    op.drop_column("trips", "actual_margin")
    op.drop_column("trips", "actual_revenue")
