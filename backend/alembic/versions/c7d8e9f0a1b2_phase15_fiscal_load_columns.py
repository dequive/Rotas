"""Phase 15: fiscal compliance columns + per-tenant invoice sequences.

Adds:
- billing_documents: invoice_number, iva_rate
- billing_items: iva_rate, iva_amount
- vehicles: max_payload_kg
- trips: payload_override_reason, is_hazmat, hazmat_class, un_number, hazmat_label
- cargo_manifests: is_hazmat, hazmat_class, un_number, hazmat_label
- contracts: client_nuit
- tenants: nuit
- PostgreSQL SEQUENCE invoice_seq_{tid_no_hyphens}_{year} for all existing tenants

Revision ID: c7d8e9f0a1b2
Revises: b9c8d7e6f5a4
Create Date: 2026-06-18
"""

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: str | None = "b9c8d7e6f5a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. billing_documents — invoice_number + unique constraint + iva_rate
    op.add_column(
        "billing_documents",
        sa.Column("invoice_number", sa.String(12), nullable=True),
    )
    op.create_unique_constraint(
        "uq_billing_docs_tenant_invoice_number",
        "billing_documents",
        ["tenant_id", "invoice_number"],
    )
    op.add_column(
        "billing_documents",
        sa.Column("iva_rate", sa.Numeric(5, 4), nullable=True),
    )

    # 2. billing_items — iva_rate + iva_amount
    op.add_column(
        "billing_items",
        sa.Column("iva_rate", sa.Numeric(5, 4), nullable=True),
    )
    op.add_column(
        "billing_items",
        sa.Column("iva_amount", sa.Numeric(10, 2), nullable=True),
    )

    # 3. vehicles — max_payload_kg (nullable — backwards compat)
    op.add_column(
        "vehicles",
        sa.Column("max_payload_kg", sa.Numeric(10, 2), nullable=True),
    )

    # 4. trips — payload_override_reason + hazmat fields
    op.add_column(
        "trips",
        sa.Column("payload_override_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "trips",
        sa.Column("is_hazmat", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "trips",
        sa.Column("hazmat_class", sa.String(10), nullable=True),
    )
    op.add_column(
        "trips",
        sa.Column("un_number", sa.String(10), nullable=True),
    )
    op.add_column(
        "trips",
        sa.Column("hazmat_label", sa.String(50), nullable=True),
    )

    # 5. cargo_manifests — hazmat fields
    op.add_column(
        "cargo_manifests",
        sa.Column("is_hazmat", sa.Boolean(), server_default="false", nullable=False),
    )
    op.add_column(
        "cargo_manifests",
        sa.Column("hazmat_class", sa.String(10), nullable=True),
    )
    op.add_column(
        "cargo_manifests",
        sa.Column("un_number", sa.String(10), nullable=True),
    )
    op.add_column(
        "cargo_manifests",
        sa.Column("hazmat_label", sa.String(50), nullable=True),
    )

    # 6. contracts — client_nuit (for AT compliance report)
    op.add_column(
        "contracts",
        sa.Column("client_nuit", sa.String(20), nullable=True),
    )

    # 7. tenants — nuit
    op.add_column(
        "tenants",
        sa.Column("nuit", sa.String(20), nullable=True),
    )

    # 8. Create per-tenant per-year invoice sequences for ALL existing tenants.
    # PostgreSQL CREATE SEQUENCE is transactional DDL — safe inside this migration.
    # Lazy creation in service.py handles new tenants and future years.
    conn = op.get_bind()
    tenant_ids = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    year = 2026
    for (tid,) in tenant_ids:
        tid_clean = str(tid).replace("-", "")
        seq_name = f"invoice_seq_{tid_clean}_{year}"
        conn.execute(
            sa.text(f'CREATE SEQUENCE IF NOT EXISTS "{seq_name}" START 1 INCREMENT 1 CACHE 1')
        )


def downgrade() -> None:
    # NOTE: Per-tenant sequences are NOT dropped in downgrade — they are tenant data artifacts.
    # Drop them manually if needed: DROP SEQUENCE IF EXISTS "invoice_seq_{tid}_{year}";
    op.drop_column("tenants", "nuit")
    op.drop_column("contracts", "client_nuit")
    op.drop_column("cargo_manifests", "hazmat_label")
    op.drop_column("cargo_manifests", "un_number")
    op.drop_column("cargo_manifests", "hazmat_class")
    op.drop_column("cargo_manifests", "is_hazmat")
    op.drop_column("trips", "hazmat_label")
    op.drop_column("trips", "un_number")
    op.drop_column("trips", "hazmat_class")
    op.drop_column("trips", "is_hazmat")
    op.drop_column("trips", "payload_override_reason")
    op.drop_column("vehicles", "max_payload_kg")
    op.drop_column("billing_items", "iva_amount")
    op.drop_column("billing_items", "iva_rate")
    op.drop_constraint(
        "uq_billing_docs_tenant_invoice_number", "billing_documents", type_="unique"
    )
    op.drop_column("billing_documents", "iva_rate")
    op.drop_column("billing_documents", "invoice_number")
