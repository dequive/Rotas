"""Scope occurrence and case human identifiers by tenant.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-09
"""

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("occurrences_numero_key", "occurrences", type_="unique")
    op.create_unique_constraint(
        "uq_occurrences_tenant_numero",
        "occurrences",
        ["tenant_id", "numero"],
    )
    op.drop_constraint("cases_reference_key", "cases", type_="unique")
    op.create_unique_constraint(
        "uq_cases_tenant_reference",
        "cases",
        ["tenant_id", "reference"],
    )


def downgrade() -> None:
    # This intentionally fails if multiple tenants already share a human ID;
    # collapsing tenant scope would otherwise make the downgrade destructive.
    op.drop_constraint("uq_cases_tenant_reference", "cases", type_="unique")
    op.create_unique_constraint("cases_reference_key", "cases", ["reference"])
    op.drop_constraint("uq_occurrences_tenant_numero", "occurrences", type_="unique")
    op.create_unique_constraint("occurrences_numero_key", "occurrences", ["numero"])
