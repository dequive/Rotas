"""add_driver_advances_and_trip_settlements

Revision ID: adv01
Revises: iva01a1b2c3d4
Create Date: 2026-06-21

CRITICAL: RLS + GRANT are co-located in this CREATE TABLE migration per v2.0 migration rule.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "adv01"
down_revision = "iva01a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── driver_advances ──────────────────────────────────────────────────
    op.create_table(
        "driver_advances",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column(
            "trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False, index=True
        ),
        sa.Column(
            "driver_id", UUID(as_uuid=True), sa.ForeignKey("drivers.id"), nullable=False, index=True
        ),
        sa.Column("amount_mzn", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MZN"),
        sa.Column("status", sa.String(20), nullable=False, server_default="issued"),
        sa.Column("issued_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("request_reference", sa.String(100), nullable=True),
        sa.UniqueConstraint("tenant_id", "request_reference", name="uq_driver_advances_tenant_ref"),
        sa.CheckConstraint("amount_mzn > 0", name="chk_driver_advances_amount_positive"),
        sa.CheckConstraint(
            "status IN ('issued', 'settled', 'voided')", name="chk_driver_advances_status"
        ),
    )
    op.execute("ALTER TABLE driver_advances ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE driver_advances FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY rls_driver_advances ON driver_advances "
        "USING (tenant_id::text = current_setting('app.tenant_id', true));"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON driver_advances TO rotas_app;")

    # ── trip_settlements ─────────────────────────────────────────────────
    op.create_table(
        "trip_settlements",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False, index=True
        ),
        sa.Column("trip_id", UUID(as_uuid=True), sa.ForeignKey("trips.id"), nullable=False),
        sa.Column(
            "advance_id", UUID(as_uuid=True), sa.ForeignKey("driver_advances.id"), nullable=True
        ),
        sa.Column("total_costs_mzn", sa.Numeric(10, 2), nullable=False),
        sa.Column("advance_amount_mzn", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("balance_mzn", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("pdf_file_id", UUID(as_uuid=True), sa.ForeignKey("files.id"), nullable=True),
        sa.Column(
            "settled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("trip_id", name="uq_trip_settlements_trip_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="chk_trip_settlements_status"
        ),
    )
    op.execute("ALTER TABLE trip_settlements ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE trip_settlements FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY rls_trip_settlements ON trip_settlements "
        "USING (tenant_id::text = current_setting('app.tenant_id', true));"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON trip_settlements TO rotas_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_trip_settlements ON trip_settlements;")
    op.drop_table("trip_settlements")
    op.execute("DROP POLICY IF EXISTS rls_driver_advances ON driver_advances;")
    op.drop_table("driver_advances")
