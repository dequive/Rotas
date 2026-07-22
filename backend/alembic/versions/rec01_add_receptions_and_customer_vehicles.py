"""add_receptions_and_customer_vehicles

Revision ID: rec01
Revises: mod01
Create Date: 2026-07-21 17:30:00.000000+02:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'rec01'
down_revision: str | None = 'mod01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add ownership_type and customer_client_id to vehicles
    op.add_column(
        'vehicles',
        sa.Column('ownership_type', sa.String(length=20), server_default='fleet', nullable=False),
    )
    op.add_column(
        'vehicles',
        sa.Column('customer_client_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f('ix_vehicles_ownership_type'), 'vehicles', ['ownership_type'], unique=False)
    op.create_index(op.f('ix_vehicles_customer_client_id'), 'vehicles', ['customer_client_id'], unique=False)
    op.create_foreign_key(
        'fk_vehicles_customer_client_id_clients',
        'vehicles',
        'clients',
        ['customer_client_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # 2. Create tenant_sequences
    op.create_table(
        'tenant_sequences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('current_value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'entity_type', name='uq_tenant_sequences_entity'),
    )
    op.create_index(op.f('ix_tenant_sequences_tenant_id'), 'tenant_sequences', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_tenant_sequences_entity_type'), 'tenant_sequences', ['entity_type'], unique=False)

    # 3. Create vehicle_receptions
    op.create_table(
        'vehicle_receptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('reception_number', sa.String(length=80), nullable=False),
        sa.Column('received_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('odometer_at_reception', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reported_issues', sa.Text(), nullable=True),
        sa.Column('visual_condition', sa.Text(), nullable=True),
        sa.Column('personal_items', sa.Text(), nullable=True),
        sa.Column('fuel_level', sa.String(length=20), server_default='half', nullable=False),
        sa.Column('client_signature_file_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('estimated_completion_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='received', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['client_signature_file_id'], ['files.id']),
        sa.ForeignKeyConstraint(['received_by'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_vehicle_receptions_tenant_id'), 'vehicle_receptions', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_vehicle_receptions_vehicle_id'), 'vehicle_receptions', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_vehicle_receptions_client_id'), 'vehicle_receptions', ['client_id'], unique=False)
    op.create_index(op.f('ix_vehicle_receptions_reception_number'), 'vehicle_receptions', ['reception_number'], unique=False)
    op.create_index(op.f('ix_vehicle_receptions_status'), 'vehicle_receptions', ['status'], unique=False)

    # 4. Create reception_photos
    op.create_table(
        'reception_photos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reception_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('caption', sa.String(length=200), nullable=True),
        sa.Column('taken_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['files.id']),
        sa.ForeignKeyConstraint(['reception_id'], ['vehicle_receptions.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reception_photos_tenant_id'), 'reception_photos', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_reception_photos_reception_id'), 'reception_photos', ['reception_id'], unique=False)

    # 5. Create vehicle_releases
    op.create_table(
        'vehicle_releases',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reception_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('released_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('released_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('odometer_at_release', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('condition_at_release', sa.Text(), nullable=True),
        sa.Column('client_signature_file_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('release_type', sa.String(length=30), server_default='after_service', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_signature_file_id'], ['files.id']),
        sa.ForeignKeyConstraint(['reception_id'], ['vehicle_receptions.id']),
        sa.ForeignKeyConstraint(['released_by'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_vehicle_releases_tenant_id'), 'vehicle_releases', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_vehicle_releases_vehicle_id'), 'vehicle_releases', ['vehicle_id'], unique=False)
    op.create_index(op.f('ix_vehicle_releases_reception_id'), 'vehicle_releases', ['reception_id'], unique=False)


def downgrade() -> None:
    op.drop_table('vehicle_releases')
    op.drop_table('reception_photos')
    op.drop_table('vehicle_receptions')
    op.drop_table('tenant_sequences')
    op.drop_constraint('fk_vehicles_customer_client_id_clients', 'vehicles', type_='foreignkey')
    op.drop_index(op.f('ix_vehicles_customer_client_id'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_ownership_type'), table_name='vehicles')
    op.drop_column('vehicles', 'customer_client_id')
    op.drop_column('vehicles', 'ownership_type')
