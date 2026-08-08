"""Grant the administrative runtime role access required by cross-tenant workers.

Revision ID: rec12
Revises: rec11
Create Date: 2026-07-26 16:30:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec12"
down_revision: str | None = "rec11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # rotas_admin is deliberately powerful across tenant data, but it must not
    # be a superuser. BYPASSRLS is required by platform operations and workers
    # that reconcile or dispatch records for more than one tenant.
    op.execute("ALTER ROLE rotas_admin NOSUPERUSER BYPASSRLS")
    op.execute("ALTER ROLE rotas_admin SET search_path = public")
    op.execute("GRANT USAGE ON SCHEMA public TO rotas_admin")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rotas_admin"
    )
    op.execute(
        "GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO rotas_admin"
    )

    # Preserve the worker grant contract for objects created later by the role
    # that executes Alembic. Application grants remain migration-controlled so
    # a new tenant table can never become reachable before RLS is installed.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rotas_admin"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO rotas_admin"
    )


def downgrade() -> None:
    # Security-forward migration: removing these grants would break platform
    # operations and cross-tenant background jobs.
    pass
