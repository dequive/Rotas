"""add_rls_to_maintenance_request_notes

Revision ID: 7933d20ec33b
Revises: 242a7399301b
Create Date: 2026-06-27 17:11:09.123456+02:00

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7933d20ec33b'
down_revision: str | None = '242a7399301b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE maintenance_request_notes ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE maintenance_request_notes FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY tenant_isolation ON maintenance_request_notes "
        "AS RESTRICTIVE USING (tenant_id = current_setting('app.tenant_id')::uuid);"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON maintenance_request_notes;")
    op.execute("ALTER TABLE maintenance_request_notes NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE maintenance_request_notes DISABLE ROW LEVEL SECURITY;")
