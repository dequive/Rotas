"""add alert request reference

Revision ID: b08dc1ef9712
Revises: a97cbdef860b
Create Date: 2026-06-02 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b08dc1ef9712"
down_revision: str | None = "a97cbdef860b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("alerts", sa.Column("request_reference", sa.String(length=120), nullable=True))
    op.execute("UPDATE alerts SET request_reference = 'legacy:' || id::text")
    op.alter_column("alerts", "request_reference", nullable=False)
    op.create_unique_constraint(
        "uq_alerts_tenant_request_reference",
        "alerts",
        ["tenant_id", "request_reference"],
    )
    op.create_index("ix_alerts_request_reference", "alerts", ["request_reference"])


def downgrade() -> None:
    op.drop_index("ix_alerts_request_reference", table_name="alerts")
    op.drop_constraint("uq_alerts_tenant_request_reference", "alerts", type_="unique")
    op.drop_column("alerts", "request_reference")
