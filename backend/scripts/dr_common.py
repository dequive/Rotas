"""Shared fail-closed primitives for encrypted PostgreSQL DR tooling."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

RESTIC_IMAGE = (
    "restic/restic@sha256:"
    "39d9072fb5651c80d75c7a811612eb60b4c06b32ffe87c2e9f3c7222e1797e76"
)
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
DR_TARGET = re.compile(r"^rotas_dr_[a-z0-9_]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class DrError(RuntimeError):
    pass


def read_single_value(path: Path, label: str) -> str:
    if not path.is_file():
        raise DrError(f"{label} file does not exist: {path}")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise DrError(f"{label} file is empty.")
    if "\n" in value or "\r" in value:
        raise DrError(f"{label} file must contain exactly one value.")
    return value


def postgres_environment(url: str, *, allow_localhost: bool) -> dict[str, str]:
    parsed = urlsplit(url)
    if not parsed.scheme.startswith("postgresql"):
        raise DrError("Database URL must use a PostgreSQL scheme.")
    if not parsed.hostname or not parsed.path.strip("/"):
        raise DrError("Database URL must contain host and database.")
    if not allow_localhost and parsed.hostname in {"localhost", "127.0.0.1"}:
        raise DrError("Production DR database URL must not target localhost.")
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    allowed_users = {"rotas_admin", "rotas_owner"}
    if allow_localhost:
        allowed_users.add("rotas")
    if user not in allowed_users:
        raise DrError("DR database URL must use rotas_admin or rotas_owner.")
    if not password:
        raise DrError("DR database URL must contain its external secret password.")
    return {
        "PGHOST": parsed.hostname,
        "PGPORT": str(parsed.port or 5432),
        "PGDATABASE": parsed.path.strip("/"),
        "PGUSER": user,
        "PGPASSWORD": password,
        "PGSSLMODE": "prefer" if allow_localhost else "require",
    }


def validate_release_sha(value: str) -> None:
    if not RELEASE_SHA.fullmatch(value):
        raise DrError("Release SHA must be 40 lowercase hexadecimal characters.")


def validate_target_database(value: str) -> None:
    if not DR_TARGET.fullmatch(value):
        raise DrError("Restore target must match rotas_dr_[a-z0-9_]+.")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_checked(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout_seconds: int = 3600,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise DrError(f"Command failed ({command[0]}): {stderr or 'no stderr'}")
    return completed


def postgres_tool(postgres_bin: Path, name: str) -> str:
    suffix = ".exe" if os.name == "nt" else ""
    path = postgres_bin / f"{name}{suffix}"
    if not path.is_file():
        raise DrError(f"Required PostgreSQL tool not found: {path}")
    return str(path)


def query_scalar(
    postgres_bin: Path,
    database_env: dict[str, str],
    sql: str,
    *,
    database: str | None = None,
) -> str:
    env = {**os.environ, **database_env}
    if database:
        env["PGDATABASE"] = database
    result = run_checked(
        [
            postgres_tool(postgres_bin, "psql"),
            "-X",
            "-A",
            "-t",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        env=env,
    )
    return result.stdout.strip()


def restic_secret_policy(secrets_dir: Path, *, local_repository: bool) -> None:
    repository = read_single_value(secrets_dir / "restic_repository", "repository")
    password = read_single_value(secrets_dir / "restic_password", "restic password")
    if len(password) < 32:
        raise DrError("Restic password must contain at least 32 characters.")
    if local_repository:
        if repository != "/repository":
            raise DrError("Local drill repository secret must contain /repository.")
        return
    if not repository.startswith("s3:https://"):
        raise DrError("Production restic repository must be an HTTPS S3 endpoint.")
    read_single_value(secrets_dir / "aws_access_key_id", "AWS access key")
    read_single_value(secrets_dir / "aws_secret_access_key", "AWS secret access key")


def restic_command(
    args: list[str],
    *,
    secrets_dir: Path,
    local_repository_dir: Path | None = None,
    input_mount: tuple[Path, str, bool] | None = None,
) -> list[str]:
    restic_secret_policy(
        secrets_dir,
        local_repository=local_repository_dir is not None,
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--mount",
        f"type=bind,source={secrets_dir.resolve()},target=/run/secrets,readonly",
    ]
    if local_repository_dir is not None:
        local_repository_dir.mkdir(parents=True, exist_ok=True)
        command.extend(
            [
                "--mount",
                (
                    f"type=bind,source={local_repository_dir.resolve()},"
                    "target=/repository"
                ),
            ]
        )
    if input_mount is not None:
        source, target, readonly = input_mount
        mount = f"type=bind,source={source.resolve()},target={target}"
        if readonly:
            mount += ",readonly"
        command.extend(["--mount", mount])
    script = """
export RESTIC_REPOSITORY="$(cat /run/secrets/restic_repository)"
export RESTIC_PASSWORD_FILE=/run/secrets/restic_password
if [ -s /run/secrets/aws_access_key_id ]; then
  export AWS_ACCESS_KEY_ID="$(cat /run/secrets/aws_access_key_id)"
  export AWS_SECRET_ACCESS_KEY="$(cat /run/secrets/aws_secret_access_key)"
fi
exec restic "$@"
""".strip()
    command.extend(
        [
            "--entrypoint",
            "/bin/sh",
            RESTIC_IMAGE,
            "-ec",
            script,
            "restic",
            *args,
        ]
    )
    return command


def parse_restic_snapshot(output: str) -> str:
    snapshot_id = ""
    for line in output.splitlines():
        try:
            item: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("message_type") == "summary":
            snapshot_id = str(item.get("snapshot_id") or "")
    if not snapshot_id:
        raise DrError("Restic backup output did not contain a snapshot ID.")
    return snapshot_id


def validate_backup_manifest(manifest: dict[str, Any], dump_path: Path) -> None:
    if manifest.get("schema_version") != 1:
        raise DrError("Unsupported DR manifest schema.")
    validate_release_sha(str(manifest.get("release_sha", "")))
    expected_hash = str(manifest.get("dump_sha256", ""))
    if not SHA256.fullmatch(expected_hash):
        raise DrError("DR manifest contains an invalid dump SHA-256.")
    if int(manifest.get("dump_bytes", -1)) != dump_path.stat().st_size:
        raise DrError("Restored dump size does not match its manifest.")
    if sha256_file(dump_path) != expected_hash:
        raise DrError("Restored dump checksum does not match its manifest.")
    if not manifest.get("alembic_revision"):
        raise DrError("DR manifest has no Alembic revision.")
