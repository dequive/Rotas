"""add_tenant_compliance_policy

Revision ID: aa94e2d0b7c1
Revises: c19ed2fa0823
Create Date: 2026-06-03 12:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "aa94e2d0b7c1"
down_revision: str | None = "c19ed2fa0823"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("compliance_policy", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "compliance_policy")
