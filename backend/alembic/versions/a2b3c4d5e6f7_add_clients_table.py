"""add clients table (migration a — DDL only)

Revision ID: a2b3c4d5e6f7
Revises: f4c8a12d9b30
Create Date: 2026-06-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "a2b3c4d5e6f7"
down_revision: str | None = "f4c8a12d9b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("trading_name", sa.String(160), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("nuit", sa.String(9), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "nuit", name="uq_clients_tenant_nuit"),
    )
    op.create_index("ix_clients_tenant_id", "clients", ["tenant_id"])
    op.create_index("ix_clients_trading_name_tenant", "clients", ["tenant_id", "trading_name"])

    # v2.0 Migration Rules — RLS + GRANT in same CREATE TABLE migration (MANDATORY)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON clients TO rotas_app")
    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON clients
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON clients")
    op.drop_index("ix_clients_trading_name_tenant", table_name="clients")
    op.drop_index("ix_clients_tenant_id", table_name="clients")
    op.drop_table("clients")
