"""add_rls_to_export_jobs

Gap-closure: export_jobs table was created in migration d4e5f6a7b8c9 on a parallel branch
before the RLS migration (4b0a7802dc3c) ran. The GRANT...ON ALL TABLES in the RLS migration
only applies to tables existing at that migration's execution time. This migration:
1. Enables RLS on export_jobs
2. Creates tenant_isolation policy (idempotent via DO block)
3. Grants rotas_app role read/write on export_jobs

Revision ID: e1f2a3b4c5d6
Revises: 147542222231
Create Date: 2026-06-07
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | None = "147542222231"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # export_jobs has tenant_id but was created on a parallel migration branch.
    # The RLS migration (4b0a7802dc3c) only covered tables existing at its run time.
    # GRANT...ON ALL TABLES in that migration also does not cover tables created after it.
    op.execute("ALTER TABLE export_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE export_jobs FORCE ROW LEVEL SECURITY")
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE tablename = 'export_jobs' AND policyname = 'tenant_isolation'
            ) THEN
                EXECUTE 'CREATE POLICY tenant_isolation ON export_jobs
                    USING (tenant_id::text = current_setting(''app.tenant_id'', true))';
            END IF;
        END $$
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON export_jobs TO rotas_app")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO rotas_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON export_jobs")
    op.execute("ALTER TABLE export_jobs DISABLE ROW LEVEL SECURITY")
