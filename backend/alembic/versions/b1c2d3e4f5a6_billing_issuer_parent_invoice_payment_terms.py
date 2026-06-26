"""billing: add issuer_name/issuer_nuit/parent_invoice_number to billing_documents; payment_terms_days to contracts

Revision ID: b1c2d3e4f5a6
Revises: restore_composite_indexes
Create Date: 2026-06-20

CME — production hardening:
- billing_documents.issuer_name (String 200, nullable): tenant company name snapshotted at document creation
- billing_documents.issuer_nuit (String 20, nullable): tenant NUIT snapshotted at document creation
- billing_documents.parent_invoice_number (String 12, nullable): human-readable parent invoice number
  for child documents (debit/credit notes, receipts) — avoids JOIN for PDF/XLSX rendering
- contracts.payment_terms_days (Integer, NOT NULL, default 30): used by issue_document to compute due_date
"""

import sqlalchemy as sa

from alembic import op

revision = "b1c2d3e4f5a6"
down_revision = "restore_composite_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "billing_documents",
        sa.Column("issuer_name", sa.String(200), nullable=True),
    )
    op.add_column(
        "billing_documents",
        sa.Column("issuer_nuit", sa.String(20), nullable=True),
    )
    op.add_column(
        "billing_documents",
        sa.Column("parent_invoice_number", sa.String(12), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column(
            "payment_terms_days",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
    )


def downgrade() -> None:
    op.drop_column("contracts", "payment_terms_days")
    op.drop_column("billing_documents", "parent_invoice_number")
    op.drop_column("billing_documents", "issuer_nuit")
    op.drop_column("billing_documents", "issuer_name")
