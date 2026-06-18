"""SM-01 SM-02: Add state machine fields to billing_documents and contracts

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-06-18

SM-01: BillingDocument — add overdue_since_at, cancellation_reason
       (paid_at already exists — no action needed)
SM-02: Contract — add paused_at, terminated_at, termination_reason, renewed_at
"""
from alembic import op
import sqlalchemy as sa

revision: str = "e9f8d7c6b5a4"
down_revision: str = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SM-01: BillingDocument — add overdue and cancellation fields
    # Note: paid_at already exists in billing_documents — skip
    op.add_column(
        "billing_documents",
        sa.Column("overdue_since_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "billing_documents",
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
    )

    # SM-02: Contract — add state machine audit timestamp fields
    op.add_column(
        "contracts",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("termination_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "contracts",
        sa.Column("renewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("billing_documents", "overdue_since_at")
    op.drop_column("billing_documents", "cancellation_reason")
    op.drop_column("contracts", "paused_at")
    op.drop_column("contracts", "terminated_at")
    op.drop_column("contracts", "termination_reason")
    op.drop_column("contracts", "renewed_at")
