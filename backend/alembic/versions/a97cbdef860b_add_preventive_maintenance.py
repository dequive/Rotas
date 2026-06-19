"""add_preventive_maintenance

Revision ID: a97cbdef860b
Revises: f86badce759a
Create Date: 2026-06-02 15:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a97cbdef860b"
down_revision: str | None = "f86badce759a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("request_reference", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("interval_km", sa.Integer(), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=True),
        sa.Column("next_due_km", sa.Integer(), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "interval_km IS NOT NULL OR interval_days IS NOT NULL",
            name="chk_maintenance_plans_interval",
        ),
        sa.CheckConstraint(
            "interval_km IS NULL OR interval_km > 0", name="chk_maintenance_plans_interval_km"
        ),
        sa.CheckConstraint(
            "interval_days IS NULL OR interval_days > 0", name="chk_maintenance_plans_interval_days"
        ),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="chk_maintenance_plans_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_maintenance_plans_tenant_request_reference",
        ),
    )
    op.create_index("ix_maintenance_plans_tenant_id", "maintenance_plans", ["tenant_id"])
    op.create_index("ix_maintenance_plans_vehicle_id", "maintenance_plans", ["vehicle_id"])
    op.create_index(
        "ix_maintenance_plans_request_reference", "maintenance_plans", ["request_reference"]
    )
    op.create_index("ix_maintenance_plans_next_due_km", "maintenance_plans", ["next_due_km"])
    op.create_index("ix_maintenance_plans_next_due_at", "maintenance_plans", ["next_due_at"])
    op.create_index("ix_maintenance_plans_status", "maintenance_plans", ["status"])

    op.create_table(
        "maintenance_schedule",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("due_km", sa.Integer(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('overdue', 'completed', 'cancelled')",
            name="chk_maintenance_schedule_status",
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["maintenance_plans.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "plan_id",
            "status",
            name="uq_maintenance_schedule_tenant_plan_status",
        ),
    )
    op.create_index("ix_maintenance_schedule_tenant_id", "maintenance_schedule", ["tenant_id"])
    op.create_index("ix_maintenance_schedule_plan_id", "maintenance_schedule", ["plan_id"])
    op.create_index("ix_maintenance_schedule_vehicle_id", "maintenance_schedule", ["vehicle_id"])
    op.create_index("ix_maintenance_schedule_due_at", "maintenance_schedule", ["due_at"])
    op.create_index("ix_maintenance_schedule_status", "maintenance_schedule", ["status"])


def downgrade() -> None:
    op.drop_table("maintenance_schedule")
    op.drop_table("maintenance_plans")
