"""Fail-closed validation for the PR-25 incident-response contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


class IncidentResponsePolicyError(ValueError):
    pass


REQUIRED_SEVERITIES = {"SEV1", "SEV2", "SEV3", "SEV4"}
REQUIRED_ROLES = {
    "incident_commander",
    "operations_lead",
    "communications_lead",
    "scribe",
    "security_privacy_lead",
    "business_owner",
}
REQUIRED_LIFECYCLE = [
    "declared",
    "triaged",
    "contained",
    "recovered",
    "monitoring",
    "resolved",
    "review_closed",
]
REQUIRED_SCENARIOS = {
    "backend_unavailable",
    "api_error_or_latency",
    "outbox_dead_letter",
    "database_loss_and_restore",
    "tenant_isolation_or_privacy",
}
PROMETHEUS_SIGNALS = {
    "RotasBackendDown",
    "RotasApiHighErrorRate",
    "RotasOutboxDeadLetter",
}


def load_incident_policy(repo_root: Path) -> dict[str, Any]:
    return json.loads(
        (
            repo_root / "infra" / "operations" / "INCIDENT_RESPONSE_POLICY.json"
        ).read_text(encoding="utf-8")
    )


def validate_incident_response_policy(repo_root: Path) -> dict[str, int]:
    policy = load_incident_policy(repo_root)
    failures: list[str] = []

    if policy.get("policy_id") != "PR25-IR-V1":
        failures.append("Canonical incident-response policy ID is missing.")
    if set(policy.get("owners", [])) != {"SRE", "PO"}:
        failures.append("PR-25 must be jointly owned by SRE and PO.")

    roster = policy.get("roster", {})
    if roster.get("source") != "external_on_call_directory":
        failures.append("On-call roster must use an external source of truth.")
    if roster.get("people_or_contacts_in_repository") is not False:
        failures.append("Personal contacts must not be stored in the repository.")
    if not roster.get("primary_and_secondary_required"):
        failures.append("Primary and secondary on-call responders are required.")

    severities = policy.get("severities", {})
    if set(severities) != REQUIRED_SEVERITIES:
        failures.append("Exactly SEV1-SEV4 severities are required.")
    for severity, contract in severities.items():
        for field in (
            "definition",
            "acknowledge_minutes",
            "incident_commander_minutes",
            "stakeholder_update_minutes",
        ):
            if not contract.get(field):
                failures.append(f"{severity} is missing {field}.")

    if set(policy.get("required_roles", [])) != REQUIRED_ROLES:
        failures.append("Incident roles differ from the required separation of duties.")
    if policy.get("lifecycle") != REQUIRED_LIFECYCLE:
        failures.append("Incident lifecycle is incomplete or out of order.")

    communication = policy.get("communication", {})
    for field in (
        "internal_incident_channel_required",
        "customer_status_channel_required",
        "tenant_scoped_customer_updates",
        "public_messages_must_exclude_tenant_identifiers",
        "update_cadence_from_severity",
    ):
        if communication.get(field) is not True:
            failures.append(f"Communication control is disabled: {field}")
    if communication.get("paging_endpoint_source") != "external_secret":
        failures.append("Paging endpoint must come from an external secret.")

    closure = policy.get("closure", {})
    for field in (
        "independent_recovery_validation_required",
        "security_privacy_review_for_sev1_sev2",
        "open_actions_block_review_closure",
    ):
        if closure.get(field) is not True:
            failures.append(f"Closure control is disabled: {field}")

    scenarios = policy.get("scenarios", [])
    scenario_ids = {scenario.get("id") for scenario in scenarios}
    if scenario_ids != REQUIRED_SCENARIOS:
        failures.append("Canonical game-day scenarios are incomplete.")
    game_day = policy.get("game_day", {})
    if game_day.get("minimum_scenarios") != len(REQUIRED_SCENARIOS):
        failures.append("Game-day minimum must cover every canonical scenario.")
    for field in (
        "independent_facilitator_required",
        "real_paging_delivery_required_for_gate",
        "release_candidate_required_for_gate",
        "production_like_staging_required_for_gate",
    ):
        if game_day.get(field) is not True:
            failures.append(f"Game-day gate is weakened: {field}")

    prometheus_rules = (
        repo_root / "infra" / "observability" / "rules" / "rotas-slo.rules.yml"
    ).read_text(encoding="utf-8")
    for scenario in scenarios:
        if not scenario.get("runbook") or not scenario.get("expected_controls"):
            failures.append(f"Scenario {scenario.get('id')!r} has no executable route.")
        signal = scenario.get("signal")
        if signal in PROMETHEUS_SIGNALS and f"alert: {signal}" not in prometheus_rules:
            failures.append(f"Scenario signal has no Prometheus alert: {signal}")

    runbook = (
        repo_root / "docs" / "operations" / "PR25_INCIDENT_RESPONSE_RUNBOOK.md"
    ).read_text(encoding="utf-8")
    for required in (
        "local_control_plane_only",
        "PR25-LOCAL-TABLETOP",
        "Comunicação multi-tenant",
        "executor da recuperação não pode ser o único validador",
    ):
        if required not in runbook:
            failures.append(f"Incident runbook control is missing: {required}")

    if failures:
        raise IncidentResponsePolicyError("; ".join(failures))
    return {
        "severities": len(severities),
        "roles": len(REQUIRED_ROLES),
        "lifecycle_states": len(REQUIRED_LIFECYCLE),
        "scenarios": len(scenarios),
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
        result = validate_incident_response_policy(args.repo_root.resolve())
    except (
        OSError,
        json.JSONDecodeError,
        IncidentResponsePolicyError,
    ) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
