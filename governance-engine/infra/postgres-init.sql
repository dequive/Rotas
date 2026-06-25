-- Creates the application role and database objects.
-- Runs once on first container start via docker-entrypoint-initdb.d.

CREATE ROLE governance_app WITH LOGIN PASSWORD 'governance';

-- Grant connect on the governance database (created by POSTGRES_DB env var)
GRANT CONNECT ON DATABASE governance TO governance_app;

-- Schema usage
GRANT USAGE ON SCHEMA public TO governance_app;

-- Future tables: grant access automatically
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO governance_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO governance_app;
