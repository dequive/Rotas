"""Restore and verify one encrypted restic PostgreSQL snapshot."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts.dr_common import (
    DrError,
    postgres_environment,
    postgres_tool,
    query_scalar,
    read_single_value,
    restic_command,
    run_checked,
    validate_backup_manifest,
    validate_target_database,
)


def _find_one(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise DrError(f"Expected exactly one restored {name}; found {len(matches)}.")
    return matches[0]


def restore_snapshot(args: argparse.Namespace) -> dict[str, object]:
    validate_target_database(args.target_database)
    if not args.confirm_disposable_target:
        raise DrError("Refusing restore without --confirm-disposable-target.")
    if args.report_path.exists():
        raise DrError(f"Refusing to overwrite report: {args.report_path}")
    if not args.scratch_root.is_absolute() or not args.scratch_root.is_dir():
        raise DrError("Scratch root must be an existing absolute directory.")

    database_url = read_single_value(args.database_url_file, "database URL")
    database_env = postgres_environment(
        database_url,
        allow_localhost=args.local_drill,
    )
    exists = query_scalar(
        args.postgres_bin,
        database_env,
        (
            "SELECT count(*) FROM pg_database "
            f"WHERE datname = '{args.target_database}'"
        ),
        database="postgres",
    )
    if exists != "0":
        raise DrError("Restore target already exists; refusing to overwrite it.")

    started_at = datetime.now(UTC)
    target_created = False
    restore_seconds = 0.0
    manifest: dict[str, object]
    try:
        with tempfile.TemporaryDirectory(
            prefix="rotas-pr21-restore-",
            dir=args.scratch_root,
        ) as temporary:
            restore_root = Path(temporary)
            run_checked(
                restic_command(
                    ["restore", args.snapshot_id, "--target", "/restore-output"],
                    secrets_dir=args.restic_secrets_dir,
                    local_repository_dir=args.local_repository_dir,
                    input_mount=(restore_root, "/restore-output", False),
                ),
                timeout_seconds=args.timeout_seconds,
            )
            dump_path = _find_one(restore_root, "rotas.dump")
            manifest_path = _find_one(restore_root, "manifest.json")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            validate_backup_manifest(manifest, dump_path)

            run_checked(
                [
                    postgres_tool(args.postgres_bin, "createdb"),
                    args.target_database,
                ],
                env={**os.environ, **database_env, "PGDATABASE": "postgres"},
            )
            target_created = True
            restore_started = time.perf_counter()
            run_checked(
                [
                    postgres_tool(args.postgres_bin, "pg_restore"),
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    "--dbname",
                    args.target_database,
                    str(dump_path),
                ],
                env={**os.environ, **database_env},
                timeout_seconds=args.timeout_seconds,
            )
            restore_seconds = time.perf_counter() - restore_started

        restored_revision = query_scalar(
            args.postgres_bin,
            database_env,
            "SELECT version_num FROM alembic_version",
            database=args.target_database,
        )
        if restored_revision != manifest["alembic_revision"]:
            raise DrError(
                "Restored Alembic revision does not match the backup manifest."
            )
        table_count = int(
            query_scalar(
                args.postgres_bin,
                database_env,
                (
                    "SELECT count(*) FROM pg_tables "
                    "WHERE schemaname = 'public'"
                ),
                database=args.target_database,
            )
        )
        if table_count < args.minimum_tables:
            raise DrError(
                f"Restore has {table_count} public tables; "
                f"expected at least {args.minimum_tables}."
            )
        unbalanced_entries = int(
            query_scalar(
                args.postgres_bin,
                database_env,
                """
SELECT count(*) FROM (
  SELECT journal_entry_id
  FROM accounting_journal_items
  GROUP BY journal_entry_id
  HAVING sum(debit) <> sum(credit)
) AS unbalanced
""".strip(),
                database=args.target_database,
            )
        )
        if unbalanced_entries:
            raise DrError("Restored database contains unbalanced journal entries.")
        forced_rls_tables = int(
            query_scalar(
                args.postgres_bin,
                database_env,
                (
                    "SELECT count(*) FROM pg_class "
                    "WHERE relkind = 'r' AND relrowsecurity AND relforcerowsecurity"
                ),
                database=args.target_database,
            )
        )
        if forced_rls_tables < args.minimum_forced_rls_tables:
            raise DrError(
                f"Restore has only {forced_rls_tables} FORCE RLS tables."
            )

        completed_at = datetime.now(UTC)
        report: dict[str, object] = {
            "schema_version": 1,
            "gate": "PR-21",
            "started_at_utc": started_at.isoformat(),
            "completed_at_utc": completed_at.isoformat(),
            "snapshot_id": args.snapshot_id,
            "backup_id": manifest["backup_id"],
            "release_sha": manifest["release_sha"],
            "target_database": args.target_database,
            "restored_revision": restored_revision,
            "dump_sha256": manifest["dump_sha256"],
            "restore_seconds": round(restore_seconds, 3),
            "rto_target_minutes": args.rto_minutes,
            "rto_met_locally": restore_seconds <= args.rto_minutes * 60,
            "public_tables": table_count,
            "forced_rls_tables": forced_rls_tables,
            "unbalanced_journal_entries": unbalanced_entries,
            "local_drill": bool(args.local_drill),
        }
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return report
    finally:
        if target_created and args.drop_target_on_success and args.report_path.exists():
            run_checked(
                [
                    postgres_tool(args.postgres_bin, "dropdb"),
                    args.target_database,
                ],
                env={**os.environ, **database_env, "PGDATABASE": "postgres"},
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url-file", type=Path, required=True)
    parser.add_argument("--restic-secrets-dir", type=Path, required=True)
    parser.add_argument("--scratch-root", type=Path, required=True)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--target-database", required=True)
    parser.add_argument("--postgres-bin", type=Path, required=True)
    parser.add_argument("--local-repository-dir", type=Path)
    parser.add_argument("--rto-minutes", type=int, default=240)
    parser.add_argument("--minimum-tables", type=int, default=100)
    parser.add_argument("--minimum-forced-rls-tables", type=int, default=50)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--confirm-disposable-target", action="store_true")
    parser.add_argument("--local-drill", action="store_true")
    parser.add_argument("--drop-target-on-success", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = restore_snapshot(args)
    except (OSError, DrError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", "report": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
