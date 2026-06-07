-- ROTAS local dev PostgreSQL initialization
-- Creates application roles with dev passwords.
-- In production (Railway), roles are created by Alembic migration 4b0a7802dc3c
-- and passwords are set manually in Railway console.
DO $$ BEGIN CREATE ROLE rotas_app; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE rotas_admin BYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Set dev-only passwords (never use these in production)
ALTER ROLE rotas_app PASSWORD 'rotas_app_dev';
ALTER ROLE rotas_admin PASSWORD 'rotas_admin_dev';

-- Grant connect on the rotas database
GRANT CONNECT ON DATABASE rotas TO rotas_app;
GRANT CONNECT ON DATABASE rotas TO rotas_admin;
