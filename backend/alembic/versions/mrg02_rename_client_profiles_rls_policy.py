"""rename_client_profiles_rls_policy

Revision ID: mrg02
Revises: mrg01
Create Date: 2026-06-22

gt01 created policy named rls_client_profiles. Project convention (enforced
by test_rls.py) requires policyname = 'tenant_isolation' on all tenant tables.
"""

from alembic import op

revision = "mrg02"
down_revision = "mrg01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER POLICY rls_client_profiles ON client_profiles RENAME TO tenant_isolation")


def downgrade() -> None:
    op.execute("ALTER POLICY tenant_isolation ON client_profiles RENAME TO rls_client_profiles")
