"""add_third_party_nullable_fks

Revision ID: tp03
Revises: tp01b
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "tp03"
down_revision = "tp01b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # fuel_purchases: nullable FK → third_parties.id (ON DELETE SET NULL)
    op.add_column(
        "fuel_purchases",
        sa.Column(
            "supplier_third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_fuel_purchases_supplier_tp",
        "fuel_purchases",
        ["supplier_third_party_id"],
    )

    # spare_parts_inventory: nullable FK → third_parties.id (ON DELETE SET NULL)
    op.add_column(
        "spare_parts_inventory",
        sa.Column(
            "supplier_third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_spare_parts_supplier_tp",
        "spare_parts_inventory",
        ["supplier_third_party_id"],
    )

    # work_orders: nullable FK → third_parties.id (ON DELETE SET NULL)
    op.add_column(
        "work_orders",
        sa.Column(
            "service_provider_third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_work_orders_service_provider_tp",
        "work_orders",
        ["service_provider_third_party_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_work_orders_service_provider_tp", table_name="work_orders")
    op.drop_column("work_orders", "service_provider_third_party_id")

    op.drop_index("ix_spare_parts_supplier_tp", table_name="spare_parts_inventory")
    op.drop_column("spare_parts_inventory", "supplier_third_party_id")

    op.drop_index("ix_fuel_purchases_supplier_tp", table_name="fuel_purchases")
    op.drop_column("fuel_purchases", "supplier_third_party_id")
