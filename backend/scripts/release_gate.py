"""Canonical fail-closed GO/NO-GO decision for the ROTAS G4 release gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
SIGNED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_CONTROLS = {
    "PR-18": {
        "no_unwaived_high_critical",
        "valid_dependency_graph",
        "sbom_attested",
    },
    "PR-19": {
        "immutable_images",
        "tls",
        "external_secrets",
        "migrations",
    },
    "PR-20": {
        "metrics",
        "logs",
        "traces",
        "alerts_delivered",
        "slo_window",
    },
    "PR-21": {
        "backup_restore",
        "pitr",
        "cross_region",
        "rpo_rto",
    },
    "PR-22": {
        "two_tenants",
        "performance_budgets",
        "network_degraded",
        "soak",
    },
    "PR-23": {
        "pentest_independent",
        "zero_high_critical",
        "privacy_approved",
    },
    "PR-24": {
        "wcag_2_2_aa",
        "manual_assistive",
        "mobile_real",
        "role_coverage",
    },
    "PR-25": {
        "paging",
        "escalation",
        "game_day",
        "signoff",
    },
}
REQUIRED_SIGNOFFS = {
    "PR-18": {"SEC", "TL"},
    "PR-19": {"SRE", "TL"},
    "PR-20": {"SRE", "BE"},
    "PR-21": {"SRE", "QA"},
    "PR-22": {"QA", "SRE"},
    "PR-23": {"SEC", "TL"},
    "PR-24": {"FE-M", "FE-D", "PO"},
    "PR-25": {"SRE", "PO"},
}


class ReleaseGateError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate_release_gate(
    manifest: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(manifest, dict):
        raise ReleaseGateError("Release manifest must be an object.")
    if manifest.get("schema_version") != 1:
        blockers.append("schema_version must be 1.")
    release_sha = str(manifest.get("release_sha", ""))
    if not RELEASE_SHA.fullmatch(release_sha):
        blockers.append("release_sha must be a full lowercase Git SHA.")
    if manifest.get("requested_decision") != "GO":
        blockers.append("requested_decision must be GO for an approval attempt.")

    workstreams = manifest.get("workstreams")
    if not isinstance(workstreams, dict) or set(workstreams) != set(REQUIRED_CONTROLS):
        blockers.append("workstreams must contain exactly PR-18 through PR-25.")
        workstreams = {}

    evidence_files = 0
    signoff_count = 0
    for pr_id in REQUIRED_CONTROLS:
        item = workstreams.get(pr_id)
        if not isinstance(item, dict):
            blockers.append(f"{pr_id}: workstream evidence is missing.")
            continue
        controls = item.get("controls")
        if not isinstance(controls, dict) or set(controls) != REQUIRED_CONTROLS[pr_id]:
            blockers.append(f"{pr_id}: control set is incomplete or contains drift.")
        else:
            for control, passed in controls.items():
                if passed is not True:
                    blockers.append(f"{pr_id}: control is not green: {control}.")

        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            blockers.append(f"{pr_id}: at least one hashed evidence file is required.")
            evidence = []
        valid_evidence_hashes: list[str] = []
        for index, artifact in enumerate(evidence):
            if not isinstance(artifact, dict):
                blockers.append(f"{pr_id}: evidence {index} must be an object.")
                continue
            relative_path = artifact.get("path")
            expected_hash = str(artifact.get("sha256", ""))
            if artifact.get("release_sha") != release_sha:
                blockers.append(f"{pr_id}: evidence {index} release SHA mismatch.")
            if not isinstance(relative_path, str) or not relative_path:
                blockers.append(f"{pr_id}: evidence {index} path is required.")
                continue
            if not FILE_SHA256.fullmatch(expected_hash):
                blockers.append(f"{pr_id}: evidence {index} SHA-256 is invalid.")
                continue
            path = Path(relative_path)
            if not path.is_absolute():
                path = base_dir / path
            try:
                actual_hash = sha256_file(path)
            except OSError as exc:
                blockers.append(f"{pr_id}: cannot read evidence {index}: {exc}.")
                continue
            if actual_hash != expected_hash:
                blockers.append(f"{pr_id}: evidence {index} hash mismatch.")
                continue
            evidence_files += 1
            valid_evidence_hashes.append(expected_hash)

        evidence_digest = hashlib.sha256(
            "".join(sorted(valid_evidence_hashes)).encode("ascii")
        ).hexdigest()

        signoffs = item.get("signoffs")
        observed_roles: set[str] = set()
        approvers: set[str] = set()
        if not isinstance(signoffs, list):
            blockers.append(f"{pr_id}: signoffs are required.")
            signoffs = []
        for signoff in signoffs:
            if not isinstance(signoff, dict):
                blockers.append(f"{pr_id}: signoff must be an object.")
                continue
            role = str(signoff.get("role", ""))
            approver = str(signoff.get("approver", "")).strip()
            if (
                signoff.get("approved") is not True
                or not approver
                or signoff.get("release_sha") != release_sha
                or signoff.get("evidence_digest") != evidence_digest
                or not SIGNED_AT.fullmatch(str(signoff.get("signed_at", "")))
            ):
                blockers.append(f"{pr_id}: signoff for {role or 'unknown'} is incomplete.")
                continue
            if approver in approvers:
                blockers.append(f"{pr_id}: one approver cannot sign twice.")
                continue
            observed_roles.add(role)
            approvers.add(approver)
            signoff_count += 1
        if observed_roles != REQUIRED_SIGNOFFS[pr_id]:
            blockers.append(f"{pr_id}: required signoff roles are incomplete.")

    decision = "GO" if not blockers else "NO-GO"
    return {
        "schema_version": 1,
        "gate": "G4",
        "release_sha": release_sha,
        "decision": decision,
        "workstreams": len(workstreams),
        "evidence_files": evidence_files,
        "signoffs": signoff_count,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        manifest_path = args.manifest.resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result = evaluate_release_gate(manifest, base_dir=manifest_path.parent)
    except (OSError, json.JSONDecodeError, ReleaseGateError) as exc:
        result = {
            "schema_version": 1,
            "gate": "G4",
            "decision": "NO-GO",
            "blockers": [str(exc)],
        }
    output = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if result["decision"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
