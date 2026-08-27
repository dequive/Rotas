"""Fail-closed PR-25 paging, escalation and game-day certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.validate_incident_response import (
    REQUIRED_ROLES,
    REQUIRED_SCENARIOS,
    REQUIRED_SEVERITIES,
)
from scripts.validate_observability import REQUIRED_ALERTS
from scripts.validate_staging_manifest import CUSTOM_IMAGE_KEYS, IMMUTABLE_IMAGE

POLICY_ID = "PR25-INCIDENT-CERTIFICATION-V1"
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_UPSTREAMS = {
    "PR-20": "PR20-OBSERVABILITY-CERTIFICATION-V1",
    "PR-21": "PR21-DR-CERTIFICATION-V1",
    "PR-22": "PR22-PERFORMANCE-V1",
    "PR-23": "PR23-SECURITY-CERTIFICATION-V1",
}
REQUIRED_SIGNOFF_ROLES = {"PO", "QA", "SRE"}
REQUIRED_EVIDENCE = {
    "paging": {"paging_delivery_report", "roster_snapshot"},
    "escalation": {"communications_report", "escalation_timeline"},
    "game_day": {
        "failure_injection_log",
        "game_day_report",
        "postmortem_actions",
        "recovery_validation",
    },
    "signoff": {"attendance_report", "independent_signoff"},
}


class IncidentCertificationError(ValueError):
    pass


def _timestamp(value: object) -> datetime | None:
    text = str(value)
    if not RFC3339_Z.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _finite_non_negative(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


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
        blockers.append("evidence must contain exactly the four PR-25 evidence groups.")
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


def _validate_upstreams(
    upstreams: object,
    *,
    release_sha: str,
    blockers: list[str],
) -> None:
    if not isinstance(upstreams, dict) or set(upstreams) != set(REQUIRED_UPSTREAMS):
        blockers.append("upstreams must contain exactly PR-20 through PR-23.")
        return
    for pr_id, policy_id in REQUIRED_UPSTREAMS.items():
        result = upstreams.get(pr_id)
        if not isinstance(result, dict):
            blockers.append(f"upstreams.{pr_id} result is required.")
            continue
        if result.get("policy_id") != policy_id:
            blockers.append(f"upstreams.{pr_id} policy mismatch.")
        if result.get("release_sha") != release_sha:
            blockers.append(f"upstreams.{pr_id} release SHA mismatch.")
        if result.get("decision") != "PASS" or result.get("passed") is not True:
            blockers.append(f"upstreams.{pr_id} must be PASS.")
        if not FILE_SHA256.fullmatch(str(result.get("artifact_sha256", ""))):
            blockers.append(f"upstreams.{pr_id} artifact SHA-256 is invalid.")


def evaluate_incident_certification(
    context: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(context, dict):
        raise IncidentCertificationError(
            "Incident certification context must be an object."
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
    if _timestamp(context.get("observed_at")) is None:
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

    _validate_upstreams(
        context.get("upstreams"),
        release_sha=release_sha,
        blockers=blockers,
    )
    evidence_count = _validate_evidence(
        context.get("evidence"),
        base_dir=base_dir,
        release_sha=release_sha,
        blockers=blockers,
    )

    paging = context.get("paging")
    if not isinstance(paging, dict):
        blockers.append("paging result is required.")
    else:
        for key in (
            "external_roster",
            "primary_secondary_present",
            "real_provider",
            "delivery_observed",
            "acknowledgement_observed",
            "credentials_revoked_after_drill",
        ):
            if paging.get(key) is not True:
                blockers.append(f"paging.{key} must be true.")
        if str(paging.get("provider", "")).strip().lower() in {
            "",
            "console",
            "local",
            "null",
            "test",
        }:
            blockers.append("paging.provider must be a real external provider.")
        if not _exact_string_set(paging.get("alerts_exercised"), REQUIRED_ALERTS):
            blockers.append("paging.alerts_exercised set mismatch.")
        deliveries = paging.get("deliveries")
        if not isinstance(deliveries, list) or len(deliveries) < len(REQUIRED_ALERTS):
            blockers.append("paging.deliveries must cover every canonical alert.")
        elif not all(
            isinstance(item, dict)
            and str(item.get("delivery_id", "")).strip()
            and _timestamp(item.get("delivered_at")) is not None
            and _timestamp(item.get("acknowledged_at")) is not None
            and str(item.get("acknowledged_by_role", "")).strip()
            for item in deliveries
        ):
            blockers.append("paging.deliveries contain incomplete lifecycle evidence.")
        if not _zero_int(paging.get("undelivered_pages")):
            blockers.append("paging.undelivered_pages must be zero.")

    escalation = context.get("escalation")
    if not isinstance(escalation, dict):
        blockers.append("escalation result is required.")
    else:
        if not _exact_string_set(
            escalation.get("severities_exercised"),
            REQUIRED_SEVERITIES,
        ):
            blockers.append("escalation.severities_exercised set mismatch.")
        for key in (
            "human_acknowledgement",
            "secondary_escalation_observed",
            "incident_commander_assigned",
            "tenant_scoped_updates",
            "public_updates_exclude_tenant_identifiers",
            "cadence_met",
        ):
            if escalation.get(key) is not True:
                blockers.append(f"escalation.{key} must be true.")
        for key in (
            "ack_sla_breaches",
            "escalation_sla_breaches",
            "communication_sla_breaches",
        ):
            if not _zero_int(escalation.get(key)):
                blockers.append(f"escalation.{key} must be zero.")

    game_day = context.get("game_day")
    if not isinstance(game_day, dict):
        blockers.append("game_day result is required.")
    else:
        for key in (
            "production_like_staging",
            "release_candidate_used",
            "independent_facilitator",
            "failure_injection_real",
            "independent_recovery_validation",
            "audit_timeline_reconciled",
        ):
            if game_day.get(key) is not True:
                blockers.append(f"game_day.{key} must be true.")
        scenarios = game_day.get("scenarios")
        if not isinstance(scenarios, list):
            blockers.append("game_day.scenarios must be a list.")
            scenarios = []
        scenario_ids = {
            str(item.get("id", ""))
            for item in scenarios
            if isinstance(item, dict)
        }
        if scenario_ids != REQUIRED_SCENARIOS or len(scenarios) != len(
            REQUIRED_SCENARIOS
        ):
            blockers.append("game_day.scenarios set mismatch.")
        for index, scenario in enumerate(scenarios):
            if not isinstance(scenario, dict):
                blockers.append(f"game_day.scenarios[{index}] must be an object.")
                continue
            started = _timestamp(scenario.get("started_at"))
            recovered = _timestamp(scenario.get("recovered_at"))
            if started is None or recovered is None or recovered <= started:
                blockers.append(f"game_day.scenarios[{index}] timestamps are invalid.")
            for key in ("failure_injected", "recovered", "independently_validated"):
                if scenario.get(key) is not True:
                    blockers.append(f"game_day.scenarios[{index}].{key} must be true.")
            for key in ("containment_minutes", "recovery_minutes"):
                if not _finite_non_negative(scenario.get(key)):
                    blockers.append(
                        f"game_day.scenarios[{index}].{key} must be non-negative."
                    )
            if scenario.get("result") != "passed":
                blockers.append(f"game_day.scenarios[{index}].result must be passed.")
        for key in ("sev1_sev2_after_drill", "unreconciled_data_loss"):
            if not _zero_int(game_day.get(key)):
                blockers.append(f"game_day.{key} must be zero.")
        if game_day.get("measured_rpo_minutes", 16) > 15:
            blockers.append("game_day.measured_rpo_minutes must be at most 15.")
        if game_day.get("measured_rto_minutes", 241) > 240:
            blockers.append("game_day.measured_rto_minutes must be at most 240.")

    signoff = context.get("signoff")
    if not isinstance(signoff, dict):
        blockers.append("signoff result is required.")
    else:
        if not _exact_string_set(signoff.get("participants"), REQUIRED_ROLES):
            blockers.append("signoff.participants set mismatch.")
        if not _exact_string_set(signoff.get("approved_roles"), REQUIRED_SIGNOFF_ROLES):
            blockers.append("signoff.approved_roles set mismatch.")
        for key in (
            "attendance_verified",
            "postmortem_complete",
            "all_actions_closed",
            "actions_independently_verified",
            "test_access_removed",
            "temporary_changes_reverted",
        ):
            if signoff.get(key) is not True:
                blockers.append(f"signoff.{key} must be true.")
        if not _positive_int(signoff.get("attendees")):
            blockers.append("signoff.attendees must be positive.")
        for key in ("open_actions", "open_release_blockers"):
            if not _zero_int(signoff.get(key)):
                blockers.append(f"signoff.{key} must be zero.")

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
                "upstreams",
                "evidence must contain",
                "duplicate evidence path",
            )
        )
        for blocker in blockers
    )
    controls = {}
    for control in ("paging", "escalation", "game_day", "signoff"):
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
        result = evaluate_incident_certification(
            context,
            base_dir=context_path.parent,
        )
    except (OSError, json.JSONDecodeError, IncidentCertificationError) as exc:
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
