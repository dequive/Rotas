"""Add HR and Inventory modules

Revision ID: 95929ae669b9
Revises: aaeadb9644c0
Create Date: 2026-06-28 21:18:10.609158+02:00

NOTES (stabilization/P0-F1):
- This migration originally ran with empty upgrade/downgrade bodies.
  Alembic still treats empty function bodies as IndentationError, so a
  placeholder ``pass`` is required to keep the tree parseable.
- Real DDL for HR, Inventory, Accounting description columns, and the
  transactional outbox lives in downstream migrations (see
  ``f4b0a59600_stabilization_p0_hr_inventory_accounting_outbox.py``).
- Reason for NOT rewriting this migration in place: production snapshots may
  have already stamped this revision; replacing its content with DDL would
  re-execute skipped statements and break idempotency.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '95929ae669b9'
down_revision: str | None = 'aaeadb9644c0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Intentionally empty — see NOTES above.
    pass


def downgrade() -> None:
    # Intentionally empty — see NOTES above.
    pass
