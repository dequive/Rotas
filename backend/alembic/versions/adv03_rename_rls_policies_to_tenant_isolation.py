"""rename_rls_policies_to_tenant_isolation

Revision ID: adv03
Revises: adv02
Create Date: 2026-06-21

adv02 created policies named rls_driver_advances / rls_trip_settlements.
The project convention (and test gate) requires policyname = 'tenant_isolation'.
This migration renames them.
"""

from alembic import op

revision = "adv03"
down_revision = "adv02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("driver_advances", "trip_settlements"):
        op.execute(f"DROP POLICY IF EXISTS rls_{table} ON {table};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id::text = current_setting('app.tenant_id', true));"
        )


def downgrade() -> None:
    for table in ("driver_advances", "trip_settlements"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(
            f"CREATE POLICY rls_{table} ON {table} "
            f"USING (tenant_id::text = current_setting('app.tenant_id', true));"
        )
