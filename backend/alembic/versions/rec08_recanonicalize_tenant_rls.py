"""Re-canonicalize tenant RLS after later feature migrations.

Revision ID: rec08
Revises: opt01
Create Date: 2026-07-25 14:30:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec08"
down_revision: str | None = "opt01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A migration after rec06 briefly added a second permissive policy.
    # Reconcile every tenant table so PostgreSQL never combines tenant policies
    # with OR and so all current tables retain both read and write guards.
    op.execute(
        """
        DO $$
        DECLARE
            tenant_table record;
            existing_policy record;
        BEGIN
            FOR tenant_table IN
                SELECT
                    namespace.nspname AS schema_name,
                    relation.relname AS table_name,
                    format('%I.%I', namespace.nspname, relation.relname) AS qualified_name
                FROM pg_class AS relation
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname = 'public'
                  AND relation.relkind IN ('r', 'p')
                  AND NOT relation.relispartition
                  AND EXISTS (
                      SELECT 1
                      FROM pg_attribute AS attribute
                      WHERE attribute.attrelid = relation.oid
                        AND attribute.attname = 'tenant_id'
                        AND NOT attribute.attisdropped
                  )
            LOOP
                EXECUTE format(
                    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %s TO rotas_app',
                    tenant_table.qualified_name
                );
                EXECUTE format(
                    'ALTER TABLE %s ENABLE ROW LEVEL SECURITY',
                    tenant_table.qualified_name
                );
                EXECUTE format(
                    'ALTER TABLE %s FORCE ROW LEVEL SECURITY',
                    tenant_table.qualified_name
                );

                FOR existing_policy IN
                    SELECT policyname
                    FROM pg_policies
                    WHERE schemaname = tenant_table.schema_name
                      AND tablename = tenant_table.table_name
                LOOP
                    EXECUTE format(
                        'DROP POLICY %I ON %s',
                        existing_policy.policyname,
                        tenant_table.qualified_name
                    );
                END LOOP;

                EXECUTE format(
                    'CREATE POLICY tenant_isolation ON %s '
                    'AS PERMISSIVE FOR ALL TO rotas_app '
                    'USING (tenant_id::text = current_setting(''app.tenant_id'', true)) '
                    'WITH CHECK (tenant_id::text = current_setting(''app.tenant_id'', true))',
                    tenant_table.qualified_name
                );
            END LOOP;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Security-forward migration: never remove tenant isolation on downgrade.
    pass
