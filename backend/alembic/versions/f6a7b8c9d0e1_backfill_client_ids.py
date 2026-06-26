"""backfill client_id on contracts and billing_documents (migration c — DML only)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-19

NOTE: Plan 05-02 specified revision c3d4e5f6a7b8. Using f6a7b8c9d0e1 to avoid future conflicts.

CRITICAL: Must run as rotas_admin (BYPASSRLS). RLS is active on contracts and
billing_documents since Phase 9. If run as rotas_app, zero rows are visible and
the backfill inserts nothing. Verify ALEMBIC_DATABASE_URL connects as rotas_admin.

Run pre-migration audit query before applying this migration:

  SELECT tenant_id, lower(trim(client_name)) AS normalized, count(*) AS occurrences,
         array_agg(DISTINCT client_name ORDER BY client_name) AS variants
  FROM contracts
  WHERE client_name IS NOT NULL AND client_name != ''
  GROUP BY 1, 2 HAVING count(*) > 1 ORDER BY 1, 3 DESC;

Pre-migration audit result: Could not connect to live DB during plan execution.
Run the query above immediately before applying this migration and document results.
If result set is empty: "No variant spellings found — normalized backfill is safe."

Backfill strategy:
1. Read DISTINCT (tenant_id, lower(trim(client_name))) from contracts
2. INSERT one client per normalized name per tenant via SELECT DISTINCT ON
   (uses client_nuit from contracts when available, placeholder '000000000' otherwise)
3. UPDATE contracts.client_id WHERE lower(trim(client_name)) matches trading_name
4. UPDATE billing_documents.client_id via their contract's client_id
5. UPDATE remaining billing_documents.client_id by direct client_name match
6. Populate due_date from issued_at + payment_terms_days for all linked billing_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1 + 2: INSERT one client per (tenant_id, normalized name) using DISTINCT ON.
    # Uses client_nuit from contracts when populated; placeholder '000000000' otherwise.
    # ON CONFLICT DO NOTHING ensures idempotent re-runs.
    conn.execute(
        sa.text("""
        INSERT INTO clients (id, tenant_id, trading_name, nuit, payment_terms_days, is_active, created_at, updated_at)
        SELECT DISTINCT ON (tenant_id, lower(trim(client_name)))
            gen_random_uuid(),
            tenant_id,
            -- Use longest non-empty variant as canonical trading_name
            first_value(client_name) OVER (
                PARTITION BY tenant_id, lower(trim(client_name))
                ORDER BY length(client_name) DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ),
            -- Use client_nuit if populated, else placeholder
            COALESCE(NULLIF(trim(client_nuit), ''), '000000000'),
            30,
            true,
            NOW(),
            NOW()
        FROM contracts
        WHERE client_name IS NOT NULL AND client_name != ''
        ON CONFLICT (tenant_id, nuit) DO NOTHING
    """)
    )

    # Step 3: UPDATE contracts.client_id by matching normalized trading_name
    conn.execute(
        sa.text("""
        UPDATE contracts c
        SET client_id = cl.id
        FROM clients cl
        WHERE c.tenant_id = cl.tenant_id
          AND lower(trim(c.client_name)) = lower(trim(cl.trading_name))
          AND c.client_id IS NULL
    """)
    )

    # Step 4: UPDATE billing_documents.client_id + due_date from their linked contract
    conn.execute(
        sa.text("""
        UPDATE billing_documents bd
        SET client_id = c.client_id,
            due_date = CASE
                WHEN bd.issued_at IS NOT NULL THEN
                    bd.issued_at + (
                        COALESCE(
                            (SELECT payment_terms_days FROM clients WHERE id = c.client_id LIMIT 1),
                            30
                        ) * INTERVAL '1 day'
                    )
                ELSE NULL
            END
        FROM contracts c
        WHERE bd.contract_id = c.id
          AND bd.client_id IS NULL
          AND c.client_id IS NOT NULL
    """)
    )

    # Step 5: billing_documents without a matched contract — match by client_name directly
    conn.execute(
        sa.text("""
        UPDATE billing_documents bd
        SET client_id = cl.id
        FROM clients cl
        WHERE bd.tenant_id = cl.tenant_id
          AND lower(trim(bd.client_name)) = lower(trim(cl.trading_name))
          AND bd.client_id IS NULL
    """)
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE contracts SET client_id = NULL"))
    conn.execute(sa.text("UPDATE billing_documents SET client_id = NULL, due_date = NULL"))
    conn.execute(sa.text("DELETE FROM clients WHERE nuit = '000000000'"))
