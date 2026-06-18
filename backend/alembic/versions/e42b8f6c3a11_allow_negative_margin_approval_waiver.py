"""allow_negative_margin_approval_waiver

Revision ID: e42b8f6c3a11
Revises: d0d7b5a91e6c
Create Date: 2026-06-04 17:42:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e42b8f6c3a11"
down_revision: str | None = "d0d7b5a91e6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WAIVER_TYPES_WITH_NEGATIVE_MARGIN = (
    "waiver_type IN ('overweight_assignment', 'missing_document', 'expired_warning', "
    "'no_pod', 'cost_overrun', 'manual_dispatch', 'negative_margin_approved')"
)
WAIVER_TYPES_BASE = (
    "waiver_type IN ('overweight_assignment', 'missing_document', 'expired_warning', "
    "'no_pod', 'cost_overrun', 'manual_dispatch')"
)


def upgrade() -> None:
    op.drop_constraint("chk_operational_waiver_type", "operational_waivers", type_="check")
    op.create_check_constraint(
        "chk_operational_waiver_type",
        "operational_waivers",
        sa.text(WAIVER_TYPES_WITH_NEGATIVE_MARGIN),
    )


def downgrade() -> None:
    op.drop_constraint("chk_operational_waiver_type", "operational_waivers", type_="check")
    op.create_check_constraint(
        "chk_operational_waiver_type",
        "operational_waivers",
        sa.text(WAIVER_TYPES_BASE),
    )
