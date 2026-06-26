"""add_operational_documents

Revision ID: tp06
Revises: tp01b
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "tp06"
down_revision = "tp01b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operational_documents",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        # PartyRef pattern — polymorphic, no DB-level FK on subject_id
        sa.Column("subject_type", sa.String(30), nullable=False),
        # subject_type values: driver | vehicle | third_party | client | contract
        sa.Column("subject_id", UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(60), nullable=False),
        # document_type examples: license | passport | bi | insurance | inspection | contract_copy
        sa.Column(
            "file_id",
            UUID(as_uuid=True),
            sa.ForeignKey("files.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("document_number", sa.String(80), nullable=True),
        sa.Column("issued_at", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("issuing_authority", sa.String(160), nullable=True),
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="pending"),
        # verification_status values: pending | verified | rejected
        sa.Column(
            "verified_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Composite index supports list_documents(subject_type, subject_id) queries
    op.create_index(
        "ix_operational_documents_tenant_subject",
        "operational_documents",
        ["tenant_id", "subject_type", "subject_id"],
    )
    # Partial index for expiry scan (document expiry alert job)
    op.create_index(
        "ix_operational_documents_expiry_date",
        "operational_documents",
        ["expiry_date"],
        postgresql_where=sa.text("expiry_date IS NOT NULL"),
    )
    # Additional indexes for common query patterns
    op.create_index(
        "ix_operational_documents_tenant",
        "operational_documents",
        ["tenant_id"],
    )
    op.create_index(
        "ix_operational_documents_verification",
        "operational_documents",
        ["tenant_id", "verification_status"],
    )

    # v2.0 RLS rules — mandatory for all tenant_id tables in Phase 5+
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON operational_documents TO rotas_app")
    op.execute("ALTER TABLE operational_documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE operational_documents FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON operational_documents
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON operational_documents")
    op.drop_index("ix_operational_documents_verification", table_name="operational_documents")
    op.drop_index("ix_operational_documents_tenant", table_name="operational_documents")
    op.drop_index("ix_operational_documents_expiry_date", table_name="operational_documents")
    op.drop_index("ix_operational_documents_tenant_subject", table_name="operational_documents")
    op.drop_table("operational_documents")
