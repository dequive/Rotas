"""add_gps_and_tracking_tables

Revision ID: gps01
Revises: mrg03
Create Date: 2026-06-22

Creates GPS ingestion + customer tracking tables:
  - gps_devices     (IMEI registry, HMAC device_secret, tenant+vehicle binding)
  - gps_positions   (partitioned BY RANGE(recorded_at), append-only, 90-day retention)
  - vehicle_last_position (upsert table for fast fleet map reads)
  - tracking_tokens (shareable customer-facing trip tracking links)

All tables: RLS + GRANT in same migration (v2.0 rule).
"""

from alembic import op

revision = "gps01"
down_revision = "mrg03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── gps_devices ───────────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE gps_devices (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID NOT NULL REFERENCES tenants(id),
        vehicle_id  UUID NOT NULL REFERENCES vehicles(id),
        imei        VARCHAR(20) NOT NULL,
        device_secret VARCHAR(128) NOT NULL,
        is_active   BOOLEAN NOT NULL DEFAULT TRUE,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_gps_devices_imei UNIQUE (imei)
    );
    CREATE INDEX ix_gps_devices_tenant_id ON gps_devices(tenant_id);
    CREATE INDEX ix_gps_devices_vehicle_id ON gps_devices(vehicle_id);
    ALTER TABLE gps_devices ENABLE ROW LEVEL SECURITY;
    ALTER TABLE gps_devices FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON gps_devices
        USING (tenant_id::text = current_setting('app.tenant_id', true));
    GRANT SELECT, INSERT, UPDATE, DELETE ON gps_devices TO rotas_app;
    """)

    # ── gps_positions (partitioned, append-only) ──────────────────────────────
    op.execute("""
    CREATE TABLE gps_positions (
        id          UUID NOT NULL DEFAULT gen_random_uuid(),
        tenant_id   UUID NOT NULL,
        vehicle_id  UUID NOT NULL,
        device_id   UUID NOT NULL,
        lat         DOUBLE PRECISION NOT NULL,
        lon         DOUBLE PRECISION NOT NULL,
        speed_kmh   NUMERIC(6,2),
        heading_deg SMALLINT,
        accuracy_m  NUMERIC(8,2),
        raw_payload JSONB,
        recorded_at TIMESTAMPTZ NOT NULL,
        ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (id, recorded_at)
    ) PARTITION BY RANGE (recorded_at);
    CREATE INDEX ix_gps_positions_tenant_vehicle
        ON gps_positions(tenant_id, vehicle_id, recorded_at DESC);
    ALTER TABLE gps_positions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE gps_positions FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON gps_positions
        USING (tenant_id::text = current_setting('app.tenant_id', true));
    GRANT SELECT, INSERT ON gps_positions TO rotas_app;
    """)

    # Seed initial partitions: current month + next month
    op.execute("""
    CREATE TABLE gps_positions_2026_06 PARTITION OF gps_positions
        FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
    CREATE TABLE gps_positions_2026_07 PARTITION OF gps_positions
        FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
    CREATE TABLE gps_positions_2026_08 PARTITION OF gps_positions
        FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
    CREATE TABLE gps_positions_default PARTITION OF gps_positions DEFAULT;
    """)

    # ── vehicle_last_position (upsert, one row per vehicle) ───────────────────
    op.execute("""
    CREATE TABLE vehicle_last_position (
        vehicle_id  UUID PRIMARY KEY REFERENCES vehicles(id),
        tenant_id   UUID NOT NULL REFERENCES tenants(id),
        lat         DOUBLE PRECISION NOT NULL,
        lon         DOUBLE PRECISION NOT NULL,
        speed_kmh   NUMERIC(6,2),
        heading_deg SMALLINT,
        recorded_at TIMESTAMPTZ NOT NULL,
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_vehicle_last_position_tenant ON vehicle_last_position(tenant_id);
    ALTER TABLE vehicle_last_position ENABLE ROW LEVEL SECURITY;
    ALTER TABLE vehicle_last_position FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON vehicle_last_position
        USING (tenant_id::text = current_setting('app.tenant_id', true));
    GRANT SELECT, INSERT, UPDATE, DELETE ON vehicle_last_position TO rotas_app;
    """)

    # ── tracking_tokens ───────────────────────────────────────────────────────
    op.execute("""
    CREATE TABLE tracking_tokens (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id   UUID NOT NULL REFERENCES tenants(id),
        trip_id     UUID NOT NULL REFERENCES trips(id),
        token       VARCHAR(64) NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL,
        created_by  UUID,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        CONSTRAINT uq_tracking_tokens_token UNIQUE (token)
    );
    CREATE INDEX ix_tracking_tokens_tenant_id ON tracking_tokens(tenant_id);
    CREATE INDEX ix_tracking_tokens_trip_id ON tracking_tokens(trip_id);
    ALTER TABLE tracking_tokens ENABLE ROW LEVEL SECURITY;
    ALTER TABLE tracking_tokens FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation ON tracking_tokens
        USING (tenant_id::text = current_setting('app.tenant_id', true));
    GRANT SELECT, INSERT, UPDATE, DELETE ON tracking_tokens TO rotas_app;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tracking_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS vehicle_last_position CASCADE")
    op.execute("DROP TABLE IF EXISTS gps_positions CASCADE")
    op.execute("DROP TABLE IF EXISTS gps_devices CASCADE")
