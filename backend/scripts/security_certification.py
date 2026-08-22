"""Fail-closed PR-23 independent security and privacy certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.validate_staging_manifest import (
    CUSTOM_IMAGE_KEYS,
    IMMUTABLE_IMAGE,
)

POLICY_ID = "PR23-SECURITY-CERTIFICATION-V1"
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_ROLES = {
    "unauthenticated",
    "tenant_a_admin",
    "tenant_a_limited",
    "tenant_b_admin",
    "tenant_a_driver",
    "platform_admin",
    "platform_support",
    "platform_billing",
    "rotas_app",
}
REQUIRED_SURFACES = {
    "edge_tls_headers",
    "authentication_session_mfa",
    "manager_bff_browser",
    "api_authorization",
    "platform_control_plane",
    "driver_offline_sync",
    "postgres_rls_grants",
    "object_storage",
    "finance_stock_workshop_billing",
    "outbox_governance_jobs_redis",
    "bi_tenant_scope",
    "rate_limits_concurrency",
}
REQUIRED_PRIVACY_CONTROLS = {
    "controller_processor_matrix",
    "purpose_lawful_basis",
    "retention_deletion",
    "data_subject_workflows",
    "immutable_record_exceptions",
    "tenant_offboarding",
    "subprocessor_contracts",
    "data_residency_transfers",
    "breach_response",
    "restricted_data_access",
}
REQUIRED_EVIDENCE = {
    "pentest_independent": {
        "pentest_authorization",
        "pentest_report",
        "scope_coverage",
    },
    "zero_high_critical": {"findings_register", "retest_report"},
    "privacy_approved": {
        "privacy_matrix",
        "legal_opinion",
        "subprocessor_register",
        "privacy_lifecycle_test",
    },
}


class SecurityCertificationError(ValueError):
    pass


def _timestamp(value: object) -> datetime | None:
    text = str(value)
    if not RFC3339_Z.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _zero_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


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
        blockers.append("evidence must contain exactly the three PR-23 evidence groups.")
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


def evaluate_security_certification(
    context: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(context, dict):
        raise SecurityCertificationError(
            "Security certification context must be an object."
        )
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
    observed_at = _timestamp(context.get("observed_at"))
    if observed_at is None:
        blockers.append("observed_at must be a valid UTC RFC3339 timestamp.")
    if context.get("external_runner") is not True:
        blockers.append("external_runner must be true.")

    images = context.get("images")
    if not isinstance(images, dict) or set(images) != set(CUSTOM_IMAGE_KEYS):
        blockers.append("images must contain exactly the four ROTAS RepoDigests.")
        images = {}
    references: set[str] = set()
    for image_key in sorted(CUSTOM_IMAGE_KEYS):
        reference = str(images.get(image_key, ""))
        if not IMMUTABLE_IMAGE.fullmatch(reference):
            blockers.append(f"images.{image_key} must be an immutable RepoDigest.")
        elif ".invalid/" in reference:
            blockers.append(f"images.{image_key} must not be a template placeholder.")
        elif reference in references:
            blockers.append(f"images.{image_key} RepoDigest must be unique.")
        references.add(reference)

    evidence_count = _validate_evidence(
        context.get("evidence"),
        base_dir=base_dir,
        release_sha=release_sha,
        blockers=blockers,
    )

    pentest = context.get("pentest_independent")
    if not isinstance(pentest, dict):
        blockers.append("pentest_independent result is required.")
    else:
        if pentest.get("release_sha") != release_sha:
            blockers.append("pentest_independent.release_sha mismatch.")
        for key in (
            "authorized",
            "completed",
            "independent_assessor",
            "no_conflict_of_interest",
            "two_tenants_overlapping_identifiers",
            "restricted_database_role_tested",
            "test_accounts_revoked",
            "allowlists_removed",
            "audit_logs_reconciled",
        ):
            if pentest.get(key) is not True:
                blockers.append(f"pentest_independent.{key} must be true.")
        for key in (
            "authorization_reference",
            "assessor_organization",
            "assessor_report_id",
            "encrypted_findings_channel",
        ):
            if not str(pentest.get(key, "")).strip():
                blockers.append(f"pentest_independent.{key} is required.")
        started = _timestamp(pentest.get("started_at"))
        completed = _timestamp(pentest.get("completed_at"))
        if started is None or completed is None or completed <= started:
            blockers.append("pentest_independent timestamps are invalid.")
        if not _exact_string_set(pentest.get("roles_tested"), REQUIRED_ROLES):
            blockers.append("pentest_independent.roles_tested set mismatch.")
        if not _exact_string_set(pentest.get("surfaces_tested"), REQUIRED_SURFACES):
            blockers.append("pentest_independent.surfaces_tested set mismatch.")
        if not _zero_int(pentest.get("stop_rule_incidents")):
            blockers.append("pentest_independent.stop_rule_incidents must be zero.")

    findings = context.get("zero_high_critical")
    if not isinstance(findings, dict):
        blockers.append("zero_high_critical result is required.")
    else:
        counts = findings.get("open_counts")
        if not isinstance(counts, dict) or set(counts) != {
            "critical",
            "high",
            "medium",
            "low",
        }:
            blockers.append("zero_high_critical.open_counts set mismatch.")
            counts = {}
        for severity in ("critical", "high", "medium", "low"):
            if not _non_negative_int(counts.get(severity)):
                blockers.append(
                    f"zero_high_critical.open_counts.{severity} is invalid."
                )
        if not _zero_int(counts.get("critical")) or not _zero_int(
            counts.get("high")
        ):
            blockers.append("zero_high_critical has open high/critical findings.")
        remediated = findings.get("remediated_findings")
        retested = findings.get("independently_retested_findings")
        if (
            not _non_negative_int(remediated)
            or not _non_negative_int(retested)
            or remediated != retested
        ):
            blockers.append("zero_high_critical remediation/retest counts mismatch.")
        if not _zero_int(findings.get("failed_retests")):
            blockers.append("zero_high_critical.failed_retests must be zero.")
        if findings.get("threat_model_items_tested") != 16:
            blockers.append("zero_high_critical must test all 16 baseline threats.")
        if not _zero_int(findings.get("unresolved_release_blockers")):
            blockers.append(
                "zero_high_critical.unresolved_release_blockers must be zero."
            )
        open_items = findings.get("open_medium_low")
        if not isinstance(open_items, list):
            blockers.append("zero_high_critical.open_medium_low must be a list.")
            open_items = []
        finding_ids: set[str] = set()
        for index, item in enumerate(open_items):
            if not isinstance(item, dict):
                blockers.append(
                    f"zero_high_critical.open_medium_low[{index}] must be an object."
                )
                continue
            finding_id = str(item.get("id", "")).strip()
            if not finding_id or finding_id in finding_ids:
                blockers.append(
                    f"zero_high_critical.open_medium_low[{index}] id is invalid."
                )
            finding_ids.add(finding_id)
            if item.get("severity") not in {"medium", "low"}:
                blockers.append(
                    f"zero_high_critical.open_medium_low[{index}] severity is invalid."
                )
            if not str(item.get("owner", "")).strip():
                blockers.append(
                    f"zero_high_critical.open_medium_low[{index}] owner is required."
                )
            due_at = _timestamp(item.get("due_at"))
            if due_at is None or (observed_at is not None and due_at <= observed_at):
                blockers.append(
                    f"zero_high_critical.open_medium_low[{index}] due_at is invalid."
                )
        if isinstance(counts, dict):
            medium_count = counts.get("medium")
            low_count = counts.get("low")
            if (
                _non_negative_int(medium_count)
                and _non_negative_int(low_count)
            ):
                assert isinstance(medium_count, int) and not isinstance(
                    medium_count, bool
                )
                assert isinstance(low_count, int) and not isinstance(low_count, bool)
                if medium_count + low_count != len(open_items):
                    blockers.append(
                        "zero_high_critical medium/low register count mismatch."
                    )

    privacy = context.get("privacy_approved")
    if not isinstance(privacy, dict):
        blockers.append("privacy_approved result is required.")
    else:
        for key in (
            "approved",
            "legal_review_independent",
            "tenant_contract_roles_defined",
            "privacy_lifecycle_tests_passed",
            "subprocessors_assessed",
            "cross_tenant_bi_governed",
        ):
            if privacy.get(key) is not True:
                blockers.append(f"privacy_approved.{key} must be true.")
        for key in (
            "jurisdiction",
            "legal_opinion_reference",
            "approver_name",
            "approver_role",
            "policy_version",
        ):
            if not str(privacy.get(key, "")).strip():
                blockers.append(f"privacy_approved.{key} is required.")
        if privacy.get("jurisdiction") != "MZ":
            blockers.append("privacy_approved.jurisdiction must be MZ.")
        signed_at = _timestamp(privacy.get("signed_at"))
        valid_until = _timestamp(privacy.get("valid_until"))
        if (
            signed_at is None
            or valid_until is None
            or valid_until <= signed_at
            or (observed_at is not None and valid_until <= observed_at)
        ):
            blockers.append("privacy_approved validity window is invalid.")
        if not _exact_string_set(
            privacy.get("controls_approved"),
            REQUIRED_PRIVACY_CONTROLS,
        ):
            blockers.append("privacy_approved.controls_approved set mismatch.")
        if not _zero_int(privacy.get("open_high_privacy_risks")):
            blockers.append("privacy_approved.open_high_privacy_risks must be zero.")
        if privacy.get("privacy_flows_tested") != 8:
            blockers.append("privacy_approved must test all eight privacy flows.")

    global_integrity_failed = any(
        blocker.startswith(
            (
                "schema_version",
                "policy_id",
                "environment",
                "release_sha",
                "observed_at",
                "external_runner",
                "images",
                "evidence must contain",
                "duplicate evidence path",
            )
        )
        for blocker in blockers
    )
    controls = {}
    for control in (
        "pentest_independent",
        "zero_high_critical",
        "privacy_approved",
    ):
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
        result = evaluate_security_certification(
            context,
            base_dir=context_path.parent,
        )
    except (OSError, json.JSONDecodeError, SecurityCertificationError) as exc:
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
