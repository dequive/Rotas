"""add_third_party_contacts_and_fields

Revision ID: tp07
Revises: b1c2d3e4f5a6
Branch_labels: None
Depends_on: None
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "tp07"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Additive columns on third_parties (nullable, backwards-compatible)
    op.add_column("third_parties", sa.Column("activity_code", sa.String(20), nullable=True))
    op.add_column("third_parties", sa.Column("sector", sa.String(80), nullable=True))

    # 2. third_party_contacts table
    op.create_table(
        "third_party_contacts",
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
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(80), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(160), nullable=True),
        sa.Column(
            "is_primary",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_tpc_tenant_party",
        "third_party_contacts",
        ["tenant_id", "third_party_id"],
    )

    # v2.0 RLS rules — mandatory for all tenant_id tables
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON third_party_contacts TO rotas_app")
    op.execute("ALTER TABLE third_party_contacts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE third_party_contacts FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON third_party_contacts
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON third_party_contacts")
    op.drop_index("ix_tpc_tenant_party", table_name="third_party_contacts")
    op.drop_table("third_party_contacts")
    op.drop_column("third_parties", "sector")
    op.drop_column("third_parties", "activity_code")
