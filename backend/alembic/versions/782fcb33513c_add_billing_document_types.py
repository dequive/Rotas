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
    # document_type, parent_document_id, due_date, FK + parent index already
    # exist from a prior Phase 5 migration — only add what's missing.
    op.add_column(
        "billing_documents",
        sa.Column("client_nuit", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_billing_documents_document_type",
        "billing_documents",
        ["document_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_documents_document_type", table_name="billing_documents")
    op.drop_column("billing_documents", "client_nuit")
