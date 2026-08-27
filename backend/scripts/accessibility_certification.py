"""Fail-closed PR-24 accessibility and principal-journey certification."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.validate_staging_manifest import CUSTOM_IMAGE_KEYS, IMMUTABLE_IMAGE

POLICY_ID = "PR24-ACCESSIBILITY-CERTIFICATION-V1"
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_ASSISTIVE_TECH = {
    "JAWS_Chrome",
    "NVDA_Firefox",
    "TalkBack_Chrome",
    "VoiceOver_Safari",
}
REQUIRED_MANUAL_CHECKS = {
    "authentication_and_errors",
    "content_language_and_dynamic_updates",
    "focus_not_obscured",
    "forced_colors_and_contrast",
    "keyboard_only",
    "modal_focus_and_escape",
    "orientation",
    "reflow_400_percent",
    "target_size",
    "zoom_200_percent",
}
REQUIRED_MOBILE_PLATFORMS = {"Android", "iOS"}
REQUIRED_ROLES = {
    "driver",
    "finance",
    "hr_manager",
    "platform_admin",
    "tenant_admin",
    "transport_dispatcher",
    "workshop_manager",
}
REQUIRED_JOURNEYS = {
    "accessible_authentication",
    "driver_pairing_offline_delivery",
    "finance_invoice_payment",
    "fleet_vehicle_driver",
    "hr_employee_payroll",
    "inventory_issue_return",
    "platform_tenant_lifecycle",
    "transport_order_trip_delivery",
    "workshop_reception_to_delivery",
}
REQUIRED_EVIDENCE = {
    "wcag_2_2_aa": {
        "axe_results",
        "conformance_report",
        "route_inventory",
    },
    "manual_assistive": {
        "assistive_matrix",
        "independent_audit",
        "keyboard_reflow_report",
    },
    "mobile_real": {
        "real_device_report",
        "touch_orientation_report",
    },
    "role_coverage": {
        "role_journey_report",
        "tenant_isolation_report",
        "user_acceptance_report",
    },
}


class AccessibilityCertificationError(ValueError):
    pass


def _timestamp(value: object) -> datetime | None:
    text = str(value)
    if not RFC3339_Z.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


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
        blockers.append("evidence must contain exactly the four PR-24 evidence groups.")
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


def evaluate_accessibility_certification(
    context: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(context, dict):
        raise AccessibilityCertificationError(
            "Accessibility certification context must be an object."
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

    evidence_count = _validate_evidence(
        context.get("evidence"),
        base_dir=base_dir,
        release_sha=release_sha,
        blockers=blockers,
    )

    wcag = context.get("wcag_2_2_aa")
    if not isinstance(wcag, dict):
        blockers.append("wcag_2_2_aa result is required.")
    else:
        if wcag.get("standard") != "WCAG 2.2":
            blockers.append("wcag_2_2_aa.standard must be WCAG 2.2.")
        if wcag.get("level") != "AA":
            blockers.append("wcag_2_2_aa.level must be AA.")
        for key in (
            "manager_build_passed",
            "driver_build_passed",
            "route_inventory_complete",
            "all_a_aa_criteria_evaluated",
        ):
            if wcag.get(key) is not True:
                blockers.append(f"wcag_2_2_aa.{key} must be true.")
        total_routes = wcag.get("total_routes")
        tested_routes = wcag.get("tested_routes")
        if (
            not _positive_int(total_routes)
            or not _positive_int(tested_routes)
            or total_routes != tested_routes
        ):
            blockers.append("wcag_2_2_aa route coverage must be complete.")
        for key in (
            "failed_a_aa_criteria",
            "critical_axe_violations",
            "serious_axe_violations",
            "skipped_tests",
            "unresolved_exceptions",
        ):
            if not _zero_int(wcag.get(key)):
                blockers.append(f"wcag_2_2_aa.{key} must be zero.")

    manual = context.get("manual_assistive")
    if not isinstance(manual, dict):
        blockers.append("manual_assistive result is required.")
    else:
        for key in (
            "independent_assessor",
            "no_conflict_of_interest",
            "audit_completed",
            "findings_retested",
        ):
            if manual.get(key) is not True:
                blockers.append(f"manual_assistive.{key} must be true.")
        for key in ("assessor_organization", "report_id"):
            if not str(manual.get(key, "")).strip():
                blockers.append(f"manual_assistive.{key} is required.")
        if not _exact_string_set(
            manual.get("assistive_technologies"),
            REQUIRED_ASSISTIVE_TECH,
        ):
            blockers.append("manual_assistive.assistive_technologies set mismatch.")
        if not _exact_string_set(
            manual.get("checks"),
            REQUIRED_MANUAL_CHECKS,
        ):
            blockers.append("manual_assistive.checks set mismatch.")
        for key in ("open_a_aa_findings", "failed_retests", "blocked_tasks"):
            if not _zero_int(manual.get(key)):
                blockers.append(f"manual_assistive.{key} must be zero.")

    mobile = context.get("mobile_real")
    if not isinstance(mobile, dict):
        blockers.append("mobile_real result is required.")
    else:
        for key in (
            "physical_devices",
            "portrait_tested",
            "landscape_tested",
            "touch_targets_passed",
            "one_handed_driver_journey_passed",
            "screen_reader_gestures_passed",
        ):
            if mobile.get(key) is not True:
                blockers.append(f"mobile_real.{key} must be true.")
        if not _exact_string_set(
            mobile.get("platforms"),
            REQUIRED_MOBILE_PLATFORMS,
        ):
            blockers.append("mobile_real.platforms set mismatch.")
        if not isinstance(mobile.get("devices"), list) or len(mobile["devices"]) < 2:
            blockers.append("mobile_real.devices must contain at least two real devices.")
        elif not all(
            isinstance(item, dict)
            and str(item.get("manufacturer", "")).strip()
            and str(item.get("model", "")).strip()
            and str(item.get("os_version", "")).strip()
            and item.get("physical") is True
            for item in mobile["devices"]
        ):
            blockers.append("mobile_real.devices contain invalid or emulated entries.")
        for key in ("failed_scenarios", "blocked_scenarios"):
            if not _zero_int(mobile.get(key)):
                blockers.append(f"mobile_real.{key} must be zero.")

    coverage = context.get("role_coverage")
    if not isinstance(coverage, dict):
        blockers.append("role_coverage result is required.")
    else:
        if not _exact_string_set(coverage.get("roles"), REQUIRED_ROLES):
            blockers.append("role_coverage.roles set mismatch.")
        if not _exact_string_set(coverage.get("journeys"), REQUIRED_JOURNEYS):
            blockers.append("role_coverage.journeys set mismatch.")
        for key in (
            "two_tenants_overlapping_identifiers",
            "all_states_covered",
            "tenant_isolation_verified",
            "po_approved",
            "user_acceptance_approved",
        ):
            if coverage.get(key) is not True:
                blockers.append(f"role_coverage.{key} must be true.")
        if not _positive_int(coverage.get("participants")):
            blockers.append("role_coverage.participants must be positive.")
        for key in ("failed_journeys", "skipped_journeys", "cross_tenant_leaks"):
            if not _zero_int(coverage.get(key)):
                blockers.append(f"role_coverage.{key} must be zero.")

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
        "wcag_2_2_aa",
        "manual_assistive",
        "mobile_real",
        "role_coverage",
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
        result = evaluate_accessibility_certification(
            context,
            base_dir=context_path.parent,
        )
    except (OSError, json.JSONDecodeError, AccessibilityCertificationError) as exc:
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
