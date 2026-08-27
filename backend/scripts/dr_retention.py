"""Apply or preview the canonical encrypted-backup retention policy."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.dr_common import DrError, restic_command, run_checked

RETENTION_ARGS = [
    "--keep-hourly",
    "24",
    "--keep-daily",
    "7",
    "--keep-weekly",
    "5",
    "--keep-monthly",
    "12",
    "--keep-yearly",
    "7",
]
CONFIRMATION = "PR21-RETENTION-V1"


def retention_command(*, execute: bool) -> list[str]:
    command = ["forget", *RETENTION_ARGS, "--group-by", "host,tags", "--json"]
    if execute:
        command.append("--prune")
    else:
        command.append("--dry-run")
    return command


def run_retention(args: argparse.Namespace) -> dict[str, object]:
    if args.report_path.exists():
        raise DrError(f"Refusing to overwrite report: {args.report_path}")
    if args.execute and args.confirm_policy != CONFIRMATION:
        raise DrError(f"Execution requires --confirm-policy {CONFIRMATION}.")
    started_at = datetime.now(UTC)
    result = run_checked(
        restic_command(
            retention_command(execute=args.execute),
            secrets_dir=args.restic_secrets_dir,
            local_repository_dir=args.local_repository_dir,
        ),
        timeout_seconds=args.timeout_seconds,
    )
    if args.execute:
        run_checked(
            restic_command(
                ["check"],
                secrets_dir=args.restic_secrets_dir,
                local_repository_dir=args.local_repository_dir,
            ),
            timeout_seconds=args.timeout_seconds,
        )
    report: dict[str, object] = {
        "schema_version": 1,
        "gate": "PR-21",
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "policy": CONFIRMATION,
        "executed": bool(args.execute),
        "restic_output": json.loads(result.stdout or "[]"),
    }
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restic-secrets-dir", type=Path, required=True)
    parser.add_argument("--local-repository-dir", type=Path)
    parser.add_argument("--report-path", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-policy", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = run_retention(args)
    except (OSError, DrError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", "report": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
