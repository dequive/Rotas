"""add_service_catalog_billing_warranty

Revision ID: cat01
Revises: quo01
Create Date: 2026-07-21 18:45:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'cat01'
down_revision: str | None = 'quo01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create service_catalog_items
    op.create_table(
        'service_catalog_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=60), server_default='geral', nullable=False),
        sa.Column('standard_duration_minutes', sa.Integer(), server_default='60', nullable=False),
        sa.Column('base_price', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('includes_parts', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_service_catalog_tenant_code'),
    )
    op.create_index(op.f('ix_service_catalog_items_tenant_id'), 'service_catalog_items', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_service_catalog_items_code'), 'service_catalog_items', ['code'], unique=False)
    op.create_index(op.f('ix_service_catalog_items_category'), 'service_catalog_items', ['category'], unique=False)
    op.create_index(op.f('ix_service_catalog_items_is_active'), 'service_catalog_items', ['is_active'], unique=False)

    # 2. Create service_warranties
    op.create_table(
        'service_warranties',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('warranty_type', sa.String(length=40), server_default='full_service', nullable=False),
        sa.Column('duration_months', sa.Integer(), server_default='6', nullable=False),
        sa.Column('duration_km', sa.Integer(), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('km_at_service', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='active', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.ForeignKeyConstraint(['work_order_id'], ['work_orders.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_service_warranties_tenant_id'), 'service_warranties', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_service_warranties_work_order_id'), 'service_warranties', ['work_order_id'], unique=False)
    op.create_index(op.f('ix_service_warranties_vehicle_id'), 'service_warranties', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_service_warranties_client_id'), 'service_warranties', ['client_id'], unique=False)
    op.create_index(op.f('ix_service_warranties_status'), 'service_warranties', ['status'], unique=False)

    # 3. Add fields to billing_documents & billing_items
    op.add_column('billing_documents', sa.Column('document_source', sa.String(length=20), server_default='transport', nullable=False))
    op.add_column('billing_documents', sa.Column('reception_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('billing_documents', sa.Column('quote_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(op.f('ix_billing_documents_document_source'), 'billing_documents', ['document_source'], unique=False)
    op.create_index(op.f('ix_billing_documents_reception_id'), 'billing_documents', ['reception_id'], unique=False)
    op.create_index(op.f('ix_billing_documents_quote_id'), 'billing_documents', ['quote_id'], unique=False)
    op.create_foreign_key('fk_billing_documents_reception_id', 'billing_documents', 'vehicle_receptions', ['reception_id'], ['id'])
    op.create_foreign_key('fk_billing_documents_quote_id', 'billing_documents', 'workshop_quotes', ['quote_id'], ['id'])

    op.add_column('billing_items', sa.Column('work_order_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('billing_items', sa.Column('catalog_item_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('billing_items', sa.Column('item_source', sa.String(length=30), server_default='transport', nullable=False))
    op.create_index(op.f('ix_billing_items_work_order_id'), 'billing_items', ['work_order_id'], unique=False)
    op.create_index(op.f('ix_billing_items_catalog_item_id'), 'billing_items', ['catalog_item_id'], unique=False)
    op.create_foreign_key('fk_billing_items_work_order_id', 'billing_items', 'work_orders', ['work_order_id'], ['id'])
    op.create_foreign_key('fk_billing_items_catalog_item_id', 'billing_items', 'service_catalog_items', ['catalog_item_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_billing_items_catalog_item_id', 'billing_items', type_='foreignkey')
    op.drop_constraint('fk_billing_items_work_order_id', 'billing_items', type_='foreignkey')
    op.drop_index(op.f('ix_billing_items_catalog_item_id'), table_name='billing_items')
    op.drop_index(op.f('ix_billing_items_work_order_id'), table_name='billing_items')
    op.drop_column('billing_items', 'item_source')
    op.drop_column('billing_items', 'catalog_item_id')
    op.drop_column('billing_items', 'work_order_id')

    op.drop_constraint('fk_billing_documents_quote_id', 'billing_documents', type_='foreignkey')
    op.drop_constraint('fk_billing_documents_reception_id', 'billing_documents', type_='foreignkey')
    op.drop_index(op.f('ix_billing_documents_quote_id'), table_name='billing_documents')
    op.drop_index(op.f('ix_billing_documents_reception_id'), table_name='billing_documents')
    op.drop_index(op.f('ix_billing_documents_document_source'), table_name='billing_documents')
    op.drop_column('billing_documents', 'quote_id')
    op.drop_column('billing_documents', 'reception_id')
    op.drop_column('billing_documents', 'document_source')

    op.drop_table('service_warranties')
    op.drop_table('service_catalog_items')
