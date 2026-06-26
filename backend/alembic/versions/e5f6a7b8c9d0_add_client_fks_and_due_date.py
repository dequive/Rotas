"""add client_id FK to contracts and billing_documents; add due_date (migration b — DDL only)

Revision ID: e5f6a7b8c9d0
Revises: 22fbf8416463
Create Date: 2026-06-19

NOTE: Plan 05-02 specified revision b2c3d4e5f6a7, but that ID is already taken by
ensure_rls_roles_can_login.py. Using e5f6a7b8c9d0 instead.

The down_revision is 22fbf8416463 (merge_clients_and_workshop_expansion), not
a1b2c3d4e5f6 as in the plan spec — the actual head after Plan 01 is the merge commit.

PITFALL: client_id is nullable — the backfill (migration c/f6a7b8c9d0e1) runs after this.
PITFALL: Never add NOT NULL constraint here — backfill must complete first.
PITFALL: due_date must be added here (not in Phase 7) — aging needs it from day one.
         Key Decision in STATE.md: 'due_date added in Phase 5 migration (b) alongside client_id — not in Phase 7'
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "22fbf8416463"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- contracts ---
    op.add_column("contracts", sa.Column("client_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_contracts_client_id",
        "contracts",
        "clients",
        ["client_id"],
        ["id"],
    )
    op.create_index("ix_contracts_client_id", "contracts", ["client_id"])

    # --- billing_documents ---
    op.add_column("billing_documents", sa.Column("client_id", UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_billing_documents_client_id",
        "billing_documents",
        "clients",
        ["client_id"],
        ["id"],
    )
    op.create_index("ix_billing_documents_client_id", "billing_documents", ["client_id"])

    op.add_column(
        "billing_documents",
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_billing_documents_due_date", "billing_documents", ["due_date"])

    # Composite index for Phase 7 aging queries — add now while columns are created
    op.create_index(
        "ix_billing_documents_tenant_client_due",
        "billing_documents",
        ["tenant_id", "client_id", "due_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_billing_documents_tenant_client_due", table_name="billing_documents")
    op.drop_index("ix_billing_documents_due_date", table_name="billing_documents")
    op.drop_column("billing_documents", "due_date")
    op.drop_constraint("fk_billing_documents_client_id", "billing_documents", type_="foreignkey")
    op.drop_index("ix_billing_documents_client_id", table_name="billing_documents")
    op.drop_column("billing_documents", "client_id")

    op.drop_constraint("fk_contracts_client_id", "contracts", type_="foreignkey")
    op.drop_index("ix_contracts_client_id", table_name="contracts")
    op.drop_column("contracts", "client_id")
