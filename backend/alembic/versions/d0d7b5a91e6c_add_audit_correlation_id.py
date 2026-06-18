"""add_audit_correlation_id

Revision ID: d0d7b5a91e6c
Revises: bf5c3a9e21d4
Create Date: 2026-06-03 21:30:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d0d7b5a91e6c"
down_revision: str | None = "bf5c3a9e21d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(length=128), nullable=True))
    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    op.drop_column("audit_logs", "correlation_id")
