"""Create the Payables aggregate tables.

Revision ID: e800073e1feb
Revises: 7933d20ec33b
Create Date: 2026-06-27 19:57:55.429037+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e800073e1feb"
down_revision: str | None = "7933d20ec33b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("third_party_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=True),
        sa.Column("po_number", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("estimated_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["third_party_id"], ["third_parties.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_orders_tenant_id", "purchase_orders", ["tenant_id"])
    op.create_index("ix_purchase_orders_third_party_id", "purchase_orders", ["third_party_id"])
    op.create_index("ix_purchase_orders_work_order_id", "purchase_orders", ["work_order_id"])
    op.create_index(
        "ix_purchase_orders_tenant_third_party",
        "purchase_orders",
        ["tenant_id", "third_party_id"],
    )

    op.create_table(
        "supplier_invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("third_party_id", sa.UUID(), nullable=False),
        sa.Column("work_order_id", sa.UUID(), nullable=True),
        sa.Column("invoice_number", sa.String(length=120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("file_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["third_party_id"], ["third_parties.id"]),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_invoices_tenant_id", "supplier_invoices", ["tenant_id"])
    op.create_index(
        "ix_supplier_invoices_third_party_id",
        "supplier_invoices",
        ["third_party_id"],
    )
    op.create_index(
        "ix_supplier_invoices_work_order_id",
        "supplier_invoices",
        ["work_order_id"],
    )
    op.create_index(
        "ix_supplier_invoices_tenant_third_party",
        "supplier_invoices",
        ["tenant_id", "third_party_id"],
    )

    op.create_table(
        "supplier_payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("third_party_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("value_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["third_party_id"], ["third_parties.id"]),
        sa.ForeignKeyConstraint(["invoice_id"], ["supplier_invoices.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_supplier_payments_tenant_id", "supplier_payments", ["tenant_id"])
    op.create_index(
        "ix_supplier_payments_third_party_id",
        "supplier_payments",
        ["third_party_id"],
    )
    op.create_index("ix_supplier_payments_invoice_id", "supplier_payments", ["invoice_id"])
    op.create_index(
        "ix_supplier_payments_tenant_third_party",
        "supplier_payments",
        ["tenant_id", "third_party_id"],
    )


def downgrade() -> None:
    op.drop_table("supplier_payments")
    op.drop_table("supplier_invoices")
    op.drop_table("purchase_orders")
