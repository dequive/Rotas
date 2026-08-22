#!/bin/sh
set -eu

app_password="$(cat /run/secrets/rotas_app_password)"
admin_password="$(cat /run/secrets/rotas_admin_password)"

psql --set=ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER}" \
  --dbname "${POSTGRES_DB}" \
  --set=app_password="${app_password}" \
  --set=admin_password="${admin_password}" <<'SQL'
CREATE ROLE rotas_app LOGIN NOBYPASSRLS PASSWORD :'app_password';
CREATE ROLE rotas_admin LOGIN NOSUPERUSER BYPASSRLS PASSWORD :'admin_password';
GRANT CONNECT ON DATABASE rotas TO rotas_app, rotas_admin;
GRANT USAGE, CREATE ON SCHEMA public TO rotas_admin;
SQL
