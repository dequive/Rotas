# Staging secrets

This directory must never contain real secret values in Git. Create the
following extensionless files in a protected directory outside the repository
and point `STAGING_SECRETS_DIR` to that directory:

- `rotas_owner_password`
- `rotas_app_password`
- `rotas_admin_password`
- `rotas_database_url`
- `rotas_admin_database_url`
- `rotas_alembic_database_url`
- `rotas_jwt_secret`
- `rotas_redis_password`
- `rotas_redis_url`
- `rotas_r2_access_key_id`
- `rotas_r2_secret_access_key`
- `rotas_governance_api_key`
- `manager_governance_api_key` (Manager BFF only; scopes `cases:read` and `cases:write`)
- `governance_database_password`
- `governance_database_url`
- `governance_jwt_secret`
- `governance_platform_admin_key`
- `alertmanager_webhook_url`
- `grafana_admin_password`

Every file must contain exactly one value. Passwords must have at least 16
characters; JWT/API/platform keys must be non-default values with at least 32
characters. URLs must embed the matching external password and use the
documented roles (`rotas_app`, `rotas_admin` and `governance_app`). Use a secret
manager to materialise these files immediately before deployment and remove
them after the deployment completes.
