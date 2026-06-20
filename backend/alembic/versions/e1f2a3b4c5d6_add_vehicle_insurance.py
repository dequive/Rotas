"""add_vehicle_insurance

Revision ID: e1f2a3b4c5d6
Revises: e1a2b3c4d5f6
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "e1a2b3c4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── vehicle_insurances ────────────────────────────────────────────────────
    op.create_table(
        "vehicle_insurances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("policy_number", sa.String(80), nullable=False),
        sa.Column("insurer", sa.String(120), nullable=False),
        sa.Column("coverage_type", sa.String(40), nullable=False),  # civil_liability|comprehensive|cargo
        sa.Column("premium_amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False, index=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # v2.0 rule: RLS + GRANT in same migration as CREATE TABLE
    op.execute("ALTER TABLE vehicle_insurances ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE vehicle_insurances FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_vehicle_insurances ON vehicle_insurances "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON vehicle_insurances TO rotas_app")

    # ── insurance_claims ──────────────────────────────────────────────────────
    op.create_table(
        "insurance_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "vehicle_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicles.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "insurance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vehicle_insurances.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "incident_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trip_incidents.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("claim_number", sa.String(80), nullable=True),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("estimated_damage", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        # open | under_review | paid | rejected
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # v2.0 rule: RLS + GRANT in same migration as CREATE TABLE
    op.execute("ALTER TABLE insurance_claims ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE insurance_claims FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_insurance_claims ON insurance_claims "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON insurance_claims TO rotas_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_insurance_claims ON insurance_claims")
    op.drop_table("insurance_claims")
    op.execute("DROP POLICY IF EXISTS rls_vehicle_insurances ON vehicle_insurances")
    op.drop_table("vehicle_insurances")
