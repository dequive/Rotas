"""create_contract_tariffs

Revision ID: 59b4ff8cbb9b
Revises: gps01
Create Date: 2026-06-26 13:40:20.329654+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "59b4ff8cbb9b"
down_revision: str | None = "gps01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── contract_tariffs ──────────────────────────────────────────────────────
    op.create_table(
        "contract_tariffs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.UUID(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "contract_id",
            sa.UUID(),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "known_route_id",
            sa.UUID(),
            sa.ForeignKey("known_routes.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("rate_basis", sa.String(40), nullable=False, server_default="trip"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MZN"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "contract_id",
            "known_route_id",
            name="uq_contract_tariffs_tenant_contract_route",
        ),
    )

    op.execute("ALTER TABLE contract_tariffs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE contract_tariffs FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON contract_tariffs "
        "USING (tenant_id::text = current_setting('app.tenant_id', true))"
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON contract_tariffs TO rotas_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON contract_tariffs")
    op.drop_table("contract_tariffs")
