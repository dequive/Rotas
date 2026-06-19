"""add driver pairing codes

Revision ID: c19ed2fa0823
Revises: b08dc1ef9712
Create Date: 2026-06-02 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c19ed2fa0823"
down_revision: str | None = "b08dc1ef9712"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("drivers", sa.Column("pairing_code_hash", sa.String(length=64), nullable=True))
    op.add_column("drivers", sa.Column("pairing_code_expires_at", sa.DateTime(timezone=True)))
    op.create_index("ix_drivers_pairing_code_hash", "drivers", ["pairing_code_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_drivers_pairing_code_hash", table_name="drivers")
    op.drop_column("drivers", "pairing_code_expires_at")
    op.drop_column("drivers", "pairing_code_hash")
