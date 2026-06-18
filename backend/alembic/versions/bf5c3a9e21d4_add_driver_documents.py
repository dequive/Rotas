"""add_driver_documents

Revision ID: bf5c3a9e21d4
Revises: aa94e2d0b7c1
Create Date: 2026-06-03 13:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "bf5c3a9e21d4"
down_revision: str | None = "aa94e2d0b7c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("documents", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("drivers", "documents")
