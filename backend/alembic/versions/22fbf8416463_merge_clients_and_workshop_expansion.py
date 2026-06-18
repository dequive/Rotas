"""merge_clients_and_workshop_expansion

Revision ID: 22fbf8416463
Revises: a2b3c4d5e6f7, a8f3b2c1d4e5
Create Date: 2026-06-19 00:59:23.720634+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '22fbf8416463'
down_revision: str | None = ('a2b3c4d5e6f7', 'a8f3b2c1d4e5')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
