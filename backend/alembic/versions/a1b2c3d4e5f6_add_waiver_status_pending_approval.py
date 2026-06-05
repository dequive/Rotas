"""add_waiver_status_pending_approval

Revision ID: a1b2c3d4e5f6
Revises: e42b8f6c3a11
Create Date: 2026-06-05 20:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "e42b8f6c3a11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("chk_operational_waiver_status", "operational_waivers", type_="check")
    op.create_check_constraint(
        "chk_operational_waiver_status",
        "operational_waivers",
        sa.text("status IN ('active', 'expired', 'revoked', 'pending_approval', 'rejected')"),
    )


def downgrade() -> None:
    op.drop_constraint("chk_operational_waiver_status", "operational_waivers", type_="check")
    op.create_check_constraint(
        "chk_operational_waiver_status",
        "operational_waivers",
        sa.text("status IN ('active', 'expired', 'revoked')"),
    )
