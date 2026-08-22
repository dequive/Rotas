"""Static validation for the PR-21 backup and disaster-recovery contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.dr_common import RESTIC_IMAGE


class DrPolicyError(ValueError):
    pass


def validate_dr_policy(repo_root: Path) -> dict[str, int]:
    policy_path = repo_root / "infra" / "dr" / "DR_POLICY.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    postgres = policy.get("postgresql", {})
    retention = policy.get("retention", {})
    storage = policy.get("storage", {})
    verification = policy.get("verification", {})

    if policy.get("policy_id") != "PR21-DR-V1":
        failures.append("Canonical DR policy ID is missing.")
    if postgres.get("rpo_minutes", 999999) > 15:
        failures.append("PostgreSQL RPO must be at most 15 minutes.")
    if postgres.get("rto_minutes", 999999) > 240:
        failures.append("PostgreSQL RTO must be at most 240 minutes.")
    if not postgres.get("independent_operator_required"):
        failures.append("Restore drills must require an independent operator.")

    expected_retention = {
        "hourly": 24,
        "daily": 7,
        "weekly": 5,
        "monthly": 12,
        "yearly": 7,
    }
    if retention != expected_retention:
        failures.append("Retention policy differs from PR21-RETENTION-V1.")
    if storage.get("client_side_encryption") != "restic":
        failures.append("Client-side encrypted backups are mandatory.")
    if storage.get("object_lock_days", 0) < 30:
        failures.append("Backup object lock must be at least 30 days.")
    if not storage.get("cross_region_copy") or not storage.get(
        "separate_failure_domain"
    ):
        failures.append("Backup copy must use a separate region and failure domain.")

    for key in (
        "manifest_sha256",
        "restic_check_each_backup",
        "alembic_revision",
        "balanced_journals",
    ):
        if not verification.get(key):
            failures.append(f"Required restore verification is disabled: {key}")

    tooling = "\n".join(
        (repo_root / "backend" / "scripts" / name).read_text(encoding="utf-8")
        for name in (
            "dr_common.py",
            "dr_backup.py",
            "dr_restore.py",
            "dr_retention.py",
        )
    )
    for required in (
        RESTIC_IMAGE.rsplit(":", 1)[-1],
        "rotas_dr_[a-z0-9_]+",
        "--confirm-encrypted-scratch",
        "temporary_plaintext_removed",
        "unbalanced_journal_entries",
        "PR21-RETENTION-V1",
    ):
        if required not in tooling:
            failures.append(f"DR tooling control is missing: {required}")

    if failures:
        raise DrPolicyError("; ".join(failures))
    return {
        "rpo_minutes": int(postgres["rpo_minutes"]),
        "rto_minutes": int(postgres["rto_minutes"]),
        "retention_tiers": len(retention),
        "verification_controls": sum(
            1 for value in verification.values() if value is True
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    args = parser.parse_args()
    try:
        result = validate_dr_policy(args.repo_root.resolve())
    except (OSError, json.JSONDecodeError, DrPolicyError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
