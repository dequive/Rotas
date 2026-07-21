"""stabilization_p0_rls_accounting_payables (P0-F5)

Apply v2.0 RLS policies (ENABLE, FORCE, tenant_isolation policy, GRANT TO
rotas_app) to Accounting and Payables tables that were created before the RLS
framework migration and are currently unprotected.

Tables covered:
  accounting_accounts
  accounting_journal_entries
  accounting_journal_items
  purchase_orders
  supplier_invoices
  supplier_payments

Revision ID: 3119f1368f93
Revises: 4dd4802e1c18
Create Date: 2026-07-20 22:18:15.123456+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = '3119f1368f93'
down_revision: str | None = '4dd4802e1c18'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RLS_TABLES = [
    "accounting_accounts",
    "accounting_journal_entries",
    "accounting_journal_items",
    "purchase_orders",
    "supplier_invoices",
    "supplier_payments",
]


def _rls(tablename: str) -> None:
    op.execute(f"ALTER TABLE {tablename} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tablename} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY rls_{tablename} ON {tablename} "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tablename} TO rotas_app")


def _drop_rls(tablename: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS rls_{tablename} ON {tablename}")
    op.execute(f"ALTER TABLE {tablename} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {tablename} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    for tbl in _RLS_TABLES:
        _rls(tbl)


def downgrade() -> None:
    for tbl in reversed(_RLS_TABLES):
        _drop_rls(tbl)