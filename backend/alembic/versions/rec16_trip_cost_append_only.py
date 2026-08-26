"""Make trip costs attributable, visibility-scoped and append-only.

Revision ID: rec16
Revises: rec15
Create Date: 2026-08-24 15:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rec16"
down_revision: str | None = "rec15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trip_costs",
        sa.Column("entry_type", sa.String(length=20), nullable=False, server_default="original"),
    )
    op.add_column("trip_costs", sa.Column("corrects_id", sa.UUID(), nullable=True))
    op.add_column("trip_costs", sa.Column("correction_reason", sa.Text(), nullable=True))
    op.add_column("trip_costs", sa.Column("driver_id", sa.UUID(), nullable=True))
    op.add_column(
        "trip_costs",
        sa.Column(
            "driver_visibility",
            sa.String(length=16),
            nullable=False,
            server_default="hidden",
        ),
    )
    op.add_column(
        "trip_costs",
        sa.Column(
            "recorded_by_type",
            sa.String(length=16),
            nullable=False,
            server_default="system",
        ),
    )

    # Deterministic migrate: the trip assignment is the journal owner snapshot.
    # Historical authorship is classified as Driver only when the stored source
    # identity exactly matches that assigned driver; no time/vehicle heuristic is used.
    op.execute(
        """
        UPDATE trip_costs AS cost
        SET
            driver_id = trip.driver_id,
            driver_visibility = CASE
                WHEN cost.paid_by = 'driver' THEN 'visible'
                ELSE 'hidden'
            END,
            recorded_by_type = CASE
                WHEN cost.source_type = 'driver_app'
                     AND cost.source_id = trip.driver_id THEN 'driver'
                WHEN cost.created_by IS NOT NULL THEN 'manager'
                ELSE 'system'
            END
        FROM trips AS trip
        WHERE trip.id = cost.trip_id
          AND trip.tenant_id = cost.tenant_id
        """
    )

    op.create_unique_constraint(
        "uq_drivers_tenant_id_id",
        "drivers",
        ["tenant_id", "id"],
    )
    op.create_unique_constraint(
        "uq_trip_costs_tenant_id_id",
        "trip_costs",
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_trip_costs_tenant_trip_trips",
        "trip_costs",
        "trips",
        ["tenant_id", "trip_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_trip_costs_tenant_corrects_trip_costs",
        "trip_costs",
        "trip_costs",
        ["tenant_id", "corrects_id"],
        ["tenant_id", "id"],
    )
    op.create_foreign_key(
        "fk_trip_costs_driver_id_drivers",
        "trip_costs",
        "drivers",
        ["driver_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_trip_costs_tenant_driver_drivers",
        "trip_costs",
        "drivers",
        ["tenant_id", "driver_id"],
        ["tenant_id", "id"],
    )
    op.create_check_constraint(
        "chk_trip_costs_entry_type",
        "trip_costs",
        "entry_type IN ('original', 'adjustment', 'reversal')",
    )
    op.create_check_constraint(
        "chk_trip_costs_driver_visibility",
        "trip_costs",
        "driver_visibility IN ('hidden', 'visible')",
    )
    op.create_check_constraint(
        "chk_trip_costs_recorded_by_type",
        "trip_costs",
        "recorded_by_type IN ('driver', 'manager', 'system')",
    )
    op.create_check_constraint(
        "chk_trip_costs_visible_owner",
        "trip_costs",
        "driver_visibility = 'hidden' OR driver_id IS NOT NULL",
    )
    op.create_check_constraint(
        "chk_trip_costs_correction_shape",
        "trip_costs",
        """
        (entry_type = 'original' AND corrects_id IS NULL
            AND correction_reason IS NULL AND amount >= 0)
        OR
        (entry_type = 'adjustment' AND corrects_id IS NOT NULL
            AND correction_reason IS NOT NULL AND amount <> 0)
        OR
        (entry_type = 'reversal' AND corrects_id IS NOT NULL
            AND correction_reason IS NOT NULL AND amount < 0)
        """,
    )
    op.create_index("ix_trip_costs_corrects_id", "trip_costs", ["corrects_id"])
    op.create_index(
        "ix_trip_costs_driver_journal",
        "trip_costs",
        ["tenant_id", "driver_id", "driver_visibility", "incurred_at"],
    )
    op.create_index(
        "uq_trip_costs_one_reversal_per_original",
        "trip_costs",
        ["tenant_id", "corrects_id"],
        unique=True,
        postgresql_where=sa.text("entry_type = 'reversal'"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_trip_cost_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'trip_costs are append-only; create an adjustment or reversal';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_trip_costs_append_only
        BEFORE UPDATE OR DELETE ON trip_costs
        FOR EACH ROW EXECUTE FUNCTION prevent_trip_cost_mutation()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_trip_costs_append_only ON trip_costs")
    op.execute("DROP FUNCTION IF EXISTS prevent_trip_cost_mutation()")
    op.drop_index("uq_trip_costs_one_reversal_per_original", table_name="trip_costs")
    op.drop_index("ix_trip_costs_driver_journal", table_name="trip_costs")
    op.drop_index("ix_trip_costs_corrects_id", table_name="trip_costs")
    op.drop_constraint("chk_trip_costs_correction_shape", "trip_costs", type_="check")
    op.drop_constraint("chk_trip_costs_visible_owner", "trip_costs", type_="check")
    op.drop_constraint("chk_trip_costs_recorded_by_type", "trip_costs", type_="check")
    op.drop_constraint("chk_trip_costs_driver_visibility", "trip_costs", type_="check")
    op.drop_constraint("chk_trip_costs_entry_type", "trip_costs", type_="check")
    op.drop_constraint("fk_trip_costs_tenant_driver_drivers", "trip_costs", type_="foreignkey")
    op.drop_constraint("fk_trip_costs_driver_id_drivers", "trip_costs", type_="foreignkey")
    op.drop_constraint(
        "fk_trip_costs_tenant_corrects_trip_costs",
        "trip_costs",
        type_="foreignkey",
    )
    op.drop_constraint("fk_trip_costs_tenant_trip_trips", "trip_costs", type_="foreignkey")
    op.drop_constraint("uq_trip_costs_tenant_id_id", "trip_costs", type_="unique")
    op.drop_constraint("uq_drivers_tenant_id_id", "drivers", type_="unique")
    op.drop_column("trip_costs", "recorded_by_type")
    op.drop_column("trip_costs", "driver_visibility")
    op.drop_column("trip_costs", "driver_id")
    op.drop_column("trip_costs", "correction_reason")
    op.drop_column("trip_costs", "corrects_id")
    op.drop_column("trip_costs", "entry_type")
