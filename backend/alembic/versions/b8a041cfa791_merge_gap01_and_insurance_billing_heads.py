"""merge_gap01_and_insurance_billing_heads

Revision ID: b8a041cfa791
Revises: gap01, e66352d728cd
Create Date: 2026-06-21 10:07:17.236208+02:00
"""

from collections.abc import Sequence

revision: str = "b8a041cfa791"
down_revision: str | None = ("gap01", "e66352d728cd")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
