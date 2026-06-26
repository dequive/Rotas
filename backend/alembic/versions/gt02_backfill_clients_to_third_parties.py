"""backfill existing clients into third_parties entity graph

Revision ID: gt02
Revises: gt01
Create Date: 2026-06-22

DML only -- no DDL. Backfills clients rows:
  - INSERT into third_parties (ON CONFLICT DO NOTHING for idempotency)
  - INSERT into third_party_roles with role_type='client'
  - INSERT into client_profiles
  - UPDATE clients.third_party_id

Idempotency: only processes clients WHERE third_party_id IS NULL.
Processed rows leave the working set automatically, so no OFFSET counter is needed.
"""

from sqlalchemy import text

from alembic import op

revision = "gt02"
down_revision = "gt01"
branch_labels = None
depends_on = None

BATCH_SIZE = 500


def upgrade() -> None:
    bind = op.get_bind()

    while True:
        # Fetch only clients not yet linked.
        # WHERE third_party_id IS NULL shrinks the working set as rows are processed,
        # so no OFFSET counter is needed -- processed rows disappear from this query.
        rows = bind.execute(
            text(
                """
                SELECT id, tenant_id, trading_name, legal_name, nuit,
                       email, payment_terms_days, credit_limit
                FROM clients
                WHERE third_party_id IS NULL
                ORDER BY id
                LIMIT :limit
                """
            ),
            {"limit": BATCH_SIZE},
        ).fetchall()

        if not rows:
            break

        for row in rows:
            # 1. INSERT third_party — ON CONFLICT DO NOTHING guards against partial-failure reruns
            tp_id = bind.execute(
                text(
                    """
                    INSERT INTO third_parties (id, tenant_id, name, nuit, status, created_at, updated_at)
                    VALUES (gen_random_uuid(), :tenant_id, :name, :nuit, 'active', now(), now())
                    ON CONFLICT (tenant_id, nuit) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "tenant_id": row.tenant_id,
                    "name": row.trading_name,
                    "nuit": row.nuit,
                },
            ).scalar()

            # If ON CONFLICT fired (row already exists), retrieve the existing id
            if tp_id is None:
                tp_id = bind.execute(
                    text(
                        "SELECT id FROM third_parties WHERE tenant_id = :tenant_id AND nuit = :nuit"
                    ),
                    {"tenant_id": row.tenant_id, "nuit": row.nuit},
                ).scalar_one()

            # 2. INSERT third_party_role with role_type='client'
            bind.execute(
                text(
                    """
                    INSERT INTO third_party_roles (id, tenant_id, third_party_id, role_type, is_active, created_at)
                    VALUES (gen_random_uuid(), :tenant_id, :tp_id, 'client', true, now())
                    ON CONFLICT (third_party_id, role_type) DO NOTHING
                    """
                ),
                {"tenant_id": row.tenant_id, "tp_id": tp_id},
            )

            # 3. INSERT client_profile
            bind.execute(
                text(
                    """
                    INSERT INTO client_profiles (
                        id, tenant_id, third_party_id,
                        payment_terms_days, credit_limit, preferred_currency,
                        created_at, updated_at
                    )
                    VALUES (
                        gen_random_uuid(), :tenant_id, :tp_id,
                        :payment_terms_days, :credit_limit, 'MZN',
                        now(), now()
                    )
                    ON CONFLICT (third_party_id) DO NOTHING
                    """
                ),
                {
                    "tenant_id": row.tenant_id,
                    "tp_id": tp_id,
                    "payment_terms_days": row.payment_terms_days,
                    "credit_limit": row.credit_limit,
                },
            )

            # 4. UPDATE clients.third_party_id
            bind.execute(
                text("UPDATE clients SET third_party_id = :tp_id WHERE id = :client_id"),
                {"tp_id": tp_id, "client_id": row.id},
            )

        # Commit after each batch to reduce lock hold time
        bind.commit()
        # No offset increment -- processed rows are excluded by WHERE third_party_id IS NULL


def downgrade() -> None:
    # Reverse: clear clients.third_party_id, remove client_profiles and roles for role_type='client'
    # Does NOT remove third_parties rows (they may be referenced from elsewhere post-migration)
    bind = op.get_bind()
    bind.execute(text("UPDATE clients SET third_party_id = NULL"))
    bind.execute(
        text(
            """
            DELETE FROM client_profiles
            WHERE third_party_id IN (
                SELECT third_party_id FROM third_party_roles WHERE role_type = 'client'
            )
            """
        )
    )
    bind.execute(text("DELETE FROM third_party_roles WHERE role_type = 'client'"))
    bind.commit()
