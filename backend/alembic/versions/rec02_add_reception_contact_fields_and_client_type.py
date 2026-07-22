"""add_reception_contact_fields_and_client_type

Revision ID: rec02
Revises: 1e006dfe187d
Create Date: 2026-07-22 20:30:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rec02"
down_revision: str | None = "1e006dfe187d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add client_type to clients table
    op.add_column(
        "clients",
        sa.Column("client_type", sa.String(length=20), server_default="individual", nullable=False),
    )

    # 2. Add contact fields to vehicle_receptions
    op.add_column("vehicle_receptions", sa.Column("delivered_by_name", sa.String(length=160), nullable=True))
    op.add_column("vehicle_receptions", sa.Column("delivered_by_phone", sa.String(length=40), nullable=True))
    op.add_column("vehicle_receptions", sa.Column("pickup_authorized_by_name", sa.String(length=160), nullable=True))
    op.add_column("vehicle_receptions", sa.Column("pickup_authorized_by_phone", sa.String(length=40), nullable=True))

    # 3. Add contact & override fields to vehicle_releases
    op.add_column("vehicle_releases", sa.Column("picked_up_by_name", sa.String(length=160), nullable=True))
    op.add_column("vehicle_releases", sa.Column("picked_up_by_phone", sa.String(length=40), nullable=True))
    op.add_column(
        "vehicle_releases",
        sa.Column("override_unauthorized_pickup", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column("vehicle_releases", sa.Column("override_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("vehicle_releases", "override_reason")
    op.drop_column("vehicle_releases", "override_unauthorized_pickup")
    op.drop_column("vehicle_releases", "picked_up_by_phone")
    op.drop_column("vehicle_releases", "picked_up_by_name")

    op.drop_column("vehicle_receptions", "pickup_authorized_by_phone")
    op.drop_column("vehicle_receptions", "pickup_authorized_by_name")
    op.drop_column("vehicle_receptions", "delivered_by_phone")
    op.drop_column("vehicle_receptions", "delivered_by_name")

    op.drop_column("clients", "client_type")
