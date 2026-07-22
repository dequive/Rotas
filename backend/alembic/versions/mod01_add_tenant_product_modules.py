"""add_tenant_product_modules

Revision ID: mod01
Revises: 3119f1368f93
Create Date: 2026-07-21 17:00:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'mod01'
down_revision: str | None = '3119f1368f93'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column(
            'product_modules',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='["tms"]',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('tenants', 'product_modules')
