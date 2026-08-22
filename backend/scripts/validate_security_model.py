"""Fail-closed validation for the PR-23 threat and privacy baseline."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


class SecurityModelError(ValueError):
    pass


REQUIRED_BOUNDARIES = {
    "public_edge",
    "manager_browser_bff",
    "driver_device_offline_store",
    "tenant_api",
    "platform_control_plane",
    "postgres_rls",
    "redis_jobs_cache",
    "object_storage",
    "outbox_governance",
    "third_party_delivery",
    "observability",
    "backup_restore",
}
REQUIRED_ASSETS = {
    "tenant_identity",
    "tenant_customer_records",
    "authentication_secrets",
    "financial_ledgers",
    "stock_and_workshop_state",
    "vehicle_and_location_data",
    "hr_payroll_data",
    "documents_and_photos",
    "audit_and_outbox_evidence",
    "availability_and_recovery_data",
}
REQUIRED_THREATS = {f"TM-{number:02d}" for number in range(1, 17)}
REQUIRED_PRIVACY_FLOWS = {f"PF-{number:02d}" for number in range(1, 9)}
RISK_BANDS = {
    "low": range(1, 5),
    "medium": range(5, 10),
    "high": range(10, 17),
    "critical": range(17, 26),
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{16,}\b", re.IGNORECASE),
)


def _required_set(value: Any, expected: set[str], label: str, failures: list[str]) -> None:
    actual = set(value) if isinstance(value, list) else set()
    missing = expected - actual
    if missing:
        failures.append(f"{label} missing: {sorted(missing)}")


def _risk_label(score: int) -> str | None:
    return next((label for label, band in RISK_BANDS.items() if score in band), None)


def validate_security_model(repo_root: Path, model_path: Path | None = None) -> dict[str, int]:
    path = model_path or repo_root / "infra" / "security" / "ROTAS_SECURITY_MODEL.json"
    raw = path.read_text(encoding="utf-8")
    model = json.loads(raw)
    failures: list[str] = []

    if model.get("schema_version") != 1 or model.get("model_id") != "PR23-THREAT-MODEL-V1":
        failures.append("The canonical PR23 model id/schema is required.")
    tenant_model = model.get("multi_tenant_model", {})
    expected_tenant_model = {
        "operator": "ROTAS SaaS",
        "tenant": "independent operating company",
        "tenant_customer": "customer owned and managed by the tenant",
    }
    if any(tenant_model.get(key) != value for key, value in expected_tenant_model.items()):
        failures.append("The SaaS operator -> tenant -> tenant customer hierarchy changed.")

    _required_set(model.get("trust_boundaries"), REQUIRED_BOUNDARIES, "trust boundaries", failures)
    _required_set(model.get("assets"), REQUIRED_ASSETS, "assets", failures)

    privacy = model.get("privacy", {})
    class_ids = {item.get("id") for item in privacy.get("data_classes", [])}
    if class_ids != {"public", "internal", "confidential", "restricted"}:
        failures.append("Privacy classification must contain the four canonical classes.")
    flow_ids = [item.get("id") for item in privacy.get("data_flows", [])]
    _required_set(flow_ids, REQUIRED_PRIVACY_FLOWS, "privacy flows", failures)
    if len(flow_ids) != len(set(flow_ids)):
        failures.append("Privacy flow ids must be unique.")
    if len(privacy.get("required_open_work", [])) < 7:
        failures.append("Privacy lifecycle open work must remain explicit.")

    release = model.get("release_policy", {})
    for control in (
        "zero_open_high_or_critical",
        "independent_pentest_required",
        "two_tenants_with_overlapping_identifiers_required",
        "restricted_database_role_required",
        "legal_review_required",
        "retest_after_remediation_required",
    ):
        if release.get(control) is not True:
            failures.append(f"Release control must be true: {control}")
    if release.get("risk_acceptance", {}).get("allowed_for_high_or_critical") is not False:
        failures.append("High/critical risk acceptance must be forbidden for G4.")

    threats = model.get("threats", [])
    threat_ids = [item.get("id") for item in threats]
    _required_set(threat_ids, REQUIRED_THREATS, "threats", failures)
    if len(threat_ids) != len(set(threat_ids)):
        failures.append("Threat ids must be unique.")
    for threat in threats:
        threat_id = threat.get("id", "<missing>")
        likelihood = threat.get("likelihood")
        impact = threat.get("impact")
        if not isinstance(likelihood, int) or not 1 <= likelihood <= 5:
            failures.append(f"{threat_id}: likelihood must be 1..5.")
            continue
        if not isinstance(impact, int) or not 1 <= impact <= 5:
            failures.append(f"{threat_id}: impact must be 1..5.")
            continue
        expected_score = likelihood * impact
        if threat.get("risk_score") != expected_score:
            failures.append(f"{threat_id}: risk_score must equal likelihood * impact.")
        if threat.get("risk") != _risk_label(expected_score):
            failures.append(f"{threat_id}: risk label does not match score.")
        if threat.get("boundary") not in REQUIRED_BOUNDARIES:
            failures.append(f"{threat_id}: unknown trust boundary.")
        for field in (
            "title",
            "scenario",
            "owner",
            "residual_risk",
            "control_status",
            "status",
        ):
            if not threat.get(field):
                failures.append(f"{threat_id}: missing {field}.")
        for field in ("stride", "assets", "existing_controls", "control_evidence", "required_verification"):
            if not isinstance(threat.get(field), list) or not threat[field]:
                failures.append(f"{threat_id}: {field} must be non-empty.")
        if any(asset not in REQUIRED_ASSETS for asset in threat.get("assets", [])):
            failures.append(f"{threat_id}: references an unknown asset.")
        if threat.get("release_blocking") is not True:
            failures.append(f"{threat_id}: every baseline threat must remain release-blocking until pentest.")
        if threat.get("status") == "closed":
            failures.append(f"{threat_id}: canonical baseline cannot pre-close a threat before RC pentest.")

    pentest = model.get("pentest", {})
    if pentest.get("status") != "not_executed":
        failures.append("The baseline must not claim that the independent pentest ran.")
    for field in ("prerequisites", "minimum_roles", "minimum_scope", "acceptance"):
        if not isinstance(pentest.get(field), list) or len(pentest[field]) < 4:
            failures.append(f"Pentest field is incomplete: {field}")

    if any(pattern.search(raw) for pattern in SECRET_PATTERNS):
        failures.append("The security model contains a token or private-key pattern.")

    required_files = [
        "backend/app/database.py",
        "backend/app/core/auth.py",
        "backend/tests/test_rls.py",
        "apps/manager/app/lib/upstream-http.ts",
        "apps/driver/src/identity.ts",
        "docs/evidence/PR18_DEPENDENCY_SECURITY_REASSESSMENT_20260726.md",
    ]
    for relative in required_files:
        if not (repo_root / relative).is_file():
            failures.append(f"Referenced control file is missing: {relative}")

    if failures:
        raise SecurityModelError("; ".join(failures))
    return {
        "threats": len(threats),
        "open_release_blockers": sum(
            1 for threat in threats if threat["release_blocking"] and threat["status"] != "closed"
        ),
        "privacy_classes": len(class_ids),
        "privacy_flows": len(flow_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--model", type=Path)
    args = parser.parse_args()
    try:
        result = validate_security_model(args.repo_root.resolve(), args.model)
    except (OSError, json.JSONDecodeError, SecurityModelError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
