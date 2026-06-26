"""add_mz_provinces

Revision ID: tp01a
Revises: acfa8ae500c0
Create Date: 2026-06-19
"""

import sqlalchemy as sa

from alembic import op

revision = "tp01a"
down_revision = "acfa8ae500c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mz_provinces",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("name_local", sa.String(80), nullable=True),
        sa.Column("region", sa.String(30), nullable=True),
    )
    # Platform-level reference table — no tenant_id, SELECT only
    op.execute("GRANT SELECT ON mz_provinces TO rotas_app")


def downgrade() -> None:
    op.drop_table("mz_provinces")
