"""Serialize driver pairing and make device identity unique.

Revision ID: rec14
Revises: rec13
Create Date: 2026-08-23 00:20:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec14"
down_revision: str | None = "rec13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "uq_driver_devices_tenant_driver_device"


def upgrade() -> None:
    # Concurrent historical pairing could create more than one row for the
    # same logical device. No table references driver_devices.id, so retain the
    # best representative deterministically before enforcing the invariant.
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY tenant_id, driver_id, device_id
                    ORDER BY
                        is_active DESC,
                        last_seen_at DESC NULLS LAST,
                        created_at DESC NULLS LAST,
                        id DESC
                ) AS duplicate_rank
            FROM driver_devices
        )
        DELETE FROM driver_devices AS duplicate
        USING ranked
        WHERE duplicate.id = ranked.id
          AND ranked.duplicate_rank > 1
        """
    )
    op.create_unique_constraint(
        _CONSTRAINT,
        "driver_devices",
        ["tenant_id", "driver_id", "device_id"],
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "driver_devices", type_="unique")
