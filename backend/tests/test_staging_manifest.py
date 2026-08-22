from pathlib import Path

import pytest

from scripts.validate_staging_manifest import (
    CUSTOM_IMAGE_KEYS,
    REQUIRED_HOST_KEYS,
    REQUIRED_SECRET_FILES,
    StagingManifestError,
    validate_deployment_inputs,
    validate_static_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _valid_secrets() -> dict[str, str]:
    app_password = "app-password-2026-secure"
    admin_password = "admin-password-2026-secure"
    governance_password = "governance-db-2026-secure"
    redis_password = "redis-password-2026-secure"
    return {
        "rotas_owner_password": "owner-password-2026-secure",
        "rotas_app_password": app_password,
        "rotas_admin_password": admin_password,
        "rotas_database_url": (
            f"postgresql+asyncpg://rotas_app:{app_password}@postgres:5432/rotas"
        ),
        "rotas_admin_database_url": (
            f"postgresql+asyncpg://rotas_admin:{admin_password}@postgres:5432/rotas"
        ),
        "rotas_alembic_database_url": (
            f"postgresql+psycopg://rotas_admin:{admin_password}@postgres:5432/rotas"
        ),
        "rotas_jwt_secret": "rotas-jwt-secret-2026-at-least-32-characters",
        "rotas_redis_password": redis_password,
        "rotas_redis_url": f"redis://:{redis_password}@redis:6379/0",
        "rotas_r2_access_key_id": "r2-access-key-id",
        "rotas_r2_secret_access_key": "r2-secret-access-key-2026",
        "rotas_governance_api_key": "rotas-governance-key-2026-at-least-32-chars",
        "manager_governance_api_key": "manager-governance-key-2026-at-least-32-chars",
        "governance_database_password": governance_password,
        "governance_database_url": (
            "postgresql+asyncpg://governance_app:"
            f"{governance_password}@governance-postgres:5432/governance"
        ),
        "governance_jwt_secret": "governance-jwt-secret-2026-at-least-32-chars",
        "governance_platform_admin_key": (
            "governance-platform-key-2026-at-least-32-chars"
        ),
        "alertmanager_webhook_url": "https://alerts.rotas.co.mz/hooks/staging",
        "grafana_admin_password": "grafana-password-2026-secure",
    }


def _write_valid_deployment(tmp_path: Path) -> tuple[Path, Path]:
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir()
    for name, value in _valid_secrets().items():
        (secrets_dir / name).write_text(value, encoding="utf-8")

    env_path = tmp_path / "staging.env"
    lines = [
        "ROTAS_RELEASE_SHA=0123456789abcdef0123456789abcdef01234567",
        *[
            f"{key}=registry.internal/rotas/{index}@sha256:{str(index) * 64}"
            for index, key in enumerate(sorted(CUSTOM_IMAGE_KEYS), 1)
        ],
        *[
            f"{key}={key.lower().replace('_', '-')}.staging.rotas.co.mz"
            for key in sorted(REQUIRED_HOST_KEYS)
        ],
        "ACME_EMAIL=operations@rotas.co.mz",
        "R2_BUCKET=rotas-staging",
        "R2_ENDPOINT_URL=https://account.r2.cloudflarestorage.com",
        "EMAIL_FROM_ADDRESS=staging@rotas.co.mz",
        "ROTAS_GOVERNANCE_TENANT_ID=11111111-1111-4111-8111-111111111111",
        f"STAGING_SECRETS_DIR={secrets_dir}",
    ]
    env_path.write_text("\n".join(lines), encoding="utf-8")
    return env_path, secrets_dir


def test_staging_static_policy_is_fail_closed():
    result = validate_static_policy(REPO_ROOT)

    assert result["literal_digest_images"] >= 3
    assert result["pinned_dockerfile_stages"] >= 7
    assert result["custom_digest_inputs"] == 4


def test_example_environment_is_deliberately_not_deployable():
    with pytest.raises(StagingManifestError, match="example registry"):
        validate_deployment_inputs(REPO_ROOT / "infra" / "staging" / "staging.env.example")


def test_realistic_digest_inputs_and_external_secrets_pass(tmp_path):
    env_path, _ = _write_valid_deployment(tmp_path)

    result = validate_deployment_inputs(env_path)

    assert result == {
        "release_sha": 1,
        "immutable_application_images": 4,
        "staging_hosts": 4,
        "secret_files": len(REQUIRED_SECRET_FILES),
    }


def test_deployment_rejects_short_sha_and_wrong_database_role(tmp_path):
    env_path, secrets_dir = _write_valid_deployment(tmp_path)
    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            "ROTAS_RELEASE_SHA=0123456789abcdef0123456789abcdef01234567",
            "ROTAS_RELEASE_SHA=deadbeef",
        ),
        encoding="utf-8",
    )
    app_url = secrets_dir / "rotas_database_url"
    app_url.write_text(
        app_url.read_text(encoding="utf-8").replace("rotas_app", "rotas_admin"),
        encoding="utf-8",
    )

    with pytest.raises(StagingManifestError) as exc:
        validate_deployment_inputs(env_path)

    message = str(exc.value)
    assert "full 40-character lowercase Git SHA" in message
    assert "rotas_database_url must use database role rotas_app" in message


def test_deployment_rejects_weak_or_incoherent_secrets(tmp_path):
    env_path, secrets_dir = _write_valid_deployment(tmp_path)
    (secrets_dir / "rotas_jwt_secret").write_text("test-secret", encoding="utf-8")
    (secrets_dir / "rotas_redis_password").write_text(
        "different-redis-password",
        encoding="utf-8",
    )

    with pytest.raises(StagingManifestError) as exc:
        validate_deployment_inputs(env_path)

    message = str(exc.value)
    assert "rotas_jwt_secret must be a non-default value" in message
    assert "rotas_redis_url password must match rotas_redis_password" in message


def test_deployment_requires_governance_tenant_mapping(tmp_path):
    env_path, _ = _write_valid_deployment(tmp_path)
    env_path.write_text(
        env_path.read_text(encoding="utf-8").replace(
            "ROTAS_GOVERNANCE_TENANT_ID=11111111-1111-4111-8111-111111111111",
            "ROTAS_GOVERNANCE_TENANT_ID=not-a-uuid",
        ),
        encoding="utf-8",
    )

    with pytest.raises(StagingManifestError, match="ROTAS_GOVERNANCE_TENANT_ID"):
        validate_deployment_inputs(env_path)
