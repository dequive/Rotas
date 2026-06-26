"""add_transport_doc_extra_fields

Revision ID: f5fe4c151bd1
Revises: 782fcb33513c
Create Date: 2026-06-19

OPDOC-01: Extend transport_documents with extra_fields JSONB for type-specific
metadata (border_post, sadc_cpi_number, authorization_code, etc.) plus
recipient_name and recipient_nuit for Guia de Remessa fiscal compliance.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "f5fe4c151bd1"
down_revision: str | None = "782fcb33513c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transport_documents",
        sa.Column("recipient_name", sa.String(length=160), nullable=True),
    )
    op.add_column(
        "transport_documents",
        sa.Column("recipient_nuit", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "transport_documents",
        sa.Column("extra_fields", JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transport_documents", "extra_fields")
    op.drop_column("transport_documents", "recipient_nuit")
    op.drop_column("transport_documents", "recipient_name")
