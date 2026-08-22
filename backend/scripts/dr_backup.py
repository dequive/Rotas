"""Create a PostgreSQL custom dump and archive it in encrypted restic storage."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from scripts.dr_common import (
    DrError,
    parse_restic_snapshot,
    postgres_environment,
    postgres_tool,
    query_scalar,
    read_single_value,
    restic_command,
    run_checked,
    sha256_file,
    validate_release_sha,
)


def create_backup(args: argparse.Namespace) -> dict[str, object]:
    validate_release_sha(args.release_sha)
    if not args.confirm_anonymized and not (
        args.local_drill and args.confirm_nonproduction_source
    ):
        raise DrError(
            "Refusing backup without --confirm-anonymized, or the local-drill "
            "--confirm-nonproduction-source alternative."
        )
    if not args.local_drill and not args.confirm_encrypted_scratch:
        raise DrError("Production backup requires --confirm-encrypted-scratch.")
    if args.report_path.exists():
        raise DrError(f"Refusing to overwrite report: {args.report_path}")
    if not args.scratch_root.is_absolute() or not args.scratch_root.is_dir():
        raise DrError("Scratch root must be an existing absolute directory.")

    database_url = read_single_value(args.database_url_file, "database URL")
    database_env = postgres_environment(
        database_url,
        allow_localhost=args.local_drill,
    )
    backup_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)

    with tempfile.TemporaryDirectory(
        prefix="rotas-pr21-",
        dir=args.scratch_root,
    ) as temporary:
        workdir = Path(temporary)
        dump_path = workdir / "rotas.dump"
        manifest_path = workdir / "manifest.json"
        alembic_revision = query_scalar(
            args.postgres_bin,
            database_env,
            "SELECT version_num FROM alembic_version",
        )
        source_timestamp = query_scalar(
            args.postgres_bin,
            database_env,
            "SELECT CURRENT_TIMESTAMP AT TIME ZONE 'UTC'",
        )

        dump_started = time.perf_counter()
        run_checked(
            [
                postgres_tool(args.postgres_bin, "pg_dump"),
                "--format=custom",
                "--compress=6",
                "--no-owner",
                "--no-privileges",
                f"--file={dump_path}",
            ],
            env={**os.environ, **database_env},
            timeout_seconds=args.timeout_seconds,
        )
        dump_seconds = time.perf_counter() - dump_started
        manifest = {
            "schema_version": 1,
            "gate": "PR-21",
            "backup_id": backup_id,
            "created_at_utc": started_at.isoformat(),
            "source_timestamp_utc": source_timestamp,
            "release_sha": args.release_sha,
            "alembic_revision": alembic_revision,
            "dump_format": "postgresql-custom",
            "dump_bytes": dump_path.stat().st_size,
            "dump_sha256": sha256_file(dump_path),
            "rpo_target_minutes": args.rpo_minutes,
            "rto_target_minutes": args.rto_minutes,
            "scratch_encrypted_or_memory_backed": bool(
                args.confirm_encrypted_scratch
            ),
            "anonymized_source_confirmed": bool(args.confirm_anonymized),
            "nonproduction_source_confirmed": bool(
                args.confirm_nonproduction_source
            ),
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        if args.initialize_repository:
            run_checked(
                restic_command(
                    ["init"],
                    secrets_dir=args.restic_secrets_dir,
                    local_repository_dir=args.local_repository_dir,
                ),
                timeout_seconds=args.timeout_seconds,
            )
        backup_result = run_checked(
            restic_command(
                [
                    "backup",
                    "/backup-input",
                    "--json",
                    "--tag",
                    "rotas",
                    "--tag",
                    "postgresql",
                    "--tag",
                    f"release:{args.release_sha}",
                    "--tag",
                    f"backup:{backup_id}",
                ],
                secrets_dir=args.restic_secrets_dir,
                local_repository_dir=args.local_repository_dir,
                input_mount=(workdir, "/backup-input", True),
            ),
            timeout_seconds=args.timeout_seconds,
        )
        snapshot_id = parse_restic_snapshot(backup_result.stdout)
        check_started = time.perf_counter()
        check_args = ["check"]
        if args.read_data:
            check_args.append("--read-data")
        run_checked(
            restic_command(
                check_args,
                secrets_dir=args.restic_secrets_dir,
                local_repository_dir=args.local_repository_dir,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        check_seconds = time.perf_counter() - check_started

    completed_at = datetime.now(UTC)
    report: dict[str, object] = {
        **manifest,
        "completed_at_utc": completed_at.isoformat(),
        "snapshot_id": snapshot_id,
        "dump_seconds": round(dump_seconds, 3),
        "restic_check_seconds": round(check_seconds, 3),
        "local_drill": bool(args.local_drill),
        "encrypted_repository": True,
        "temporary_plaintext_removed": True,
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url-file", type=Path, required=True)
    parser.add_argument("--restic-secrets-dir", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--local-repository-dir", type=Path)
    parser.add_argument("--rpo-minutes", type=int, default=15)
    parser.add_argument("--rto-minutes", type=int, default=240)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--confirm-anonymized", action="store_true")
    parser.add_argument("--confirm-nonproduction-source", action="store_true")
    parser.add_argument("--confirm-encrypted-scratch", action="store_true")
    parser.add_argument("--local-drill", action="store_true")
    parser.add_argument("--initialize-repository", action="store_true")
    parser.add_argument("--read-data", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = create_backup(args)
    except (OSError, DrError, ValueError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", "report": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
