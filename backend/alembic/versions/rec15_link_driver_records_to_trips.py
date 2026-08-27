"""Link Driver operational records to their trip.

Revision ID: rec15
Revises: rec14
Create Date: 2026-08-24 12:30:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rec15"
down_revision: str | None = "rec14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Widen only: historical rows remain nullable until a deterministic,
    # separately reviewed backfill exists. Vehicle/time heuristics are not an
    # acceptable substitute for an explicit trip identity.
    op.create_unique_constraint("uq_trips_tenant_id_id", "trips", ["tenant_id", "id"])

    op.add_column("checklists", sa.Column("trip_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_checklists_tenant_trip_trips",
        "checklists",
        "trips",
        ["tenant_id", "trip_id"],
        ["tenant_id", "id"],
    )
    op.create_index("ix_checklists_trip_id", "checklists", ["trip_id"])

    op.add_column("fuel_logs", sa.Column("trip_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_fuel_logs_tenant_trip_trips",
        "fuel_logs",
        "trips",
        ["tenant_id", "trip_id"],
        ["tenant_id", "id"],
    )
    op.create_index("ix_fuel_logs_trip_id", "fuel_logs", ["trip_id"])


def downgrade() -> None:
    op.drop_index("ix_fuel_logs_trip_id", table_name="fuel_logs")
    op.drop_constraint("fk_fuel_logs_tenant_trip_trips", "fuel_logs", type_="foreignkey")
    op.drop_column("fuel_logs", "trip_id")

    op.drop_index("ix_checklists_trip_id", table_name="checklists")
    op.drop_constraint("fk_checklists_tenant_trip_trips", "checklists", type_="foreignkey")
    op.drop_column("checklists", "trip_id")
    op.drop_constraint("uq_trips_tenant_id_id", "trips", type_="unique")
