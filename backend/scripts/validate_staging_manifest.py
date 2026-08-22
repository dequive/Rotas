"""Fail-closed policy validation for the provider-neutral staging baseline."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID

REQUIRED_SECRET_FILES = frozenset(
    {
        "rotas_owner_password",
        "rotas_app_password",
        "rotas_admin_password",
        "rotas_database_url",
        "rotas_admin_database_url",
        "rotas_alembic_database_url",
        "rotas_jwt_secret",
        "rotas_redis_password",
        "rotas_redis_url",
        "rotas_r2_access_key_id",
        "rotas_r2_secret_access_key",
        "rotas_governance_api_key",
        "manager_governance_api_key",
        "governance_database_password",
        "governance_database_url",
        "governance_jwt_secret",
        "governance_platform_admin_key",
        "alertmanager_webhook_url",
        "grafana_admin_password",
    }
)
CUSTOM_IMAGE_KEYS = frozenset(
    {
        "ROTAS_BACKEND_IMAGE",
        "ROTAS_GOVERNANCE_IMAGE",
        "ROTAS_MANAGER_IMAGE",
        "ROTAS_DRIVER_IMAGE",
    }
)
REQUIRED_HOST_KEYS = frozenset(
    {
        "ROTAS_MANAGER_HOST",
        "ROTAS_DRIVER_HOST",
        "ROTAS_API_HOST",
        "ROTAS_GRAFANA_HOST",
    }
)
IMMUTABLE_IMAGE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FROM_LINE = re.compile(
    r"^FROM\s+(?P<source>\S+)(?:\s+AS\s+(?P<alias>\S+))?$",
    re.IGNORECASE,
)


class StagingManifestError(ValueError):
    pass


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise StagingManifestError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _read_secret(path: Path, name: str, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing secret file: {name}")
        return ""
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        failures.append(f"empty secret file: {name}")
    elif "\n" in value or "\r" in value:
        failures.append(f"secret file must contain exactly one value: {name}")
    return value


def _validate_email(value: str, key: str, failures: list[str]) -> None:
    if (
        "@" not in value
        or value.endswith("@example.invalid")
        or value.startswith("@")
        or value.endswith("@")
    ):
        failures.append(f"{key} must be a real operations address.")


def _validate_https_url(value: str, key: str, failures: list[str]) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname in {"localhost", "127.0.0.1"}
        or parsed.hostname.endswith(".example.invalid")
    ):
        failures.append(f"{key} must be a real HTTPS URL.")


def _validate_database_url(
    value: str,
    key: str,
    expected_user: str,
    expected_password: str,
    failures: list[str],
) -> None:
    parsed = urlsplit(value)
    if not parsed.scheme.startswith("postgresql") or not parsed.hostname or not parsed.path.strip("/"):
        failures.append(f"{key} must be a complete PostgreSQL URL.")
        return
    if unquote(parsed.username or "") != expected_user:
        failures.append(f"{key} must use database role {expected_user}.")
    if unquote(parsed.password or "") != expected_password:
        failures.append(f"{key} password must match its external password secret.")
    if parsed.hostname in {"localhost", "127.0.0.1"}:
        failures.append(f"{key} must not target localhost.")


def _validate_secret_policy(values: dict[str, str], failures: list[str]) -> None:
    for name in (
        "rotas_owner_password",
        "rotas_app_password",
        "rotas_admin_password",
        "rotas_redis_password",
        "governance_database_password",
        "grafana_admin_password",
    ):
        if len(values.get(name, "")) < 16:
            failures.append(f"{name} must contain at least 16 characters.")

    for name in (
        "rotas_jwt_secret",
        "rotas_governance_api_key",
        "manager_governance_api_key",
        "governance_jwt_secret",
        "governance_platform_admin_key",
    ):
        value = values.get(name, "")
        if len(value) < 32 or any(token in value.lower() for token in ("change-me", "test-secret")):
            failures.append(f"{name} must be a non-default value of at least 32 characters.")

    if len(values.get("rotas_r2_access_key_id", "")) < 8:
        failures.append("rotas_r2_access_key_id must contain at least 8 characters.")
    if len(values.get("rotas_r2_secret_access_key", "")) < 16:
        failures.append("rotas_r2_secret_access_key must contain at least 16 characters.")
    _validate_https_url(
        values.get("alertmanager_webhook_url", ""),
        "alertmanager_webhook_url",
        failures,
    )

    _validate_database_url(
        values.get("rotas_database_url", ""),
        "rotas_database_url",
        "rotas_app",
        values.get("rotas_app_password", ""),
        failures,
    )
    _validate_database_url(
        values.get("rotas_admin_database_url", ""),
        "rotas_admin_database_url",
        "rotas_admin",
        values.get("rotas_admin_password", ""),
        failures,
    )
    _validate_database_url(
        values.get("rotas_alembic_database_url", ""),
        "rotas_alembic_database_url",
        "rotas_admin",
        values.get("rotas_admin_password", ""),
        failures,
    )
    _validate_database_url(
        values.get("governance_database_url", ""),
        "governance_database_url",
        "governance_app",
        values.get("governance_database_password", ""),
        failures,
    )

    redis_url = urlsplit(values.get("rotas_redis_url", ""))
    if (
        redis_url.scheme not in {"redis", "rediss"}
        or not redis_url.hostname
        or redis_url.hostname in {"localhost", "127.0.0.1"}
    ):
        failures.append("rotas_redis_url must be a complete non-local Redis URL.")
    if unquote(redis_url.password or "") != values.get("rotas_redis_password", ""):
        failures.append("rotas_redis_url password must match rotas_redis_password.")


def validate_static_policy(repo_root: Path) -> dict[str, int]:
    staging_root = repo_root / "infra" / "staging"
    compose_path = staging_root / "docker-compose.yml"
    compose = compose_path.read_text(encoding="utf-8")
    failures: list[str] = []

    forbidden = {
        "mutable latest tag": ":latest",
        "development bind mount": "- .:/",
        "development reload": "--reload",
        "inline build": "\n    build:",
        "hard-coded development password": "rotas_app_dev",
    }
    for label, token in forbidden.items():
        if token in compose:
            failures.append(f"{label}: {token!r}")

    for required in (
        "read_only: true",
        "no-new-privileges:true",
        "cap_drop:",
        "condition: service_completed_successfully",
        "internal: true",
        'ENVIRONMENT: production',
        'DATABASE_URL_FILE: /run/secrets/rotas_database_url',
        'VERSION: "${ROTAS_RELEASE_SHA:?ROTAS_RELEASE_SHA must be the full release SHA}"',
        'Strict-Transport-Security "max-age=31536000; includeSubDomains"',
    ):
        source = compose if required != 'Strict-Transport-Security "max-age=31536000; includeSubDomains"' else (
            staging_root / "Caddyfile"
        ).read_text(encoding="utf-8")
        if required not in source:
            failures.append(f"required staging control missing: {required}")

    literal_images = re.findall(r"^\s*image:\s*([^\s\"']+@sha256:[0-9a-f]{64})\s*$", compose, re.MULTILINE)
    if len(literal_images) < 3:
        failures.append("PostgreSQL, Redis and Caddy must use literal digest-pinned images.")
    for key in CUSTOM_IMAGE_KEYS:
        if f"${{{key}:?" not in compose:
            failures.append(f"{key} must be a required deployment input.")

    dockerfiles = (
        repo_root / "backend" / "Dockerfile",
        repo_root / "governance-engine" / "Dockerfile.production",
        repo_root / "apps" / "manager" / "Dockerfile",
        repo_root / "apps" / "driver" / "Dockerfile",
    )
    pinned_from_count = 0
    for dockerfile in dockerfiles:
        content = dockerfile.read_text(encoding="utf-8")
        known_stages: set[str] = set()
        for line in content.splitlines():
            if not line.startswith("FROM "):
                continue
            match = FROM_LINE.fullmatch(line)
            if match is None:
                failures.append(f"{dockerfile}: invalid FROM line: {line}")
                continue
            source = match.group("source")
            alias = match.group("alias")
            if source.lower() not in known_stages:
                if not re.search(r"@sha256:[0-9a-f]{64}$", source):
                    failures.append(f"{dockerfile}: external image is not pinned: {source}")
                else:
                    pinned_from_count += 1
            if alias:
                known_stages.add(alias.lower())
        if ":latest" in content:
            failures.append(f"{dockerfile}: latest tag is forbidden.")

    if failures:
        raise StagingManifestError("; ".join(failures))
    return {
        "literal_digest_images": len(literal_images),
        "pinned_dockerfile_stages": pinned_from_count,
        "custom_digest_inputs": len(CUSTOM_IMAGE_KEYS),
    }


def validate_deployment_inputs(env_path: Path) -> dict[str, int]:
    values = _read_env(env_path)
    failures: list[str] = []
    release_sha = values.get("ROTAS_RELEASE_SHA", "")
    if not RELEASE_SHA.fullmatch(release_sha):
        failures.append("ROTAS_RELEASE_SHA must be the full 40-character lowercase Git SHA.")

    image_references: list[str] = []
    for key in CUSTOM_IMAGE_KEYS:
        value = values.get(key, "")
        if not IMMUTABLE_IMAGE.fullmatch(value):
            failures.append(f"{key} must be an image reference pinned with @sha256.")
        elif "example.invalid" in value:
            failures.append(f"{key} still uses the example registry.")
        else:
            image_references.append(value)
    if len(set(image_references)) != len(image_references):
        failures.append("Each application component must use its own immutable image reference.")

    staging_hosts: list[str] = []
    for key in REQUIRED_HOST_KEYS:
        value = values.get(key, "")
        if not value or "example.invalid" in value or value in {"localhost", "127.0.0.1"}:
            failures.append(f"{key} must be a real staging hostname.")
        else:
            staging_hosts.append(value)
    if len(set(staging_hosts)) != len(staging_hosts):
        failures.append("Manager, Driver and API must use distinct hostnames.")

    _validate_email(values.get("ACME_EMAIL", ""), "ACME_EMAIL", failures)
    _validate_email(values.get("EMAIL_FROM_ADDRESS", ""), "EMAIL_FROM_ADDRESS", failures)
    _validate_https_url(values.get("R2_ENDPOINT_URL", ""), "R2_ENDPOINT_URL", failures)
    if not values.get("R2_BUCKET", "").strip():
        failures.append("R2_BUCKET is required.")
    try:
        UUID(values.get("ROTAS_GOVERNANCE_TENANT_ID", ""))
    except ValueError:
        failures.append("ROTAS_GOVERNANCE_TENANT_ID must be a valid UUID.")

    secrets_dir_raw = values.get("STAGING_SECRETS_DIR", "")
    secret_values: dict[str, str] = {}
    if not secrets_dir_raw:
        failures.append("STAGING_SECRETS_DIR is required.")
    else:
        secrets_dir = Path(secrets_dir_raw)
        if not secrets_dir.is_absolute():
            secrets_dir = (env_path.parent / secrets_dir).resolve()
        for secret_name in sorted(REQUIRED_SECRET_FILES):
            secret_values[secret_name] = _read_secret(
                secrets_dir / secret_name,
                secret_name,
                failures,
            )
        _validate_secret_policy(secret_values, failures)

    if failures:
        raise StagingManifestError("; ".join(failures))
    return {
        "release_sha": 1,
        "immutable_application_images": len(CUSTOM_IMAGE_KEYS),
        "staging_hosts": len(REQUIRED_HOST_KEYS),
        "secret_files": len(REQUIRED_SECRET_FILES),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--env-file", type=Path)
    args = parser.parse_args()
    try:
        result = {"static": validate_static_policy(args.repo_root.resolve())}
        if args.env_file:
            result["deployment"] = validate_deployment_inputs(args.env_file.resolve())
    except (OSError, StagingManifestError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
