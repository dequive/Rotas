"""add_plan_id_to_work_orders

Revision ID: 7b6acddf4ab0
Revises: f8774ec1c190
Create Date: 2026-06-05 21:41:55.194220+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '7b6acddf4ab0'
down_revision: str | None = 'f8774ec1c190'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add plan_id FK to work_orders for maintenance scheduler de-dupe (D-04)
    op.add_column('work_orders', sa.Column('plan_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_work_orders_plan_id'), 'work_orders', ['plan_id'], unique=False)
    op.create_foreign_key(
        'fk_work_orders_plan_id',
        'work_orders',
        'maintenance_plans',
        ['plan_id'],
        ['id'],
    )
    # Extend maintenance_schedule status constraint to include 'pending' (for next-cycle records D-03)
    op.drop_constraint('chk_maintenance_schedule_status', 'maintenance_schedule', type_='check')
    op.create_check_constraint(
        'chk_maintenance_schedule_status',
        'maintenance_schedule',
        "status IN ('overdue', 'completed', 'cancelled', 'pending')",
    )


def downgrade() -> None:
    # Revert maintenance_schedule status constraint
    op.drop_constraint('chk_maintenance_schedule_status', 'maintenance_schedule', type_='check')
    op.create_check_constraint(
        'chk_maintenance_schedule_status',
        'maintenance_schedule',
        "status IN ('overdue', 'completed', 'cancelled')",
    )
    # Revert work_orders plan_id column
    op.drop_constraint('fk_work_orders_plan_id', 'work_orders', type_='foreignkey')
    op.drop_index(op.f('ix_work_orders_plan_id'), table_name='work_orders')
    op.drop_column('work_orders', 'plan_id')
