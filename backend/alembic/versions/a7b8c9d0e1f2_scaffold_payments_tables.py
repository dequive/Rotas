"""scaffold client_payments and payment_allocations tables (migration d — DDL only)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-19

NOTE: Plan 05-02 specified revision d4e5f6a7b8c9, but that ID is already taken by
add_export_jobs_table.py. Using a7b8c9d0e1f2 instead.

Phase 5 scaffolds full schema here so Phase 6 only adds service + router.
PITFALL (from RESEARCH.md): Retrofitting payment_allocations after payment rows exist
is a high-risk migration — creating both tables now prevents this.

client_payments.billing_document_id is nullable — supports advance payments.
payment_allocations: junction table linking client_payments to billing_documents.

v2.0 Migration Rules: RLS + GRANT co-located in this migration (MANDATORY per CLAUDE.md).
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "f6a7b8c9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id"),
            nullable=False,
        ),
        # billing_document_id is nullable — advance payments have no invoice at creation
        sa.Column(
            "billing_document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("billing_documents.id"),
            nullable=True,
        ),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MZN"),
        sa.Column("value_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_method", sa.String(40), nullable=False),  # bank_transfer|cheque|cash
        sa.Column("reference", sa.String(120), nullable=True),  # bank ref, cheque number
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="confirmed",
        ),  # confirmed|voided
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "voided_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_client_payments_tenant_id", "client_payments", ["tenant_id"])
    op.create_index("ix_client_payments_client_id", "client_payments", ["client_id"])
    op.create_index(
        "ix_client_payments_billing_document_id",
        "client_payments",
        ["billing_document_id"],
    )
    op.create_index(
        "ix_client_payments_tenant_client",
        "client_payments",
        ["tenant_id", "client_id"],
    )

    op.create_table(
        "payment_allocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "payment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("client_payments.id"),
            nullable=False,
        ),
        sa.Column(
            "billing_document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("billing_documents.id"),
            nullable=False,
        ),
        sa.Column("amount_applied", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_payment_allocations_tenant_id", "payment_allocations", ["tenant_id"])
    op.create_index("ix_payment_allocations_payment_id", "payment_allocations", ["payment_id"])
    op.create_index(
        "ix_payment_allocations_billing_document_id",
        "payment_allocations",
        ["billing_document_id"],
    )

    # v2.0 Migration Rules — RLS + GRANT in same CREATE TABLE migration (MANDATORY per CLAUDE.md)
    for table in ("client_payments", "payment_allocations"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app")  # noqa: S608
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_isolation ON {table}
               USING (tenant_id::text = current_setting('app.tenant_id', true))"""
        )


def downgrade() -> None:
    for table in ("payment_allocations", "client_payments"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.drop_table(table)
