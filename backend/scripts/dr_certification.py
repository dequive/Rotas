"""Fail-closed PR-21 disaster-recovery certification bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

POLICY_ID = "PR21-DR-CERTIFICATION-V1"
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_JOURNEYS = {
    "authentication",
    "rls_multi_tenant",
    "workshop",
    "billing",
    "outbox",
}
REQUIRED_EVIDENCE = {
    "backup_restore": {
        "backup_report",
        "restore_report",
        "invariant_report",
        "observability_restore_report",
    },
    "pitr": {"pitr_report", "wal_archive_report"},
    "cross_region": {
        "primary_storage_report",
        "replica_storage_report",
        "object_lock_report",
    },
    "rpo_rto": {"timing_report", "independent_operator_report"},
}


class DrCertificationError(ValueError):
    pass


def _timestamp(value: object) -> datetime | None:
    text = str(value)
    if not RFC3339_Z.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _finite_float(value: object) -> float | None:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    ):
        return float(value)
    return None


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _exact_string_set(value: object, expected: set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and set(value) == expected
        and len(value) == len(expected)
    )


def _validate_evidence(
    evidence: object,
    *,
    base_dir: Path,
    release_sha: str,
    blockers: list[str],
) -> int:
    if not isinstance(evidence, dict) or set(evidence) != set(REQUIRED_EVIDENCE):
        blockers.append("evidence must contain exactly the four PR-21 evidence groups.")
        return 0
    count = 0
    observed_paths: set[str] = set()
    for group, required_kinds in REQUIRED_EVIDENCE.items():
        artifacts = evidence.get(group)
        if not isinstance(artifacts, list):
            blockers.append(f"evidence.{group} must be a list.")
            continue
        observed_kinds: set[str] = set()
        for index, artifact in enumerate(artifacts):
            if not isinstance(artifact, dict):
                blockers.append(f"evidence.{group}[{index}] must be an object.")
                continue
            kind = str(artifact.get("kind", ""))
            if kind in observed_kinds:
                blockers.append(f"evidence.{group} duplicate kind: {kind}.")
            observed_kinds.add(kind)
            relative_path = artifact.get("path")
            expected_hash = str(artifact.get("sha256", ""))
            if artifact.get("release_sha") != release_sha:
                blockers.append(f"evidence.{group}[{index}] release SHA mismatch.")
            if not isinstance(relative_path, str) or not relative_path:
                blockers.append(f"evidence.{group}[{index}] path is required.")
                continue
            if relative_path in observed_paths:
                blockers.append(f"duplicate evidence path: {relative_path}.")
            observed_paths.add(relative_path)
            if not FILE_SHA256.fullmatch(expected_hash):
                blockers.append(f"evidence.{group}[{index}] SHA-256 is invalid.")
                continue
            path = Path(relative_path)
            if not path.is_absolute():
                path = base_dir / path
            try:
                raw = path.read_bytes()
            except OSError as exc:
                blockers.append(f"cannot read evidence.{group}[{index}]: {exc}.")
                continue
            if hashlib.sha256(raw).hexdigest() != expected_hash:
                blockers.append(f"evidence.{group}[{index}] hash mismatch.")
                continue
            try:
                physical = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                blockers.append(f"evidence.{group}[{index}] is not valid JSON: {exc}.")
                continue
            if not isinstance(physical, dict):
                blockers.append(f"evidence.{group}[{index}] JSON must be an object.")
                continue
            if physical.get("kind") != kind:
                blockers.append(f"evidence.{group}[{index}] physical kind mismatch.")
            if physical.get("release_sha") != release_sha:
                blockers.append(
                    f"evidence.{group}[{index}] physical release SHA mismatch."
                )
            count += 1
        if observed_kinds != required_kinds:
            blockers.append(f"evidence.{group} kinds are incomplete or contain drift.")
    return count


def _expect_true(section: dict[str, Any], keys: tuple[str, ...], prefix: str, blockers: list[str]) -> None:
    for key in keys:
        if section.get(key) is not True:
            blockers.append(f"{prefix}.{key} must be true.")


def evaluate_dr_certification(
    context: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(context, dict):
        raise DrCertificationError("DR certification context must be an object.")
    if context.get("schema_version") != 1:
        blockers.append("schema_version must be 1.")
    if context.get("policy_id") != POLICY_ID:
        blockers.append(f"policy_id must be {POLICY_ID}.")
    if context.get("environment") != "staging":
        blockers.append("environment must be staging.")

    release_sha = str(context.get("release_sha", ""))
    if not RELEASE_SHA.fullmatch(release_sha):
        blockers.append("release_sha must be a full lowercase Git SHA.")
    elif release_sha == "0" * 40:
        blockers.append("release_sha must not be the template placeholder.")
    if _timestamp(context.get("observed_at")) is None:
        blockers.append("observed_at must be a valid UTC RFC3339 timestamp.")
    if context.get("external_runner") is not True:
        blockers.append("external_runner must be true.")
    operator = str(context.get("operator", "")).strip()
    backup_operator = str(context.get("backup_operator", "")).strip()
    if not operator or not backup_operator:
        blockers.append("operator and backup_operator are required.")
    elif operator == backup_operator:
        blockers.append("restore operator must be independent from backup operator.")

    evidence_count = _validate_evidence(
        context.get("evidence"),
        base_dir=base_dir,
        release_sha=release_sha,
        blockers=blockers,
    )

    backup_restore = context.get("backup_restore")
    if not isinstance(backup_restore, dict):
        blockers.append("backup_restore result is required.")
    else:
        if backup_restore.get("release_sha") != release_sha:
            blockers.append("backup_restore.release_sha mismatch.")
        if backup_restore.get("source_environment") != "staging":
            blockers.append("backup_restore.source_environment must be staging.")
        _expect_true(
            backup_restore,
            (
                "representative_volume",
                "data_authorized",
                "client_side_encrypted",
                "restic_read_data_clean",
                "manifest_checksum_verified",
                "temporary_plaintext_removed",
                "isolated_target",
                "restore_succeeded",
                "alembic_check_clean",
                "governance_restored",
                "observability_restored",
                "cleanup_completed",
            ),
            "backup_restore",
            blockers,
        )
        if not str(backup_restore.get("authorization_reference", "")).strip():
            blockers.append("backup_restore.authorization_reference is required.")
        if not str(backup_restore.get("snapshot_id", "")).strip():
            blockers.append("backup_restore.snapshot_id is required.")
        tenant_tables = backup_restore.get("tenant_tables")
        force_rls_tables = backup_restore.get("force_rls_tables")
        if (
            not _positive_int(tenant_tables)
            or not _positive_int(force_rls_tables)
            or tenant_tables != force_rls_tables
        ):
            blockers.append("backup_restore FORCE RLS coverage is incomplete.")
        if _finite_float(backup_restore.get("unbalanced_journal_entries")) != 0:
            blockers.append("backup_restore journals are not balanced.")
        if not _exact_string_set(
            backup_restore.get("journeys_passed"),
            REQUIRED_JOURNEYS,
        ):
            blockers.append("backup_restore.journeys_passed set mismatch.")

    pitr = context.get("pitr")
    if not isinstance(pitr, dict):
        blockers.append("pitr result is required.")
    else:
        _expect_true(
            pitr,
            (
                "wal_archiving_continuous",
                "restore_point_created",
                "restore_point_reached",
                "timeline_verified",
                "pitr_restore_succeeded",
            ),
            "pitr",
            blockers,
        )
        if _finite_float(pitr.get("archive_errors")) != 0:
            blockers.append("pitr.archive_errors must be zero.")
        target = _timestamp(pitr.get("target_time"))
        restored = _timestamp(pitr.get("restored_time"))
        if target is None or restored is None or restored < target:
            blockers.append("pitr target/restored timestamps are invalid.")
        data_loss = pitr.get("data_loss_seconds")
        data_loss_number = _finite_float(data_loss)
        if (
            data_loss_number is None
            or data_loss_number < 0
            or data_loss_number > 900
        ):
            blockers.append("pitr.data_loss_seconds must be between 0 and 900.")

    cross_region = context.get("cross_region")
    if not isinstance(cross_region, dict):
        blockers.append("cross_region result is required.")
    else:
        primary_region = str(cross_region.get("primary_region", "")).strip()
        replica_region = str(cross_region.get("replica_region", "")).strip()
        if not primary_region or not replica_region or primary_region == replica_region:
            blockers.append("cross_region regions must be non-empty and distinct.")
        _expect_true(
            cross_region,
            (
                "separate_failure_domain",
                "replica_encrypted",
                "versioning_enabled",
                "object_lock_verified",
                "restore_credentials_separated",
                "primary_unavailable_simulated",
                "restored_from_replica",
            ),
            "cross_region",
            blockers,
        )
        if (
            not _positive_int(cross_region.get("object_lock_days"))
            or cross_region["object_lock_days"] < 30
        ):
            blockers.append("cross_region.object_lock_days must be at least 30.")
        lag = cross_region.get("replication_lag_seconds")
        lag_number = _finite_float(lag)
        if lag_number is None or lag_number < 0 or lag_number > 900:
            blockers.append(
                "cross_region.replication_lag_seconds must be between 0 and 900."
            )

    rpo_rto = context.get("rpo_rto")
    if not isinstance(rpo_rto, dict):
        blockers.append("rpo_rto result is required.")
    else:
        _expect_true(
            rpo_rto,
            (
                "full_recovery_timed",
                "representative_load",
                "independent_operator_observed",
                "incident_paging_exercised",
            ),
            "rpo_rto",
            blockers,
        )
        rpo_minutes = rpo_rto.get("measured_rpo_minutes")
        rto_minutes = rpo_rto.get("measured_rto_minutes")
        rpo_number = _finite_float(rpo_minutes)
        rto_number = _finite_float(rto_minutes)
        if rpo_number is None or rpo_number < 0 or rpo_number > 15:
            blockers.append("rpo_rto.measured_rpo_minutes must be between 0 and 15.")
        if rto_number is None or rto_number <= 0 or rto_number > 240:
            blockers.append("rpo_rto.measured_rto_minutes must be between 0 and 240.")
        started = _timestamp(rpo_rto.get("started_at"))
        recovered = _timestamp(rpo_rto.get("recovered_at"))
        if started is None or recovered is None or recovered <= started:
            blockers.append("rpo_rto timestamps are invalid.")
        elif rto_number is not None:
            measured = (recovered - started).total_seconds() / 60
            if abs(measured - rto_number) > 0.1:
                blockers.append("rpo_rto measured duration does not match timestamps.")
        if not _positive_int(rpo_rto.get("restored_bytes")):
            blockers.append("rpo_rto.restored_bytes must be positive.")

    global_integrity_failed = any(
        blocker.startswith(
            (
                "schema_version",
                "policy_id",
                "environment",
                "release_sha",
                "observed_at",
                "external_runner",
                "operator and backup_operator",
                "restore operator",
                "evidence must contain",
                "duplicate evidence path",
            )
        )
        for blocker in blockers
    )
    controls = {}
    for control in ("backup_restore", "pitr", "cross_region", "rpo_rto"):
        controls[control] = not global_integrity_failed and not any(
            blocker.startswith(control)
            or blocker.startswith(f"evidence.{control}")
            for blocker in blockers
        )
    passed = not blockers
    return {
        "schema_version": 1,
        "artifact_type": "release_evidence_fragment",
        "policy_id": POLICY_ID,
        "release_sha": release_sha,
        "passed": passed,
        "decision": "PASS" if passed else "NO-GO",
        "controls": controls,
        "evidence_files": evidence_count,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        context_path = args.context.resolve()
        context = json.loads(context_path.read_text(encoding="utf-8"))
        result = evaluate_dr_certification(context, base_dir=context_path.parent)
    except (OSError, json.JSONDecodeError, DrCertificationError) as exc:
        result = {
            "schema_version": 1,
            "artifact_type": "release_evidence_fragment",
            "policy_id": POLICY_ID,
            "passed": False,
            "decision": "NO-GO",
            "blockers": [str(exc)],
        }
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
