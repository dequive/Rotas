"""add client_profiles table and clients.third_party_id FK

Revision ID: gt01
Revises: adv03
Create Date: 2026-06-21

CRITICAL: RLS + GRANT are co-located in this CREATE TABLE migration per v2.0 migration rule.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision = "gt01"
down_revision = "adv03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. CREATE TABLE client_profiles
    op.create_table(
        "client_profiles",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "third_party_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("payment_terms_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("preferred_currency", sa.String(3), nullable=True, server_default="MZN"),
        sa.Column("billing_email", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 2. RLS + GRANT for client_profiles (v2.0 rule: same migration as CREATE TABLE)
    op.execute("ALTER TABLE client_profiles ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE client_profiles FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY rls_client_profiles ON client_profiles "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON client_profiles TO rotas_app")

    # 3. ADD COLUMN clients.third_party_id (nullable — backfill populates it in gt02)
    op.add_column(
        "clients",
        sa.Column(
            "third_party_id",
            PG_UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_clients_third_party_id", "clients", ["third_party_id"])


def downgrade() -> None:
    op.drop_index("ix_clients_third_party_id", table_name="clients")
    op.drop_column("clients", "third_party_id")
    op.execute("DROP POLICY IF EXISTS rls_client_profiles ON client_profiles")
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON client_profiles FROM rotas_app")
    op.drop_table("client_profiles")
