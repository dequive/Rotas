"""merge_rls_and_export_jobs

Revision ID: 147542222231
Revises: b7e2a9c4d1f3, d4e5f6a7b8c9
Create Date: 2026-06-07 00:39:41.578213+02:00
"""

from collections.abc import Sequence

revision: str = "147542222231"
down_revision: str | None = ("b7e2a9c4d1f3", "d4e5f6a7b8c9")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
