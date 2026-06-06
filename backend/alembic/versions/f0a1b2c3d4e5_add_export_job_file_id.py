"""add_export_job_file_id

Adds file_id FK column to export_jobs table, linking ARQ worker-generated
billing exports to the files table (INFRA-02).

file_path is retained for backward compatibility with existing download endpoints.

Revision ID: f0a1b2c3d4e5
Revises: e1f2a3b4c5d6
Create Date: 2026-06-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f0a1b2c3d4e5"
down_revision: str | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "export_jobs",
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("export_jobs", "file_id")
