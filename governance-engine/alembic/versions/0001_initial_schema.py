"""Initial schema — all tables, RLS, triggers, grants.

Revision ID: 0001
Revises:
Create Date: 2026-06-22
"""

from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None

_SQL_FILE = Path(__file__).parent.parent.parent / "migrations" / "001_auth_tables.sql"


def upgrade() -> None:
    # Execute the canonical SQL migration. The file is idempotent
    # (all CREATE TABLE / CREATE INDEX use IF NOT EXISTS).
    sql = _SQL_FILE.read_text(encoding="utf-8")
    op.execute(sql)


def downgrade() -> None:
    # Full teardown — drops everything in reverse dependency order.
    op.execute("DROP TABLE IF EXISTS notes             CASCADE")
    op.execute("DROP TABLE IF EXISTS activities        CASCADE")
    op.execute("DROP TABLE IF EXISTS case_transitions  CASCADE")
    op.execute("DROP TABLE IF EXISTS case_transition_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS case_occurrences  CASCADE")
    op.execute("DROP TABLE IF EXISTS cases             CASCADE")
    op.execute("DROP TABLE IF EXISTS attachments       CASCADE")
    op.execute("DROP TABLE IF EXISTS occurrence_links  CASCADE")
    op.execute("DROP TABLE IF EXISTS occurrences       CASCADE")
    op.execute("DROP TABLE IF EXISTS entity_instances  CASCADE")
    op.execute("DROP TABLE IF EXISTS entity_catalogs   CASCADE")
    op.execute("DROP TABLE IF EXISTS taxonomy_type_promotions CASCADE")
    op.execute("DROP TABLE IF EXISTS taxonomy_types    CASCADE")
    op.execute("DROP TABLE IF EXISTS taxonomy_case_types CASCADE")
    op.execute("DROP TABLE IF EXISTS taxonomy_domains  CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_sequences  CASCADE")
    op.execute("DROP TABLE IF EXISTS api_keys          CASCADE")
    op.execute("DROP TABLE IF EXISTS tenants           CASCADE")
    op.execute("DROP FUNCTION IF EXISTS next_human_id(UUID, TEXT, SMALLINT)")
    op.execute("DROP FUNCTION IF EXISTS raise_immutable_record()")
