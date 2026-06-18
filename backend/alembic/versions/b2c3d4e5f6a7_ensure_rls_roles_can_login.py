"""ensure_rls_roles_can_login

Revision ID: b2c3d4e5f6a7
Revises: a9b8c7d6e5f4
Create Date: 2026-06-16
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a9b8c7d6e5f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER ROLE rotas_app LOGIN")
    op.execute("ALTER ROLE rotas_admin LOGIN")


def downgrade() -> None:
    # Keep LOGIN on downgrade. Removing it would break running app and migration users.
    pass
