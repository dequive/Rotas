"""gap01: add tenant_isolation RLS policy to INS-01 + document-profile tables

Revision ID: gap01
Revises: a3b4c5d6e7f8
Create Date: 2026-06-21

These tables were created by bc18318 migration (ins01-era) with policy names
rls_vehicle_insurances / rls_insurance_claims / rls_tenant_document_profiles.
The RLS test expects policyname = 'tenant_isolation' (project convention).
This migration idempotently adds tenant_isolation policies.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "gap01"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("vehicle_insurances", "insurance_claims", "tenant_document_profiles"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies
                    WHERE tablename = '{table}' AND policyname = 'tenant_isolation'
                ) THEN
                    EXECUTE 'CREATE POLICY tenant_isolation ON {table}
                        USING (tenant_id::text = current_setting(''app.tenant_id'', true))';
                END IF;
            END $$;
            """
        )


def downgrade() -> None:
    for table in ("vehicle_insurances", "insurance_claims", "tenant_document_profiles"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
