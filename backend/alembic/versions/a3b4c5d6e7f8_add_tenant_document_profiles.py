"""add_tenant_document_profiles

Revision ID: a3b4c5d6e7f8
Revises: ins01
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a3b4c5d6e7f8"
down_revision: str | None = "e1a2b3c4d5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant_document_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            unique=True,
            nullable=False,
            index=True,
        ),
        sa.Column(
            "logo_file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("files.id"),
            nullable=True,
        ),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("address_line1", sa.String(160), nullable=True),
        sa.Column("address_line2", sa.String(160), nullable=True),
        sa.Column("city", sa.String(80), nullable=True),
        sa.Column("province", sa.String(80), nullable=True),
        sa.Column("country", sa.String(80), nullable=False, server_default="Moçambique"),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(120), nullable=True),
        sa.Column("website", sa.String(160), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("bank_account", sa.String(60), nullable=True),
        sa.Column("bank_nib", sa.String(60), nullable=True),
        sa.Column("invoice_prefix", sa.String(10), nullable=False, server_default=""),
        sa.Column("invoice_seq_padding", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("invoice_start_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("per_type_sequences", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("payment_conditions", sa.String(80), nullable=False, server_default="Pronto"),
        sa.Column("invoice_footer", sa.Text(), nullable=True),
        sa.Column("show_bank_details", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("show_logo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_tenant_document_profiles_tenant_id "
        "ON tenant_document_profiles (tenant_id)"
    )
    # v2.0 Migration Rules — MANDATORY RLS + GRANT in same migration as CREATE TABLE
    op.execute("ALTER TABLE tenant_document_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_document_profiles FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_tenant_document_profiles ON tenant_document_profiles "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_document_profiles TO rotas_app"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS rls_tenant_document_profiles ON tenant_document_profiles"
    )
    op.drop_index(
        "ix_tenant_document_profiles_tenant_id", table_name="tenant_document_profiles"
    )
    op.drop_table("tenant_document_profiles")
