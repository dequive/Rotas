"""add is_international to trips

Revision ID: 9a3cc9a059814
Revises: f5fe4c151bd1
Create Date: 2026-06-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "9a3cc9a059814"
down_revision = "f5fe4c151bd1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trips",
        sa.Column(
            "is_international",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("trips", "is_international")
