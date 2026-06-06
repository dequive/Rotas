"""make_tenant_limits_nullable

INFRA-03: max_vehicles/max_drivers/max_users become nullable to support
"unlimited" plan tier (NULL = no limit enforced). Guards in service layer
treat NULL as skip-check (D-13).

Revision ID: a9b8c7d6e5f4
Revises: f0a1b2c3d4e5
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "a9b8c7d6e5f4"
down_revision: str | None = "f0a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("tenants", "max_vehicles", existing_type=sa.Integer(), nullable=True)
    op.alter_column("tenants", "max_drivers", existing_type=sa.Integer(), nullable=True)
    op.alter_column("tenants", "max_users", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Set NULL values to default before making NOT NULL again
    op.execute("UPDATE tenants SET max_vehicles = 5 WHERE max_vehicles IS NULL")
    op.execute("UPDATE tenants SET max_drivers = 5 WHERE max_drivers IS NULL")
    op.execute("UPDATE tenants SET max_users = 3 WHERE max_users IS NULL")
    op.alter_column("tenants", "max_vehicles", existing_type=sa.Integer(), nullable=False)
    op.alter_column("tenants", "max_drivers", existing_type=sa.Integer(), nullable=False)
    op.alter_column("tenants", "max_users", existing_type=sa.Integer(), nullable=False)
