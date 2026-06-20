"""add_platform_users_and_audit_logs

Revision ID: e1a2b3c4d5f6
Revises: tp11
Branch labels: None
Depends_on: None
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e1a2b3c4d5f6"
down_revision = "tp11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_users",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
    op.create_index("ix_platform_users_email", "platform_users", ["email"], unique=True)

    # INTENTIONALLY NO RLS on platform_users.
    # This table is platform-scoped, not tenant-scoped. RLS policies use app.tenant_id which
    # has no meaning here. Platform authentication uses direct PK lookups by platform_user_id
    # after JWT validation — no tenant context is ever set in the session for platform flows.
    # Access control is enforced at the application layer via require_platform_role().
    # GRANT is still required so rotas_app can read/write via the ORM.
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON platform_users TO rotas_app")

    op.create_table(
        "platform_audit_logs",
        sa.Column(
            "id",
            sa.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("actor_role", sa.String(50), nullable=False),
        sa.Column("target_tenant_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.UUID(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # INTENTIONALLY NO RLS on platform_audit_logs.
    # Platform audit logs record cross-tenant operator actions. They must be readable by
    # platform_admin without a tenant_id session variable set. RLS would block all reads.
    # Access control is enforced at the application layer via require_platform_role().
    op.execute("GRANT SELECT, INSERT ON platform_audit_logs TO rotas_app")
    op.create_index(
        "ix_platform_audit_logs_actor_id",
        "platform_audit_logs",
        ["actor_id"],
    )
    op.create_index(
        "ix_platform_audit_logs_target_tenant_id",
        "platform_audit_logs",
        ["target_tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_platform_audit_logs_target_tenant_id", table_name="platform_audit_logs")
    op.drop_index("ix_platform_audit_logs_actor_id", table_name="platform_audit_logs")
    op.drop_table("platform_audit_logs")
    op.drop_index("ix_platform_users_email", table_name="platform_users")
    op.drop_table("platform_users")
