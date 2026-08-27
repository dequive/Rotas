"""Harden inventory UUID generation and audit timestamps.

Revision ID: rec13
Revises: rec12
Create Date: 2026-07-26 20:15:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec13"
down_revision: str | None = "rec12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INVENTORY_TABLES = (
    "warehouses",
    "item_categories",
    "items",
    "stock_movements",
)


def upgrade() -> None:
    for table in _INVENTORY_TABLES:
        op.execute(
            f"ALTER TABLE {table} "
            "ALTER COLUMN id SET DEFAULT gen_random_uuid()"
        )
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS created_at timestamptz "
            "NOT NULL DEFAULT now()"
        )
        op.execute(
            f"ALTER TABLE {table} "
            "ADD COLUMN IF NOT EXISTS updated_at timestamptz "
            "NOT NULL DEFAULT now()"
        )


def downgrade() -> None:
    # Security/data-forward migration: identity and audit fields are retained.
    pass
