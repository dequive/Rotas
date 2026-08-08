"""add_billing_document_types

Revision ID: 782fcb33513c
Revises: a7b8c9d0e1f2
Create Date: 2026-06-19

FDOC-01: Add document_type, parent_document_id, due_date, client_nuit
to billing_documents for fiscal document type discrimination and AR tracking.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "782fcb33513c"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the fiscal-document discriminator fields missing from the baseline.

    Earlier versions of this migration assumed these columns had been created
    by Phase 5, but the canonical migration chain never created them. Inspecting
    first keeps the upgrade safe for databases where the fields were added
    manually before this correction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("billing_documents")}

    if "document_type" not in columns:
        op.add_column(
            "billing_documents",
            sa.Column(
                "document_type",
                sa.String(length=30),
                nullable=False,
                server_default="invoice",
            ),
        )
    if "parent_document_id" not in columns:
        op.add_column(
            "billing_documents",
            sa.Column("parent_document_id", sa.UUID(), nullable=True),
        )
    if "client_nuit" not in columns:
        op.add_column(
            "billing_documents",
            sa.Column("client_nuit", sa.String(length=20), nullable=True),
        )

    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("billing_documents")}
    if "ix_billing_documents_document_type" not in indexes:
        op.create_index(
            "ix_billing_documents_document_type",
            "billing_documents",
            ["document_type"],
        )
    if "ix_billing_documents_parent_document_id" not in indexes:
        op.create_index(
            "ix_billing_documents_parent_document_id",
            "billing_documents",
            ["parent_document_id"],
        )

    foreign_keys = {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys("billing_documents")
    }
    if "fk_billing_documents_parent" not in foreign_keys:
        op.create_foreign_key(
            "fk_billing_documents_parent",
            "billing_documents",
            "billing_documents",
            ["parent_document_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_billing_documents_parent",
        "billing_documents",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_billing_documents_parent_document_id",
        table_name="billing_documents",
    )
    op.drop_index("ix_billing_documents_document_type", table_name="billing_documents")
    op.drop_column("billing_documents", "client_nuit")
    op.drop_column("billing_documents", "parent_document_id")
    op.drop_column("billing_documents", "document_type")
