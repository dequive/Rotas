"""rec05_reconcile_schema_drift

Revision ID: d8a499250d84
Revises: rec04
Create Date: 2026-07-23 10:40:53.504290+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d8a499250d84"
down_revision: str | None = "rec04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE clients SET client_type = 'individual' WHERE client_type IS NULL")
    op.alter_column(
        "clients",
        "client_type",
        existing_type=sa.VARCHAR(length=20),
        nullable=False,
        existing_server_default=sa.text("'individual'::character varying"),
    )
    op.drop_constraint(
        "insurance_claims_incident_id_fkey", "insurance_claims", type_="foreignkey"
    )
    op.drop_constraint(
        "insurance_claims_insurance_id_fkey", "insurance_claims", type_="foreignkey"
    )
    op.create_foreign_key(
        "insurance_claims_incident_id_fkey",
        "insurance_claims",
        "trip_incidents",
        ["incident_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "insurance_claims_insurance_id_fkey",
        "insurance_claims",
        "vehicle_insurances",
        ["insurance_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.execute(
        "UPDATE vehicle_releases SET override_unauthorized_pickup = false "
        "WHERE override_unauthorized_pickup IS NULL"
    )
    op.alter_column(
        "vehicle_releases",
        "override_unauthorized_pickup",
        existing_type=sa.BOOLEAN(),
        nullable=False,
        existing_server_default=sa.text("false"),
    )


def downgrade() -> None:
    op.alter_column(
        "vehicle_releases",
        "override_unauthorized_pickup",
        existing_type=sa.BOOLEAN(),
        nullable=True,
        existing_server_default=sa.text("false"),
    )
    op.drop_constraint(
        "insurance_claims_insurance_id_fkey", "insurance_claims", type_="foreignkey"
    )
    op.drop_constraint(
        "insurance_claims_incident_id_fkey", "insurance_claims", type_="foreignkey"
    )
    op.create_foreign_key(
        "insurance_claims_insurance_id_fkey",
        "insurance_claims",
        "vehicle_insurances",
        ["insurance_id"],
        ["id"],
    )
    op.create_foreign_key(
        "insurance_claims_incident_id_fkey",
        "insurance_claims",
        "trip_incidents",
        ["incident_id"],
        ["id"],
    )
    op.alter_column(
        "clients",
        "client_type",
        existing_type=sa.VARCHAR(length=20),
        nullable=True,
        existing_server_default=sa.text("'individual'::character varying"),
    )
