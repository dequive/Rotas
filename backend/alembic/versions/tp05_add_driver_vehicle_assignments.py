"""add_driver_vehicle_assignments

Revision ID: tp05
Revises: tp01b
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "tp05"
down_revision = "tp01b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "driver_vehicle_assignments",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "driver_id",
            UUID(as_uuid=True),
            sa.ForeignKey("drivers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "vehicle_id",
            UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assignment_type",
            sa.String(40),
            nullable=True,
        ),
        # assignment_type values: primary | temporary | maintenance_only
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "assigned_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_dva_tenant",
        "driver_vehicle_assignments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_dva_driver",
        "driver_vehicle_assignments",
        ["tenant_id", "driver_id"],
    )
    op.create_index(
        "ix_dva_vehicle",
        "driver_vehicle_assignments",
        ["tenant_id", "vehicle_id"],
    )

    # v2.0 RLS rules — mandatory for tenant_id tables
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON driver_vehicle_assignments TO rotas_app"
    )
    op.execute(
        "ALTER TABLE driver_vehicle_assignments ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE driver_vehicle_assignments FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """CREATE POLICY tenant_isolation ON driver_vehicle_assignments
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation ON driver_vehicle_assignments"
    )
    op.drop_index("ix_dva_vehicle", table_name="driver_vehicle_assignments")
    op.drop_index("ix_dva_driver", table_name="driver_vehicle_assignments")
    op.drop_index("ix_dva_tenant", table_name="driver_vehicle_assignments")
    op.drop_table("driver_vehicle_assignments")
