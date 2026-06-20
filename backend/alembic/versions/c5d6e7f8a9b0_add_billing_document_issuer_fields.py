"""add billing_document issuer snapshot fields

Revision ID: c5d6e7f8a9b0
Revises: a3b4c5d6e7f8
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "c5d6e7f8a9b0"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("billing_documents", sa.Column("issuer_address", sa.Text(), nullable=True))
    op.add_column("billing_documents", sa.Column("issuer_phone", sa.String(40), nullable=True))
    op.add_column("billing_documents", sa.Column("issuer_email", sa.String(120), nullable=True))
    op.add_column("billing_documents", sa.Column("issuer_city", sa.String(80), nullable=True))
    op.add_column("billing_documents", sa.Column("issuer_bank_details", sa.Text(), nullable=True))
    op.add_column("billing_documents", sa.Column("payment_conditions", sa.String(80), nullable=True))
    op.add_column("billing_documents", sa.Column("commercial_discount", sa.Numeric(5, 4), nullable=True, server_default="0"))
    op.add_column("billing_documents", sa.Column("financial_discount", sa.Numeric(5, 4), nullable=True, server_default="0"))


def downgrade():
    op.drop_column("billing_documents", "financial_discount")
    op.drop_column("billing_documents", "commercial_discount")
    op.drop_column("billing_documents", "payment_conditions")
    op.drop_column("billing_documents", "issuer_bank_details")
    op.drop_column("billing_documents", "issuer_city")
    op.drop_column("billing_documents", "issuer_email")
    op.drop_column("billing_documents", "issuer_phone")
    op.drop_column("billing_documents", "issuer_address")
