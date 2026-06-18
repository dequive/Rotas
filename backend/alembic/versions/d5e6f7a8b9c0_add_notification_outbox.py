"""add_notification_outbox

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-17 00:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_reference", sa.String(length=160), nullable=False),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("template", sa.String(length=80), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "request_reference",
            name="uq_notification_outbox_tenant_request_reference",
        ),
    )
    op.create_index("ix_notification_outbox_tenant_id", "notification_outbox", ["tenant_id"])
    op.create_index(
        "ix_notification_outbox_request_reference",
        "notification_outbox",
        ["request_reference"],
    )
    op.create_index("ix_notification_outbox_channel", "notification_outbox", ["channel"])
    op.create_index("ix_notification_outbox_recipient", "notification_outbox", ["recipient"])
    op.create_index("ix_notification_outbox_template", "notification_outbox", ["template"])
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])
    op.create_index("ix_notification_outbox_scheduled_at", "notification_outbox", ["scheduled_at"])

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON notification_outbox TO rotas_app")
    op.execute("ALTER TABLE notification_outbox ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notification_outbox FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON notification_outbox
        USING (tenant_id::text = current_setting('app.tenant_id', true))
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notification_outbox")
    op.drop_index("ix_notification_outbox_scheduled_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_template", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_recipient", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_channel", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_request_reference", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_tenant_id", table_name="notification_outbox")
    op.drop_table("notification_outbox")
