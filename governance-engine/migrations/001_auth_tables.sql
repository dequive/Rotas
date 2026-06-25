-- ============================================================
-- 001_auth_tables.sql — Bootstrap schema for the Governance Engine
-- Run once against a fresh PostgreSQL 16 database.
-- The application role governance_app must already exist
-- (created by infra/postgres-init.sql).
-- ============================================================

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Helpers ──────────────────────────────────────────────────────────────────

-- Atomic human-readable sequence: EVT-YYYY-NNNNNN / CASE-YYYY-NNNNNN
-- Uses ON CONFLICT DO UPDATE to increment last_seq atomically without a lock.
CREATE TABLE IF NOT EXISTS tenant_sequences (
    tenant_id   UUID        NOT NULL,
    prefix      VARCHAR(10) NOT NULL,
    year        SMALLINT    NOT NULL,
    last_seq    INTEGER     NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, prefix, year)
);

CREATE OR REPLACE FUNCTION next_human_id(
    p_tenant_id UUID,
    p_prefix    TEXT,
    p_year      SMALLINT
) RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE
    v_seq INTEGER;
BEGIN
    INSERT INTO tenant_sequences (tenant_id, prefix, year, last_seq)
    VALUES (p_tenant_id, p_prefix, p_year, 1)
    ON CONFLICT (tenant_id, prefix, year)
    DO UPDATE SET last_seq = tenant_sequences.last_seq + 1
    RETURNING last_seq INTO v_seq;

    RETURN p_prefix || '-' || p_year::TEXT || '-' || LPAD(v_seq::TEXT, 6, '0');
END;
$$;

-- Immutability trigger (shared by occurrences + case_transitions)
CREATE OR REPLACE FUNCTION raise_immutable_record()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'This table is append-only — reverse with a new record.';
END;
$$;

-- ── Auth tables (NO RLS — read before tenant is known) ───────────────────────

CREATE TABLE IF NOT EXISTS tenants (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL UNIQUE,
    plan        TEXT        NOT NULL DEFAULT 'starter',
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_keys (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    label        TEXT        NOT NULL,
    key_prefix   VARCHAR(8)  NOT NULL,
    key_hash     CHAR(64)    NOT NULL UNIQUE,  -- SHA-256 hex
    scopes       TEXT[]      NOT NULL DEFAULT '{}',
    actor_type   TEXT        NOT NULL DEFAULT 'service',
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_api_keys_tenant ON api_keys (tenant_id);

-- ── Taxonomy ─────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS taxonomy_domains (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    code        TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    description TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS ix_taxonomy_domains_tenant ON taxonomy_domains (tenant_id);

CREATE TABLE IF NOT EXISTS taxonomy_case_types (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    domain_id           UUID        NOT NULL REFERENCES taxonomy_domains(id),
    code                TEXT        NOT NULL,
    name                TEXT        NOT NULL,
    description         TEXT,
    initial_status      TEXT        NOT NULL DEFAULT 'open',
    sla_hours           INTEGER,
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS ix_taxonomy_case_types_tenant ON taxonomy_case_types (tenant_id);

CREATE TABLE IF NOT EXISTS taxonomy_types (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    domain_id   UUID        NOT NULL REFERENCES taxonomy_domains(id),
    code        TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    description TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, code)
);
CREATE INDEX IF NOT EXISTS ix_taxonomy_types_tenant ON taxonomy_types (tenant_id);

CREATE TABLE IF NOT EXISTS taxonomy_type_promotions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    type_id         UUID        NOT NULL REFERENCES taxonomy_types(id),
    case_type_id    UUID        NOT NULL REFERENCES taxonomy_case_types(id),
    min_severity    TEXT        NOT NULL DEFAULT 'alta',
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, type_id, case_type_id)
);
CREATE INDEX IF NOT EXISTS ix_taxonomy_type_promotions_tenant ON taxonomy_type_promotions (tenant_id);

-- ── Entity catalog ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_catalogs (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    entity_type TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    description TEXT,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, entity_type)
);
CREATE INDEX IF NOT EXISTS ix_entity_catalogs_tenant ON entity_catalogs (tenant_id);

CREATE TABLE IF NOT EXISTS entity_instances (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    catalog_id      UUID        NOT NULL REFERENCES entity_catalogs(id),
    external_id     TEXT        NOT NULL,
    display_name    TEXT        NOT NULL,
    attributes      JSONB       NOT NULL DEFAULT '{}',
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, catalog_id, external_id)
);
CREATE INDEX IF NOT EXISTS ix_entity_instances_tenant ON entity_instances (tenant_id);

-- ── Occurrences (append-only) ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS occurrences (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    numero          TEXT        NOT NULL UNIQUE,      -- EVT-YYYY-NNNNNN
    type_id         UUID        NOT NULL REFERENCES taxonomy_types(id),
    severity        TEXT        NOT NULL,
    title           TEXT        NOT NULL,
    description     TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    reported_by     UUID        NOT NULL,             -- actor_id (service or user)
    location_text   TEXT,
    latitude        NUMERIC(10, 8),
    longitude       NUMERIC(11, 8),
    supersedes_id   UUID        REFERENCES occurrences(id),  -- correction chain
    idempotency_key TEXT,
    payload         JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_occurrences_tenant    ON occurrences (tenant_id);
CREATE INDEX IF NOT EXISTS ix_occurrences_type      ON occurrences (tenant_id, type_id);
CREATE INDEX IF NOT EXISTS ix_occurrences_occurred  ON occurrences (tenant_id, occurred_at DESC);
-- Scoped to tenant_id so different tenants can reuse the same key string
CREATE UNIQUE INDEX IF NOT EXISTS ux_occurrences_idem_key ON occurrences (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TRIGGER trg_occurrences_immutable
    BEFORE UPDATE OR DELETE ON occurrences
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_record();

CREATE TABLE IF NOT EXISTS occurrence_links (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    occurrence_id   UUID        NOT NULL REFERENCES occurrences(id),
    instance_id     UUID        NOT NULL REFERENCES entity_instances(id),
    role            TEXT        NOT NULL DEFAULT 'sujeito',
    snapshot        JSONB       NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_occurrence_links_tenant     ON occurrence_links (tenant_id);
CREATE INDEX IF NOT EXISTS ix_occurrence_links_occurrence ON occurrence_links (occurrence_id);

CREATE TABLE IF NOT EXISTS attachments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    occurrence_id   UUID        REFERENCES occurrences(id),
    case_id         UUID,                              -- FK set after cases table created
    filename        TEXT        NOT NULL,
    content_type    TEXT        NOT NULL,
    size_bytes      INTEGER     NOT NULL,
    storage_key     TEXT        NOT NULL,
    uploaded_by     UUID        NOT NULL,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_attachments_tenant     ON attachments (tenant_id);
CREATE INDEX IF NOT EXISTS ix_attachments_occurrence ON attachments (occurrence_id);

-- ── Cases ─────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cases (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    reference       TEXT        NOT NULL UNIQUE,      -- CASE-YYYY-NNNNNN
    case_type_id    UUID        NOT NULL REFERENCES taxonomy_case_types(id),
    status          TEXT        NOT NULL DEFAULT 'open',
    assignee_id     UUID,
    payload         JSONB       NOT NULL DEFAULT '{}',
    sla_due_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_cases_tenant  ON cases (tenant_id);
CREATE INDEX IF NOT EXISTS ix_cases_status  ON cases (tenant_id, status);

-- Deferred FK: attachments → cases
ALTER TABLE attachments
    ADD CONSTRAINT fk_attachments_case
    FOREIGN KEY (case_id) REFERENCES cases(id);
CREATE INDEX IF NOT EXISTS ix_attachments_case ON attachments (case_id);

CREATE TABLE IF NOT EXISTS case_occurrences (
    case_id         UUID    NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    occurrence_id   UUID    NOT NULL REFERENCES occurrences(id),
    tenant_id       UUID    NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    linked_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (case_id, occurrence_id)
);
CREATE INDEX IF NOT EXISTS ix_case_occurrences_tenant ON case_occurrences (tenant_id);

CREATE TABLE IF NOT EXISTS case_transition_rules (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    case_type_id    UUID        NOT NULL REFERENCES taxonomy_case_types(id),
    from_status     TEXT,                              -- NULL = entry rule (open_case)
    to_status       TEXT        NOT NULL,
    required_fields TEXT[]      NOT NULL DEFAULT '{}',
    required_attachments BOOLEAN NOT NULL DEFAULT FALSE,
    sla_hours       INTEGER,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, case_type_id, from_status, to_status)
);
CREATE INDEX IF NOT EXISTS ix_case_transition_rules_tenant ON case_transition_rules (tenant_id);

CREATE TABLE IF NOT EXISTS case_transitions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    case_id         UUID        NOT NULL REFERENCES cases(id),
    from_status     TEXT,
    to_status       TEXT        NOT NULL,
    actor_id        UUID        NOT NULL,
    reason          TEXT,
    payload         JSONB       NOT NULL DEFAULT '{}',
    idempotency_key TEXT,
    transitioned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_case_transitions_tenant ON case_transitions (tenant_id);
CREATE INDEX IF NOT EXISTS ix_case_transitions_case   ON case_transitions (case_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_case_transitions_idem_key ON case_transitions (tenant_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TRIGGER trg_case_transitions_immutable
    BEFORE UPDATE OR DELETE ON case_transitions
    FOR EACH ROW EXECUTE FUNCTION raise_immutable_record();

-- ── Activities & Notes ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS activities (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    case_id         UUID        REFERENCES cases(id),
    transition_id   UUID        REFERENCES case_transitions(id),
    actor_id        UUID        NOT NULL,
    activity_type   TEXT        NOT NULL,
    description     TEXT,
    payload         JSONB       NOT NULL DEFAULT '{}',
    at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_activities_tenant ON activities (tenant_id);
CREATE INDEX IF NOT EXISTS ix_activities_case   ON activities (case_id);

CREATE TABLE IF NOT EXISTS notes (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    occurrence_id   UUID        REFERENCES occurrences(id),
    case_id         UUID        REFERENCES cases(id),
    author_id       UUID        NOT NULL,
    body            TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_notes_tenant ON notes (tenant_id);

-- ── RLS policies ─────────────────────────────────────────────────────────────
-- tenant_sequences, tenants, api_keys: NO RLS (auth layer reads them pre-principal)

ALTER TABLE taxonomy_domains           ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy_domains           FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_taxonomy_domains ON taxonomy_domains
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE taxonomy_case_types        ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy_case_types        FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_taxonomy_case_types ON taxonomy_case_types
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE taxonomy_types             ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy_types             FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_taxonomy_types ON taxonomy_types
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE taxonomy_type_promotions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE taxonomy_type_promotions   FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_taxonomy_type_promotions ON taxonomy_type_promotions
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE entity_catalogs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_catalogs            FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_entity_catalogs ON entity_catalogs
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE entity_instances           ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_instances           FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_entity_instances ON entity_instances
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE occurrences                ENABLE ROW LEVEL SECURITY;
ALTER TABLE occurrences                FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_occurrences ON occurrences
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE occurrence_links           ENABLE ROW LEVEL SECURITY;
ALTER TABLE occurrence_links           FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_occurrence_links ON occurrence_links
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE attachments                ENABLE ROW LEVEL SECURITY;
ALTER TABLE attachments                FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_attachments ON attachments
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE cases                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases                      FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_cases ON cases
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE case_occurrences           ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_occurrences           FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_case_occurrences ON case_occurrences
    USING (
        EXISTS (
            SELECT 1 FROM cases c
            WHERE c.id = case_occurrences.case_id
              AND c.tenant_id::text = current_setting('app.tenant_id', true)
        )
    );

ALTER TABLE case_transition_rules      ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_transition_rules      FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_case_transition_rules ON case_transition_rules
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE case_transitions           ENABLE ROW LEVEL SECURITY;
ALTER TABLE case_transitions           FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_case_transitions ON case_transitions
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE activities                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE activities                 FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_activities ON activities
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE notes                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes                      FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_notes ON notes
    USING (tenant_id::text = current_setting('app.tenant_id', true));

ALTER TABLE tenant_sequences           ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_sequences           FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_tenant_sequences ON tenant_sequences
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- ── Grants ────────────────────────────────────────────────────────────────────
-- occurrences + case_transitions: INSERT only (append-only contract)
-- everything else: full CRUD

GRANT SELECT, INSERT, UPDATE, DELETE ON tenants                  TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON api_keys                 TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON tenant_sequences         TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON taxonomy_domains         TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON taxonomy_case_types      TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON taxonomy_types           TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON taxonomy_type_promotions TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON entity_catalogs          TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON entity_instances         TO governance_app;
GRANT SELECT, INSERT               ON occurrences                TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON occurrence_links         TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON attachments              TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON cases                    TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON case_occurrences         TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON case_transition_rules    TO governance_app;
GRANT SELECT, INSERT               ON case_transitions           TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON activities               TO governance_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON notes                    TO governance_app;
