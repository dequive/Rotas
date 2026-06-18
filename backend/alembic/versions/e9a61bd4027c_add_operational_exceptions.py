"""add_operational_exceptions

Revision ID: e9a61bd4027c
Revises: d42f7c8e109a
Create Date: 2026-05-31 21:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "e9a61bd4027c"
down_revision: str | None = "d42f7c8e109a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_exceptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("exception_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("acknowledged_by", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high', 'critical')",
            name="chk_operational_exceptions_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved')",
            name="chk_operational_exceptions_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operational_exceptions_tenant_id", "operational_exceptions", ["tenant_id"])
    op.create_index("ix_operational_exceptions_entity_type", "operational_exceptions", ["entity_type"])
    op.create_index("ix_operational_exceptions_entity_id", "operational_exceptions", ["entity_id"])
    op.create_index(
        "ix_operational_exceptions_exception_type",
        "operational_exceptions",
        ["exception_type"],
    )
    op.create_index("ix_operational_exceptions_severity", "operational_exceptions", ["severity"])
    op.create_index("ix_operational_exceptions_status", "operational_exceptions", ["status"])
    op.create_index("ix_operational_exceptions_source_type", "operational_exceptions", ["source_type"])
    op.create_index("ix_operational_exceptions_source_id", "operational_exceptions", ["source_id"])
    op.create_index(
        "idx_operational_exceptions_active_queue",
        "operational_exceptions",
        ["tenant_id", "status", "severity", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_operational_exceptions_active_queue", table_name="operational_exceptions")
    op.drop_table("operational_exceptions")
