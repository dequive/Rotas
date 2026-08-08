"""Harden rotas_app grants outside tenant-scoped tables.

Revision ID: rec07
Revises: rec06
Create Date: 2026-07-23 13:00:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec07"
down_revision: str | None = "rec06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("REVOKE ALL ON alembic_version FROM rotas_app")
    op.execute("REVOKE ALL ON platform_audit_logs FROM rotas_app")
    op.execute("REVOKE ALL ON platform_users FROM rotas_app")
    op.execute("REVOKE ALL ON tenants FROM rotas_app")
    op.execute("GRANT SELECT ON tenants, mz_provinces TO rotas_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rotas_app")


def downgrade() -> None:
    # Security-forward migration: never restore broad control-plane privileges.
    pass
