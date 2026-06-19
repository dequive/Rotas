"""add_operational_close_and_waivers

Revision ID: f18a4b6d2e90
Revises: c1a8df090b33
Create Date: 2026-05-31 00:20:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f18a4b6d2e90"
down_revision: str | None = "c1a8df090b33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("trips", sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("trips", sa.Column("closed_by", sa.UUID(), nullable=True))
    op.add_column("trips", sa.Column("operational_close_notes", sa.Text(), nullable=True))

    op.create_table(
        "operational_waivers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("waiver_type", sa.String(length=50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.String(length=30), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "waiver_type IN ('overweight_assignment', 'missing_document', 'expired_warning', "
            "'no_pod', 'cost_overrun', 'manual_dispatch')",
            name="chk_operational_waiver_type",
        ),
        sa.CheckConstraint(
            "risk_level IN ('low', 'medium', 'high', 'critical')",
            name="chk_operational_waiver_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'expired', 'revoked')",
            name="chk_operational_waiver_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operational_waivers_tenant_id", "operational_waivers", ["tenant_id"])
    op.create_index("ix_operational_waivers_entity_type", "operational_waivers", ["entity_type"])
    op.create_index("ix_operational_waivers_entity_id", "operational_waivers", ["entity_id"])
    op.create_index("ix_operational_waivers_waiver_type", "operational_waivers", ["waiver_type"])
    op.create_index("ix_operational_waivers_risk_level", "operational_waivers", ["risk_level"])
    op.create_index("ix_operational_waivers_expires_at", "operational_waivers", ["expires_at"])
    op.create_index("ix_operational_waivers_status", "operational_waivers", ["status"])
    op.create_index(
        "idx_operational_waivers_entity",
        "operational_waivers",
        ["tenant_id", "entity_type", "entity_id", "waiver_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_operational_waivers_entity", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_status", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_expires_at", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_risk_level", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_waiver_type", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_entity_id", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_entity_type", table_name="operational_waivers")
    op.drop_index("ix_operational_waivers_tenant_id", table_name="operational_waivers")
    op.drop_table("operational_waivers")
    op.drop_column("trips", "operational_close_notes")
    op.drop_column("trips", "closed_by")
    op.drop_column("trips", "closed_at")
