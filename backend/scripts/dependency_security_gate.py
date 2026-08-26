"""PR-18 dependency graph, audit and CycloneDX evidence generator."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

NODE_VERSION = re.compile(r"^v(?P<major>\d+)\.")
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
WAIVER_ID = re.compile(r"^[A-Z0-9][A-Z0-9_-]{5,63}$")
REQUIRED_WAIVER_APPROVERS = {"SEC", "TL"}
MAX_WAIVER_LIFETIME = timedelta(days=30)


class DependencySecurityError(ValueError):
    pass


def _audit_counts(payload: dict[str, Any]) -> dict[str, int]:
    vulnerabilities = payload.get("metadata", {}).get("vulnerabilities", {})
    return {
        severity: int(vulnerabilities.get(severity, 0))
        for severity in ("info", "low", "moderate", "high", "critical", "total")
    }


def _audit_payload_valid(payload: dict[str, Any]) -> bool:
    metadata = payload.get("metadata")
    vulnerabilities = payload.get("vulnerabilities")
    if (
        payload.get("auditReportVersion") != 2
        or not isinstance(metadata, dict)
        or not isinstance(vulnerabilities, dict)
    ):
        return False
    counts = metadata.get("vulnerabilities")
    if not isinstance(counts, dict):
        return False
    severities = ("info", "low", "moderate", "high", "critical")
    if any(
        not isinstance(counts.get(severity), int) or counts[severity] < 0
        for severity in severities
    ):
        return False
    total = counts.get("total")
    return isinstance(total, int) and total == sum(counts[item] for item in severities)


def _audit_command_valid(exit_code: int, payload: dict[str, Any]) -> bool:
    if not _audit_payload_valid(payload):
        return False
    expected_exit_code = 0 if _audit_counts(payload)["total"] == 0 else 1
    return exit_code == expected_exit_code


def _security_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    vulnerabilities = payload.get("vulnerabilities", {})
    if not isinstance(vulnerabilities, dict):
        return findings
    for package, raw_details in vulnerabilities.items():
        if not isinstance(raw_details, dict):
            continue
        severity = str(raw_details.get("severity", "")).lower()
        if severity not in {"high", "critical"}:
            continue
        advisories: set[str] = set()
        for item in raw_details.get("via", []):
            if not isinstance(item, dict):
                continue
            reference = item.get("url") or item.get("source")
            if reference is not None:
                advisories.add(str(reference))
        findings.append(
            {
                "package": str(package),
                "severity": severity,
                "affected_range": str(raw_details.get("range", "")),
                "advisories": sorted(advisories),
            }
        )
    return sorted(
        findings,
        key=lambda item: (
            item["package"],
            item["severity"],
            item["affected_range"],
        ),
    )


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise DependencySecurityError(f"{field} must be an ISO-8601 UTC timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DependencySecurityError(
            f"{field} must be an ISO-8601 UTC timestamp."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise DependencySecurityError(f"{field} must use UTC.")
    return parsed.astimezone(UTC)


def evaluate_security_waivers(
    *,
    waiver_manifest: dict[str, Any] | None,
    release_sha: str | None,
    production_findings: list[dict[str, Any]],
    complete_findings: list[dict[str, Any]],
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    now = (evaluated_at or datetime.now(UTC)).astimezone(UTC)
    all_findings = {
        (
            finding["package"],
            finding["severity"],
            finding["affected_range"],
            tuple(finding["advisories"]),
        ): finding
        for finding in [*production_findings, *complete_findings]
    }
    errors: list[str] = []
    valid_waiver_ids: list[str] = []
    covered_keys: set[tuple[str, str, str, tuple[str, ...]]] = set()

    if waiver_manifest is None:
        waivers: list[Any] = []
    else:
        if waiver_manifest.get("schema_version") != 1:
            errors.append("waiver manifest schema_version must be 1.")
        if (
            not isinstance(release_sha, str)
            or RELEASE_SHA.fullmatch(release_sha) is None
            or waiver_manifest.get("release_sha") != release_sha
        ):
            errors.append("waiver manifest must be bound to the release SHA.")
        raw_waivers = waiver_manifest.get("waivers")
        if not isinstance(raw_waivers, list):
            errors.append("waiver manifest waivers must be a list.")
            waivers = []
        else:
            waivers = raw_waivers

    manifest_binding_valid = not errors
    seen_ids: set[str] = set()
    for index, raw_waiver in enumerate(waivers):
        prefix = f"waiver[{index}]"
        waiver_errors: list[str] = []
        if not isinstance(raw_waiver, dict):
            errors.append(f"{prefix} must be an object.")
            continue

        waiver_id = raw_waiver.get("id")
        if (
            not isinstance(waiver_id, str)
            or WAIVER_ID.fullmatch(waiver_id) is None
        ):
            waiver_errors.append(f"{prefix}.id is invalid.")
        elif waiver_id in seen_ids:
            waiver_errors.append(f"{prefix}.id is duplicated.")
        else:
            seen_ids.add(waiver_id)

        severity = str(raw_waiver.get("severity", "")).lower()
        if severity != "high":
            waiver_errors.append(f"{prefix} may waive high severity only.")
        package = raw_waiver.get("package")
        affected_range = raw_waiver.get("affected_range")
        if not isinstance(package, str) or not package:
            waiver_errors.append(f"{prefix}.package is required.")
        if not isinstance(affected_range, str) or not affected_range:
            waiver_errors.append(f"{prefix}.affected_range is required.")

        advisories = raw_waiver.get("advisories")
        if (
            not isinstance(advisories, list)
            or any(not isinstance(item, str) or not item for item in advisories)
        ):
            waiver_errors.append(f"{prefix}.advisories must be a string list.")
            advisory_set: set[str] = set()
        else:
            advisory_set = set(advisories)

        justification = raw_waiver.get("justification")
        if not isinstance(justification, str) or len(justification.strip()) < 40:
            waiver_errors.append(
                f"{prefix}.justification must contain at least 40 characters."
            )
        controls = raw_waiver.get("compensating_controls")
        if (
            not isinstance(controls, list)
            or len(set(controls)) < 2
            or any(not isinstance(item, str) or not item.strip() for item in controls)
        ):
            waiver_errors.append(
                f"{prefix}.compensating_controls must contain two distinct controls."
            )
        ticket = raw_waiver.get("tracking_url")
        if not isinstance(ticket, str) or not ticket.startswith("https://"):
            waiver_errors.append(f"{prefix}.tracking_url must use HTTPS.")

        owner = raw_waiver.get("owner")
        if (
            not isinstance(owner, dict)
            or not isinstance(owner.get("identifier"), str)
            or not owner.get("identifier")
            or not isinstance(owner.get("role"), str)
            or not owner.get("role")
        ):
            waiver_errors.append(f"{prefix}.owner identifier and role are required.")

        try:
            created_at = _parse_utc(
                raw_waiver.get("created_at"),
                field=f"{prefix}.created_at",
            )
            expires_at = _parse_utc(
                raw_waiver.get("expires_at"),
                field=f"{prefix}.expires_at",
            )
            if created_at > now:
                waiver_errors.append(f"{prefix}.created_at cannot be in the future.")
            if expires_at <= now:
                waiver_errors.append(f"{prefix} is expired.")
            if expires_at <= created_at:
                waiver_errors.append(f"{prefix}.expires_at must follow created_at.")
            if expires_at - created_at > MAX_WAIVER_LIFETIME:
                waiver_errors.append(f"{prefix} lifetime exceeds 30 days.")
        except DependencySecurityError as exc:
            waiver_errors.append(str(exc))

        approvals = raw_waiver.get("approvals")
        approval_roles: set[str] = set()
        approval_identities: set[str] = set()
        if not isinstance(approvals, list):
            waiver_errors.append(f"{prefix}.approvals must be a list.")
        else:
            for approval_index, approval in enumerate(approvals):
                approval_prefix = f"{prefix}.approvals[{approval_index}]"
                if not isinstance(approval, dict):
                    waiver_errors.append(f"{approval_prefix} must be an object.")
                    continue
                role = approval.get("role")
                identity = approval.get("approver")
                if role not in REQUIRED_WAIVER_APPROVERS:
                    waiver_errors.append(f"{approval_prefix}.role is invalid.")
                else:
                    approval_roles.add(str(role))
                if not isinstance(identity, str) or not identity:
                    waiver_errors.append(f"{approval_prefix}.approver is required.")
                elif identity in approval_identities:
                    waiver_errors.append(
                        f"{prefix} approver identities must be distinct."
                    )
                else:
                    approval_identities.add(identity)
                if approval.get("approved") is not True:
                    waiver_errors.append(f"{approval_prefix} is not approved.")
                if approval.get("release_sha") != release_sha:
                    waiver_errors.append(
                        f"{approval_prefix} is not bound to the release SHA."
                    )
                try:
                    signed_at = _parse_utc(
                        approval.get("signed_at"),
                        field=f"{approval_prefix}.signed_at",
                    )
                    if signed_at > now:
                        waiver_errors.append(
                            f"{approval_prefix}.signed_at cannot be in the future."
                        )
                except DependencySecurityError as exc:
                    waiver_errors.append(str(exc))
        if approval_roles != REQUIRED_WAIVER_APPROVERS:
            waiver_errors.append(f"{prefix} requires SEC and TL approvals.")

        matching_keys = []
        for key, finding in all_findings.items():
            if (
                finding["package"] == package
                and finding["severity"] == severity
                and finding["affected_range"] == affected_range
                and set(finding["advisories"]).issubset(advisory_set)
            ):
                matching_keys.append(key)
        if not matching_keys:
            waiver_errors.append(f"{prefix} does not match a current finding.")

        if waiver_errors:
            errors.extend(waiver_errors)
        elif manifest_binding_valid:
            valid_waiver_ids.append(str(waiver_id))
            covered_keys.update(matching_keys)

    def _unwaived(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            finding
            for finding in findings
            if (
                finding["package"],
                finding["severity"],
                finding["affected_range"],
                tuple(finding["advisories"]),
            )
            not in covered_keys
        ]

    return {
        "provided": waiver_manifest is not None,
        "valid": not errors,
        "max_lifetime_days": MAX_WAIVER_LIFETIME.days,
        "valid_waiver_ids": sorted(valid_waiver_ids),
        "errors": errors,
        "production_unwaived": _unwaived(production_findings),
        "complete_unwaived": _unwaived(complete_findings),
    }


def evaluate_dependency_security(
    *,
    production_audit: dict[str, Any],
    complete_audit: dict[str, Any],
    production_audit_exit_code: int,
    complete_audit_exit_code: int,
    tree_exit_code: int,
    tree: dict[str, Any],
    sbom: dict[str, Any],
    node_version: str,
    npm_version: str,
    profile: str,
    release_sha: str | None,
    sbom_sha256: str,
    waiver_manifest: dict[str, Any] | None = None,
    evaluated_at: datetime | None = None,
) -> dict[str, Any]:
    production = _audit_counts(production_audit)
    complete = _audit_counts(complete_audit)
    production_findings = _security_findings(production_audit)
    complete_findings = _security_findings(complete_audit)
    waiver_result = evaluate_security_waivers(
        waiver_manifest=waiver_manifest,
        release_sha=release_sha,
        production_findings=production_findings,
        complete_findings=complete_findings,
        evaluated_at=evaluated_at,
    )
    problems = [str(item) for item in tree.get("problems", []) if item]
    components = sbom.get("components")
    sbom_valid = (
        sbom.get("bomFormat") == "CycloneDX"
        and sbom.get("specVersion") == "1.5"
        and isinstance(components, list)
        and len(components) > 0
        and re.fullmatch(r"[0-9a-f]{64}", sbom_sha256) is not None
    )
    node_match = NODE_VERSION.match(node_version)
    node_20 = node_match is not None and int(node_match.group("major")) == 20
    release_bound = (
        profile == "local"
        or (
            isinstance(release_sha, str)
            and RELEASE_SHA.fullmatch(release_sha) is not None
        )
    )
    checks = {
        "production_no_unwaived_high_critical": not waiver_result[
            "production_unwaived"
        ],
        "complete_no_unwaived_high_critical": not waiver_result[
            "complete_unwaived"
        ],
        "audit_findings_consistent": (
            len(production_findings) == production["high"] + production["critical"]
            and len(complete_findings) == complete["high"] + complete["critical"]
        ),
        "audit_payloads_valid": (
            _audit_payload_valid(production_audit)
            and _audit_payload_valid(complete_audit)
        ),
        "audit_commands_valid": (
            _audit_command_valid(production_audit_exit_code, production_audit)
            and _audit_command_valid(complete_audit_exit_code, complete_audit)
        ),
        "waiver_manifest_valid": waiver_result["valid"],
        "dependency_tree_valid": tree_exit_code == 0 and not problems,
        "cyclonedx_sbom_generated": sbom_valid,
        "node_20": node_20,
        "release_sha_bound": release_bound,
    }
    blockers = [name for name, passed in checks.items() if not passed]
    vulnerable_packages = sorted(
        str(name) for name in production_audit.get("vulnerabilities", {})
    )
    return {
        "schema_version": 2,
        "policy_id": "PR18-DEPENDENCY-SECURITY-V2",
        "generated_at": datetime.now(UTC).isoformat(),
        "profile": profile,
        "evidence_class": (
            "engineering_evidence_only"
            if profile == "local"
            else "release_evidence_fragment"
        ),
        "release_sha": release_sha,
        "runtime": {
            "node": node_version,
            "npm": npm_version,
        },
        "production_audit": production,
        "complete_audit": complete,
        "audit_commands": {
            "production_exit_code": production_audit_exit_code,
            "complete_exit_code": complete_audit_exit_code,
        },
        "production_findings": production_findings,
        "complete_findings": complete_findings,
        "security_waivers": waiver_result,
        "vulnerable_production_packages": vulnerable_packages,
        "dependency_tree": {
            "exit_code": tree_exit_code,
            "problems": problems,
        },
        "sbom": {
            "format": sbom.get("bomFormat"),
            "spec_version": sbom.get("specVersion"),
            "components": len(components) if isinstance(components, list) else 0,
            "sha256": sbom_sha256,
            "attested": False,
        },
        "checks": checks,
        "passed": not blockers,
        "blockers": blockers,
    }


def _run_json(
    executable: str,
    args: list[str],
    *,
    cwd: Path,
    allowed_exit_codes: set[int],
) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [executable, *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    if completed.returncode not in allowed_exit_codes:
        error = completed.stderr.strip() or "command failed"
        raise DependencySecurityError(f"{' '.join(args)}: {error}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DependencySecurityError(
            f"{' '.join(args)} returned invalid JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise DependencySecurityError(f"{' '.join(args)} must return an object.")
    return completed.returncode, payload


def generate_evidence(
    *,
    repo_root: Path,
    profile: str,
    release_sha: str | None,
    waiver_manifest: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    node = shutil.which("node.exe") or shutil.which("node")
    if not npm or not node:
        raise DependencySecurityError("node and npm are required.")

    production_audit_exit, production_audit = _run_json(
        npm,
        ["audit", "--omit=dev", "--json"],
        cwd=repo_root,
        allowed_exit_codes={0, 1},
    )
    complete_audit_exit, complete_audit = _run_json(
        npm,
        ["audit", "--json"],
        cwd=repo_root,
        allowed_exit_codes={0, 1},
    )
    tree_exit, tree = _run_json(
        npm,
        ["ls", "--all", "--json"],
        cwd=repo_root,
        allowed_exit_codes={0, 1},
    )
    _, sbom = _run_json(
        npm,
        ["sbom", "--sbom-format", "cyclonedx"],
        cwd=repo_root,
        allowed_exit_codes={0},
    )
    node_version = subprocess.run(
        [node, "--version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    npm_version = subprocess.run(
        [npm, "--version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    sbom_bytes = (json.dumps(sbom, indent=2, sort_keys=True) + "\n").encode("utf-8")
    report = evaluate_dependency_security(
        production_audit=production_audit,
        complete_audit=complete_audit,
        production_audit_exit_code=production_audit_exit,
        complete_audit_exit_code=complete_audit_exit,
        tree_exit_code=tree_exit,
        tree=tree,
        sbom=sbom,
        node_version=node_version,
        npm_version=npm_version,
        profile=profile,
        release_sha=release_sha,
        sbom_sha256=hashlib.sha256(sbom_bytes).hexdigest(),
        waiver_manifest=waiver_manifest,
    )
    return report, sbom


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--profile", choices=("local", "release_candidate"), required=True)
    parser.add_argument("--release-sha")
    parser.add_argument("--waiver-manifest", type=Path)
    parser.add_argument("--report-output", type=Path, required=True)
    parser.add_argument("--sbom-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        waiver_manifest = None
        if args.waiver_manifest is not None:
            waiver_path = args.waiver_manifest.resolve()
            repo_root = args.repo_root.resolve()
            if not waiver_path.is_relative_to(repo_root):
                raise DependencySecurityError(
                    "waiver manifest must be inside the repository."
                )
            waiver_manifest = json.loads(waiver_path.read_text(encoding="utf-8"))
            if not isinstance(waiver_manifest, dict):
                raise DependencySecurityError("waiver manifest must be an object.")
        report, sbom = generate_evidence(
            repo_root=args.repo_root.resolve(),
            profile=args.profile,
            release_sha=args.release_sha,
            waiver_manifest=waiver_manifest,
        )
    except (
        DependencySecurityError,
        json.JSONDecodeError,
        OSError,
        subprocess.SubprocessError,
    ) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 2
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.sbom_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.sbom_output.write_bytes(
        (json.dumps(sbom, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
