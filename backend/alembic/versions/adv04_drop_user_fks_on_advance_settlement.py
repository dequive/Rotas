"""drop_user_fks_on_advance_settlement

Revision ID: adv04
Revises: adv03
Create Date: 2026-06-22

issued_by and approved_by are audit-trail UUID columns — soft references,
not enforced FKs. Matches audit_logs.user_id pattern (no FK in DB).
"""

from alembic import op

revision = "adv04"
down_revision = "adv03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE driver_advances DROP CONSTRAINT IF EXISTS driver_advances_issued_by_fkey"
    )
    op.execute(
        "ALTER TABLE trip_settlements DROP CONSTRAINT IF EXISTS trip_settlements_approved_by_fkey"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE driver_advances ADD CONSTRAINT driver_advances_issued_by_fkey "
        "FOREIGN KEY (issued_by) REFERENCES users(id)"
    )
    op.execute(
        "ALTER TABLE trip_settlements ADD CONSTRAINT trip_settlements_approved_by_fkey "
        "FOREIGN KEY (approved_by) REFERENCES users(id)"
    )
