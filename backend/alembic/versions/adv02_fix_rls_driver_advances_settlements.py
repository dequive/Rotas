"""fix_rls_driver_advances_settlements

Revision ID: adv02
Revises: adv01
Create Date: 2026-06-21

adv01 was applied before the RLS block was added to the file.
This migration retroactively adds RLS policies to driver_advances and trip_settlements.
"""

from alembic import op

revision = "adv02"
down_revision = "adv01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # driver_advances — idempotent: DROP POLICY IF EXISTS before CREATE
    op.execute("ALTER TABLE driver_advances ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE driver_advances FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS rls_driver_advances ON driver_advances;")
    op.execute(
        "CREATE POLICY rls_driver_advances ON driver_advances "
        "USING (tenant_id::text = current_setting('app.tenant_id', true));"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON driver_advances TO rotas_app;")

    # trip_settlements — same pattern
    op.execute("ALTER TABLE trip_settlements ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE trip_settlements FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS rls_trip_settlements ON trip_settlements;")
    op.execute(
        "CREATE POLICY rls_trip_settlements ON trip_settlements "
        "USING (tenant_id::text = current_setting('app.tenant_id', true));"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON trip_settlements TO rotas_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS rls_trip_settlements ON trip_settlements;")
    op.execute("DROP POLICY IF EXISTS rls_driver_advances ON driver_advances;")
