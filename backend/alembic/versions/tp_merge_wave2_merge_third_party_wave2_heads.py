"""merge_third_party_wave2_heads

Revision ID: tp_merge_wave2
Revises: tp06
Create Date: 2026-06-19 17:09:38.591851+02:00
"""

from collections.abc import Sequence

revision: str = "tp_merge_wave2"
down_revision: tuple[str, ...] = ("tp03", "tp05", "tp06")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
