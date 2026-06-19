"""add_despacho_overrides_to_known_routes

Revision ID: c3a1d8e2f047
Revises: f8774ec1c190
Create Date: 2026-06-06 18:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3a1d8e2f047"
down_revision: str | None = "4b0a7802dc3c"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("known_routes", sa.Column("despacho_vazio", sa.Numeric(10, 2), nullable=True))
    op.add_column("known_routes", sa.Column("despacho_carregado", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("known_routes", "despacho_carregado")
    op.drop_column("known_routes", "despacho_vazio")
