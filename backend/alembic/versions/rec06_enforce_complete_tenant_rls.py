"""Enforce complete tenant RLS coverage with the restricted application role.

Revision ID: rec06
Revises: d8a499250d84
Create Date: 2026-07-23 12:10:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec06"
down_revision: str | None = "d8a499250d84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Passwords remain an infrastructure secret; the migration only guarantees
    # that the application role exists and can never bypass row security.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rotas_app') THEN
                CREATE ROLE rotas_app NOINHERIT NOBYPASSRLS;
            END IF;
        END
        $$;
        """
    )
    op.execute("ALTER ROLE rotas_app NOBYPASSRLS")
    op.execute("ALTER ROLE rotas_app SET search_path = public")
    op.execute("GRANT USAGE ON SCHEMA public TO rotas_app")
    op.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rotas_app")
    op.execute("GRANT SELECT ON tenants TO rotas_app")

    # Reconcile every current tenant table, including files. Partition children
    # inherit enforcement from the partitioned parent and are deliberately skipped.
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

                -- PostgreSQL combines permissive policies with OR. Remove legacy
                -- policy names before installing the single canonical policy.
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
    # Security-forward migration: changing the revision must not silently
    # disable tenant isolation or restore permissive legacy policies.
    pass
