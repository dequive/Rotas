"""add_third_party_tables

Revision ID: tp01b
Revises: tp01a
Create Date: 2026-06-19
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "tp01b"
down_revision = "tp01a"
branch_labels = None
depends_on = None


def _rls(table: str) -> None:
    """Apply v2.0 RLS rules to a tenant-scoped table."""
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO rotas_app")
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY tenant_isolation ON {table} "
        f"USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )


def upgrade() -> None:
    # ── third_parties ────────────────────────────────────────────────────────
    op.create_table(
        "third_parties",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("trade_name", sa.String(160), nullable=True),
        sa.Column("legal_type", sa.String(40), nullable=True, server_default="company"),
        sa.Column("nuit", sa.String(9), nullable=True),
        sa.Column("contact_email", sa.String(200), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column(
            "province_code",
            sa.String(10),
            sa.ForeignKey("mz_provinces.code"),
            nullable=True,
        ),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "verified_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
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
    )
    op.create_index("ix_third_parties_tenant_id", "third_parties", ["tenant_id"])
    op.create_index("ix_third_parties_tenant_status", "third_parties", ["tenant_id", "status"])
    op.create_unique_constraint(
        "uq_third_parties_tenant_nuit", "third_parties", ["tenant_id", "nuit"]
    )
    _rls("third_parties")

    # ── third_party_roles ────────────────────────────────────────────────────
    op.create_table(
        "third_party_roles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role_type", sa.String(40), nullable=False),
        # role_type values: fuel_supplier | spare_parts_supplier | service_provider | transport_subcontractor
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("certified_at", sa.Date, nullable=True),
        sa.Column("certification_ref", sa.String(120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_third_party_roles_tenant_id", "third_party_roles", ["tenant_id"])
    op.create_index("ix_third_party_roles_third_party_id", "third_party_roles", ["third_party_id"])
    op.create_unique_constraint(
        "uq_third_party_roles_tp_role",
        "third_party_roles",
        ["third_party_id", "role_type"],
    )
    _rls("third_party_roles")

    # ── supplier_profiles ────────────────────────────────────────────────────
    op.create_table(
        "supplier_profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("payment_terms", sa.String(60), nullable=True),
        sa.Column(
            "preferred_currency",
            sa.String(3),
            nullable=True,
            server_default="MZN",
        ),
        sa.Column("credit_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("account_number", sa.String(60), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
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
    )
    op.create_index("ix_supplier_profiles_tenant_id", "supplier_profiles", ["tenant_id"])
    _rls("supplier_profiles")

    # ── service_provider_profiles ────────────────────────────────────────────
    op.create_table(
        "service_provider_profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "third_party_id",
            UUID(as_uuid=True),
            sa.ForeignKey("third_parties.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("service_categories", JSONB, nullable=True),
        sa.Column("coverage_province_codes", JSONB, nullable=True),
        sa.Column("response_time_hours", sa.Integer, nullable=True),
        sa.Column("rate_per_hour", sa.Numeric(10, 2), nullable=True),
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
    )
    op.create_index(
        "ix_service_provider_profiles_tenant_id",
        "service_provider_profiles",
        ["tenant_id"],
    )
    _rls("service_provider_profiles")


def downgrade() -> None:
    for tbl in [
        "service_provider_profiles",
        "supplier_profiles",
        "third_party_roles",
        "third_parties",
    ]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl}")
        op.drop_table(tbl)
