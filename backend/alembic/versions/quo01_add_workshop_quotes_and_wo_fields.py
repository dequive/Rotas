"""add_workshop_quotes_and_wo_fields

Revision ID: quo01
Revises: rec01
Create Date: 2026-07-21 17:45:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'quo01'
down_revision: str | None = 'rec01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add fields to work_orders
    op.add_column(
        'work_orders',
        sa.Column('reception_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        'work_orders',
        sa.Column('origin_type', sa.String(length=30), server_default='direct', nullable=False),
    )
    op.add_column(
        'work_orders',
        sa.Column('warranty_original_wo_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f('ix_work_orders_reception_id'), 'work_orders', ['reception_id'], unique=False)
    op.create_index(op.f('ix_work_orders_warranty_original_wo_id'), 'work_orders', ['warranty_original_wo_id'], unique=False)
    op.create_foreign_key(
        'fk_work_orders_reception_id_vehicle_receptions',
        'work_orders',
        'vehicle_receptions',
        ['reception_id'],
        ['id'],
    )
    op.create_foreign_key(
        'fk_work_orders_warranty_original_wo_id_work_orders',
        'work_orders',
        'work_orders',
        ['warranty_original_wo_id'],
        ['id'],
    )

    # 2. Create workshop_quotes
    op.create_table(
        'workshop_quotes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reception_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quote_number', sa.String(length=80), nullable=False),
        sa.Column('is_supplemental', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('related_work_order_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('labor_total', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('parts_total', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('tax_total', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('client_signature_file_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['client_signature_file_id'], ['files.id']),
        sa.ForeignKeyConstraint(['reception_id'], ['vehicle_receptions.id']),
        sa.ForeignKeyConstraint(['related_work_order_id'], ['work_orders.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workshop_quotes_tenant_id'), 'workshop_quotes', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_workshop_quotes_vehicle_id'), 'workshop_quotes', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_workshop_quotes_client_id'), 'workshop_quotes', ['client_id'], unique=False)
    op.create_index(op.f('ix_workshop_quotes_reception_id'), 'workshop_quotes', ['reception_id'], unique=False)
    op.create_index(op.f('ix_workshop_quotes_quote_number'), 'workshop_quotes', ['quote_number'], unique=False)
    op.create_index(op.f('ix_workshop_quotes_related_work_order_id'), 'workshop_quotes', ['related_work_order_id'], unique=False)
    op.create_index(op.f('ix_workshop_quotes_status'), 'workshop_quotes', ['status'], unique=False)

    # 3. Create workshop_quote_items
    op.create_table(
        'workshop_quote_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('item_type', sa.String(length=20), server_default='labor', nullable=False),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('part_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), server_default='1', nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('total_price', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('warranty_months', sa.Integer(), server_default='0', nullable=False),
        sa.Column('warranty_km', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['part_id'], ['spare_parts_inventory.id']),
        sa.ForeignKeyConstraint(['quote_id'], ['workshop_quotes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_workshop_quote_items_tenant_id'), 'workshop_quote_items', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_workshop_quote_items_quote_id'), 'workshop_quote_items', ['quote_id'], unique=False)


def downgrade() -> None:
    op.drop_table('workshop_quote_items')
    op.drop_table('workshop_quotes')
    op.drop_constraint('fk_work_orders_warranty_original_wo_id_work_orders', 'work_orders', type_='foreignkey')
    op.drop_constraint('fk_work_orders_reception_id_vehicle_receptions', 'work_orders', type_='foreignkey')
    op.drop_index(op.f('ix_work_orders_warranty_original_wo_id'), table_name='work_orders')
    op.drop_index(op.f('ix_work_orders_reception_id'), table_name='work_orders')
    op.drop_column('work_orders', 'warranty_original_wo_id')
    op.drop_column('work_orders', 'origin_type')
    op.drop_column('work_orders', 'reception_id')
