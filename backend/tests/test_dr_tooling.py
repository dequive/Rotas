import json
from pathlib import Path

import pytest

from scripts.dr_common import (
    DrError,
    parse_restic_snapshot,
    postgres_environment,
    restic_secret_policy,
    sha256_file,
    validate_backup_manifest,
    validate_release_sha,
    validate_target_database,
)
from scripts.dr_retention import CONFIRMATION, retention_command
from scripts.validate_dr_policy import validate_dr_policy

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_postgres_environment_requires_admin_role_and_tls_in_production():
    env = postgres_environment(
        "postgresql+asyncpg://rotas_admin:secret@db.internal:5432/rotas",
        allow_localhost=False,
    )

    assert env == {
        "PGHOST": "db.internal",
        "PGPORT": "5432",
        "PGDATABASE": "rotas",
        "PGUSER": "rotas_admin",
        "PGPASSWORD": "secret",
        "PGSSLMODE": "require",
    }


def test_local_drill_allows_local_development_owner():
    env = postgres_environment(
        "postgresql://rotas:rotas@localhost:55432/rotas",
        allow_localhost=True,
    )

    assert env["PGUSER"] == "rotas"
    assert env["PGSSLMODE"] == "prefer"


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///rotas",
        "postgresql://rotas_app:secret@db.internal/rotas",
        "postgresql://rotas_admin:secret@localhost/rotas",
        "postgresql://rotas_admin@db.internal/rotas",
    ],
)
def test_postgres_environment_rejects_unsafe_sources(url):
    with pytest.raises(DrError):
        postgres_environment(url, allow_localhost=False)


def test_release_sha_and_restore_target_are_fail_closed():
    validate_release_sha("0123456789abcdef0123456789abcdef01234567")
    validate_target_database("rotas_dr_20260727")

    with pytest.raises(DrError):
        validate_release_sha("deadbeef")
    with pytest.raises(DrError):
        validate_target_database("rotas")


def test_restic_secret_policy_requires_strong_encrypted_repository(tmp_path):
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "restic_repository").write_text("/repository", encoding="utf-8")
    (secrets / "restic_password").write_text("x" * 32, encoding="utf-8")

    restic_secret_policy(secrets, local_repository=True)

    (secrets / "restic_password").write_text("short", encoding="utf-8")
    with pytest.raises(DrError, match="at least 32"):
        restic_secret_policy(secrets, local_repository=True)


def test_restic_snapshot_parser_requires_summary():
    output = "\n".join(
        [
            json.dumps({"message_type": "status", "seconds_elapsed": 1}),
            json.dumps({"message_type": "summary", "snapshot_id": "abc123"}),
        ]
    )
    assert parse_restic_snapshot(output) == "abc123"

    with pytest.raises(DrError):
        parse_restic_snapshot('{"message_type":"status"}')


def test_backup_manifest_detects_size_and_checksum_drift(tmp_path):
    dump = tmp_path / "rotas.dump"
    dump.write_bytes(b"synthetic-pg-dump")
    manifest = {
        "schema_version": 1,
        "release_sha": "0123456789abcdef0123456789abcdef01234567",
        "dump_sha256": sha256_file(dump),
        "dump_bytes": dump.stat().st_size,
        "alembic_revision": "rec13",
    }

    validate_backup_manifest(manifest, dump)

    dump.write_bytes(b"tampered")
    with pytest.raises(DrError, match="size|checksum"):
        validate_backup_manifest(manifest, dump)


def test_retention_is_dry_run_by_default_and_requires_explicit_execution():
    preview = retention_command(execute=False)
    execution = retention_command(execute=True)

    assert "--dry-run" in preview
    assert "--prune" not in preview
    assert "--prune" in execution
    assert "--dry-run" not in execution
    assert CONFIRMATION == "PR21-RETENTION-V1"


def test_dr_policy_is_fail_closed_and_versioned():
    assert validate_dr_policy(REPO_ROOT) == {
        "rpo_minutes": 15,
        "rto_minutes": 240,
        "retention_tiers": 5,
        "verification_controls": 4,
    }
