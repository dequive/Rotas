"""merge_composite_indexes_and_work_order_plan_id

Revision ID: cb7d41a8a0f7
Revises: a1b2c3d4e5f6, b19ec4f5d607
Create Date: 2026-06-05 23:03:26.265438+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'cb7d41a8a0f7'
down_revision: str | None = ('a1b2c3d4e5f6', 'b19ec4f5d607')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
