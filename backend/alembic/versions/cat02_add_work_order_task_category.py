"""add_work_order_task_category

Revision ID: cat02
Revises: rec07
Create Date: 2026-07-24 00:00:00.000000+02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "cat02"
down_revision: str | None = "rec07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "work_order_tasks",
        sa.Column("category", sa.String(length=40), nullable=True),
    )
    op.create_check_constraint(
        "chk_work_order_tasks_category",
        "work_order_tasks",
        sa.text(
            "category IN ('motor','travoes','suspensao','eletrica','pneus','revisao','chapa_pintura','outro')"
        ),
    )
def downgrade() -> None:
    op.drop_constraint("chk_work_order_tasks_category", "work_order_tasks", type_="check")
    op.drop_column("work_order_tasks", "category")
