"""driver_passport_and_bi_replace_inatter

Revision ID: b7e2a9c4d1f3
Revises: c3a1d8e2f047
Create Date: 2026-06-07 09:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7e2a9c4d1f3"
down_revision: str | None = "c3a1d8e2f047"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("drivers", "inatter_license")
    op.drop_column("drivers", "inatter_valid_until")
    op.add_column("drivers", sa.Column("passport_number", sa.String(80), nullable=True))
    op.add_column("drivers", sa.Column("passport_valid_until", sa.Date, nullable=True))
    op.add_column("drivers", sa.Column("bi_number", sa.String(80), nullable=True))
    op.add_column("drivers", sa.Column("bi_valid_until", sa.Date, nullable=True))


def downgrade() -> None:
    op.drop_column("drivers", "bi_valid_until")
    op.drop_column("drivers", "bi_number")
    op.drop_column("drivers", "passport_valid_until")
    op.drop_column("drivers", "passport_number")
    op.add_column("drivers", sa.Column("inatter_valid_until", sa.Date, nullable=True))
    op.add_column("drivers", sa.Column("inatter_license", sa.String(80), nullable=True))
