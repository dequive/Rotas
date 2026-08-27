import hashlib
import json
from pathlib import Path

from scripts.incident_certification import (
    REQUIRED_EVIDENCE,
    REQUIRED_SIGNOFF_ROLES,
    REQUIRED_UPSTREAMS,
    evaluate_incident_certification,
)
from scripts.validate_incident_response import (
    REQUIRED_ROLES,
    REQUIRED_SCENARIOS,
    REQUIRED_SEVERITIES,
)
from scripts.validate_observability import REQUIRED_ALERTS
from scripts.validate_staging_manifest import CUSTOM_IMAGE_KEYS

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write_artifact(tmp_path: Path, kind: str) -> dict:
    path = tmp_path / f"{kind}.json"
    path.write_text(
        json.dumps({"kind": kind, "release_sha": RELEASE_SHA}, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "kind": kind,
        "path": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "release_sha": RELEASE_SHA,
    }


def _scenario(scenario_id: str) -> dict:
    return {
        "id": scenario_id,
        "started_at": "2026-07-31T08:00:00Z",
        "recovered_at": "2026-07-31T08:30:00Z",
        "failure_injected": True,
        "recovered": True,
        "independently_validated": True,
        "containment_minutes": 5,
        "recovery_minutes": 30,
        "result": "passed",
    }


def _context(tmp_path: Path) -> dict:
    return {
        "schema_version": 1,
        "policy_id": "PR25-INCIDENT-CERTIFICATION-V1",
        "environment": "staging",
        "release_sha": RELEASE_SHA,
        "observed_at": "2026-07-31T12:00:00Z",
        "external_runner": True,
        "images": {
            image_key: (
                f"registry.example/rotas/{image_key.lower()}@sha256:{index:064x}"
            )
            for index, image_key in enumerate(sorted(CUSTOM_IMAGE_KEYS), 1)
        },
        "upstreams": {
            pr_id: {
                "policy_id": policy_id,
                "release_sha": RELEASE_SHA,
                "decision": "PASS",
                "passed": True,
                "artifact_sha256": f"{index:064x}",
            }
            for index, (pr_id, policy_id) in enumerate(
                sorted(REQUIRED_UPSTREAMS.items()),
                1,
            )
        },
        "paging": {
            "external_roster": True,
            "primary_secondary_present": True,
            "real_provider": True,
            "delivery_observed": True,
            "acknowledgement_observed": True,
            "credentials_revoked_after_drill": True,
            "provider": "PagerDuty",
            "alerts_exercised": sorted(REQUIRED_ALERTS),
            "deliveries": [
                {
                    "delivery_id": f"delivery-{index}",
                    "delivered_at": "2026-07-31T08:00:00Z",
                    "acknowledged_at": "2026-07-31T08:02:00Z",
                    "acknowledged_by_role": "operations_lead",
                }
                for index, _ in enumerate(sorted(REQUIRED_ALERTS), 1)
            ],
            "undelivered_pages": 0,
        },
        "escalation": {
            "severities_exercised": sorted(REQUIRED_SEVERITIES),
            "human_acknowledgement": True,
            "secondary_escalation_observed": True,
            "incident_commander_assigned": True,
            "tenant_scoped_updates": True,
            "public_updates_exclude_tenant_identifiers": True,
            "cadence_met": True,
            "ack_sla_breaches": 0,
            "escalation_sla_breaches": 0,
            "communication_sla_breaches": 0,
        },
        "game_day": {
            "production_like_staging": True,
            "release_candidate_used": True,
            "independent_facilitator": True,
            "failure_injection_real": True,
            "independent_recovery_validation": True,
            "audit_timeline_reconciled": True,
            "scenarios": [
                _scenario(scenario_id) for scenario_id in sorted(REQUIRED_SCENARIOS)
            ],
            "sev1_sev2_after_drill": 0,
            "unreconciled_data_loss": 0,
            "measured_rpo_minutes": 10,
            "measured_rto_minutes": 30,
        },
        "signoff": {
            "participants": sorted(REQUIRED_ROLES),
            "approved_roles": sorted(REQUIRED_SIGNOFF_ROLES),
            "attendance_verified": True,
            "postmortem_complete": True,
            "all_actions_closed": True,
            "actions_independently_verified": True,
            "test_access_removed": True,
            "temporary_changes_reverted": True,
            "attendees": 8,
            "open_actions": 0,
            "open_release_blockers": 0,
        },
        "evidence": {
            group: [_write_artifact(tmp_path, kind) for kind in sorted(kinds)]
            for group, kinds in REQUIRED_EVIDENCE.items()
        },
    }


def test_incident_certification_passes_complete_bundle(tmp_path):
    result = evaluate_incident_certification(_context(tmp_path), base_dir=tmp_path)

    assert result["decision"] == "PASS"
    assert result["controls"] == {
        "paging": True,
        "escalation": True,
        "game_day": True,
        "signoff": True,
    }
    assert result["evidence_files"] == 10
    assert result["blockers"] == []


def test_incident_certification_rejects_each_control(tmp_path):
    context = _context(tmp_path)
    context["paging"]["undelivered_pages"] = 1
    context["escalation"]["ack_sla_breaches"] = 1
    context["game_day"]["scenarios"][0]["recovered"] = False
    context["signoff"]["open_actions"] = 1

    result = evaluate_incident_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert all(value is False for value in result["controls"].values())


def test_incident_certification_rejects_upstream_or_image_drift_globally(tmp_path):
    context = _context(tmp_path)
    context["upstreams"]["PR-21"]["decision"] = "NO-GO"
    context["images"]["ROTAS_DRIVER_IMAGE"] = "registry.example/rotas/driver:latest"

    result = evaluate_incident_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert "upstreams.PR-21 must be PASS" in blockers
    assert "immutable RepoDigest" in blockers
    assert all(value is False for value in result["controls"].values())


def test_incident_certification_rejects_evidence_drift(tmp_path):
    context = _context(tmp_path)
    context["evidence"]["paging"][0]["sha256"] = "0" * 64
    context["evidence"]["escalation"].append(
        context["evidence"]["escalation"][0].copy()
    )
    report_path = tmp_path / context["evidence"]["game_day"][0]["path"]
    physical = json.loads(report_path.read_text(encoding="utf-8"))
    physical["release_sha"] = "f" * 40
    report_path.write_text(json.dumps(physical, sort_keys=True), encoding="utf-8")
    context["evidence"]["game_day"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()

    result = evaluate_incident_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert "evidence.paging[0] hash mismatch" in blockers
    assert "evidence.escalation duplicate kind" in blockers
    assert "physical release SHA mismatch" in blockers


def test_incident_certification_rejects_tabletop_substitutes(tmp_path):
    context = _context(tmp_path)
    context["paging"]["provider"] = "local"
    context["game_day"]["failure_injection_real"] = False
    context["game_day"]["measured_rpo_minutes"] = 16
    context["signoff"]["participants"] = ["incident_commander"]

    result = evaluate_incident_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert "real external provider" in blockers
    assert "failure_injection_real must be true" in blockers
    assert "measured_rpo_minutes must be at most 15" in blockers
    assert "signoff.participants set mismatch" in blockers
