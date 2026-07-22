"""add_work_bays_and_plan_ownership_scope

Revision ID: bay01
Revises: cat01
Create Date: 2026-07-21 19:15:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'bay01'
down_revision: str | None = 'cat01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create work_bays
    op.create_table(
        'work_bays',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=60), server_default='geral', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_work_bays_tenant_id'), 'work_bays', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_work_bays_is_active'), 'work_bays', ['is_active'], unique=False)

    # 2. Add ownership_scope to maintenance_plans
    op.add_column(
        'maintenance_plans',
        sa.Column('ownership_scope', sa.String(length=20), server_default='fleet', nullable=False),
    )


def downgrade() -> None:
    op.drop_column('maintenance_plans', 'ownership_scope')
    op.drop_table('work_bays')
