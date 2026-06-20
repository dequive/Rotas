"""add_supplier_evaluations

Revision ID: tp09
Revises: tp08
Branch_labels: None
Depends_on: None
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "tp09"
down_revision = "tp08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "supplier_evaluations",
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
            sa.ForeignKey("third_parties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "evaluated_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("evaluation_date", sa.Date, nullable=False),
        sa.Column("criteria", JSONB, nullable=False),
        # criteria shape: [{"name": "prazo_entrega", "weight": 0.4, "score": 8.0}, ...]
        # weight values must sum to 1.0; score is 0-10 scale
        sa.Column("score", sa.Numeric(4, 2), nullable=False),
        # score = sum(criterion.weight * criterion.score) for all criteria
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("score >= 0 AND score <= 10", name="ck_se_score_range"),
    )
    op.create_index(
        "ix_se_tenant_party",
        "supplier_evaluations",
        ["tenant_id", "third_party_id"],
    )
    op.create_index(
        "ix_se_evaluation_date",
        "supplier_evaluations",
        ["tenant_id", "evaluation_date"],
    )

    # v2.0 RLS rules
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON supplier_evaluations TO rotas_app")
    op.execute("ALTER TABLE supplier_evaluations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE supplier_evaluations FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_isolation ON supplier_evaluations
           USING (tenant_id::text = current_setting('app.tenant_id', true))"""
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON supplier_evaluations")
    op.drop_index("ix_se_evaluation_date", table_name="supplier_evaluations")
    op.drop_index("ix_se_tenant_party", table_name="supplier_evaluations")
    op.drop_table("supplier_evaluations")
