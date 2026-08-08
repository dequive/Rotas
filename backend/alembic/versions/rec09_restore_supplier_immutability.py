"""Restore immutable supplier ledger and evaluation triggers.

Revision ID: rec09
Revises: rec08
Create Date: 2026-07-25 23:05:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec09"
down_revision: str | None = "rec08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION raise_immutable_ledger()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'supplier_ledger_entries are immutable — reverse with a new entry';
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_sle_immutable ON supplier_ledger_entries")
    op.execute(
        """
        CREATE TRIGGER trg_sle_immutable
          BEFORE UPDATE OR DELETE ON supplier_ledger_entries
          FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION raise_immutable_evaluation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'supplier_evaluations are immutable — submit a new evaluation to supersede';
        END;
        $$;
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_se_immutable ON supplier_evaluations")
    op.execute(
        """
        CREATE TRIGGER trg_se_immutable
          BEFORE UPDATE OR DELETE ON supplier_evaluations
          FOR EACH ROW EXECUTE FUNCTION raise_immutable_evaluation()
        """
    )


def downgrade() -> None:
    # Security-forward: immutable financial/evaluation records stay immutable.
    pass
