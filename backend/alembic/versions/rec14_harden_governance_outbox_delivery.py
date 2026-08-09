"""Harden Governance outbox delivery, replay and reconciliation.

Revision ID: rec14
Revises: rec13
Create Date: 2026-08-09 21:30:00+02:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "rec14"
down_revision: str | None = "rec13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Restart-safe because the original production schema is long-lived and may
    # already contain operational hotfix columns or indexes.
    op.execute(
        "ALTER TABLE outbox_events "
        "ADD COLUMN IF NOT EXISTS governance_occurrence_id uuid, "
        "ADD COLUMN IF NOT EXISTS reconciled_at timestamptz, "
        "ADD COLUMN IF NOT EXISTS reconciliation_attempt_count integer NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS next_reconciliation_at timestamptz, "
        "ADD COLUMN IF NOT EXISTS reconciliation_error text, "
        "ADD COLUMN IF NOT EXISTS claimed_at timestamptz, "
        "ADD COLUMN IF NOT EXISTS claim_expires_at timestamptz, "
        "ADD COLUMN IF NOT EXISTS claimed_by varchar(128), "
        "ADD COLUMN IF NOT EXISTS dead_lettered_at timestamptz, "
        "ADD COLUMN IF NOT EXISTS replay_count integer NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS last_replayed_at timestamptz, "
        "ADD COLUMN IF NOT EXISTS replayed_by varchar(128), "
        "ADD COLUMN IF NOT EXISTS replay_reason text"
    )
    op.execute("ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS total_attempt_count integer NOT NULL DEFAULT 0")
    op.execute(
        "UPDATE outbox_events SET total_attempt_count = attempt_count "
        "WHERE total_attempt_count = 0 AND attempt_count > 0"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_outbox_events_dispatch ON outbox_events (status, next_attempt_at, created_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_outbox_events_claim_expiry ON outbox_events (status, claim_expires_at)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_outbox_events_status'
                  AND conrelid = 'outbox_events'::regclass
            ) THEN
                ALTER TABLE outbox_events
                ADD CONSTRAINT ck_outbox_events_status
                CHECK (status IN ('pending', 'processing', 'sent', 'dead_letter'));
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    # Forward-only operational hardening: delivery audit and replay provenance
    # must not be erased by a rollback.
    pass
