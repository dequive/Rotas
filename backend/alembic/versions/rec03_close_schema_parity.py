"""Close production schema parity gaps without dropping managed indexes.

Revision ID: rec03
Revises: rec02
Create Date: 2026-07-22 21:00:00+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "rec03"
down_revision: str | None = "rec02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TIMESTAMP_TABLES = (
    "fiscal_counters",
    "insurance_claims",
    "tenant_document_profiles",
    "vehicle_insurances",
)

_QUANTITY_COLUMNS = (
    ("maintenance_parts_used", "quantity"),
    ("spare_part_movements", "quantity"),
    ("spare_part_movements", "balance_after_quantity"),
    ("spare_parts_inventory", "current_quantity"),
    ("spare_parts_inventory", "minimum_quantity"),
)


def upgrade() -> None:
    for table in _TIMESTAMP_TABLES:
        op.execute(f"UPDATE {table} SET created_at = now() WHERE created_at IS NULL")
        op.execute(f"UPDATE {table} SET updated_at = COALESCE(created_at, now()) WHERE updated_at IS NULL")
        op.alter_column(table, "created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        op.alter_column(table, "updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    # Production databases may already have this model-managed index even when
    # their Alembic revision is still rec02. Keep reconciliation restart-safe.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_insurance_claims_status "
        "ON insurance_claims (status)"
    )

    # Numeric(15, 3) preserves the 12 integer digits available in Numeric(14, 2)
    # while adding the sub-unit precision required by parts and fluid quantities.
    for table, column in _QUANTITY_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(precision=14, scale=2),
            type_=sa.Numeric(precision=15, scale=3),
            existing_nullable=False,
        )


def downgrade() -> None:
    for table, column in reversed(_QUANTITY_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(precision=15, scale=3),
            type_=sa.Numeric(precision=14, scale=2),
            existing_nullable=False,
        )

    op.execute("DROP INDEX IF EXISTS ix_insurance_claims_status")

    for table in reversed(_TIMESTAMP_TABLES):
        op.alter_column(table, "updated_at", existing_type=sa.DateTime(timezone=True), nullable=True)
        op.alter_column(table, "created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
