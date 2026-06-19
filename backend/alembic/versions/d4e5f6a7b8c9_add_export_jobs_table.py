"""add_export_jobs_table

Revision ID: d4e5f6a7b8c9
Revises: cb7d41a8a0f7
Create Date: 2026-06-05 22:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "cb7d41a8a0f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("job_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("file_path", sa.Text, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_export_jobs_tenant_status",
        "export_jobs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_export_jobs_tenant_entity_type",
        "export_jobs",
        ["tenant_id", "entity_id", "job_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_jobs_tenant_entity_type", table_name="export_jobs")
    op.drop_index("ix_export_jobs_tenant_status", table_name="export_jobs")
    op.drop_table("export_jobs")
