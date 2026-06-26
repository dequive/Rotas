"""merge_insurance_and_billing_issuer

Revision ID: e66352d728cd
Revises: c5d6e7f8a9b0, ins01
Create Date: 2026-06-21 07:15:49.230918+02:00
"""

from collections.abc import Sequence

revision: str = "e66352d728cd"
down_revision: str | None = ("c5d6e7f8a9b0", "ins01")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
