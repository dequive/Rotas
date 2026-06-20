"""immutability_triggers_for_ledger_and_evaluations

Revision ID: tp11
Revises: tp10
Branch_labels: None
Depends_on: None
"""

from alembic import op

revision = "tp11"
down_revision = "tp10"
branch_labels = None
depends_on = None


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
    op.execute(
        """
        CREATE TRIGGER trg_sle_immutable
          BEFORE UPDATE OR DELETE ON supplier_ledger_entries
          FOR EACH ROW EXECUTE FUNCTION raise_immutable_ledger();
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
    op.execute(
        """
        CREATE TRIGGER trg_se_immutable
          BEFORE UPDATE OR DELETE ON supplier_evaluations
          FOR EACH ROW EXECUTE FUNCTION raise_immutable_evaluation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sle_immutable ON supplier_ledger_entries")
    op.execute("DROP FUNCTION IF EXISTS raise_immutable_ledger()")
    op.execute("DROP TRIGGER IF EXISTS trg_se_immutable ON supplier_evaluations")
    op.execute("DROP FUNCTION IF EXISTS raise_immutable_evaluation()")
