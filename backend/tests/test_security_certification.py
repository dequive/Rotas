import hashlib
import json
from pathlib import Path

from scripts.security_certification import (
    REQUIRED_EVIDENCE,
    REQUIRED_PRIVACY_CONTROLS,
    REQUIRED_ROLES,
    REQUIRED_SURFACES,
    evaluate_security_certification,
)
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


def _context(tmp_path: Path) -> dict:
    images = {
        image_key: (
            f"registry.example/rotas/{image_key.lower()}@sha256:{index:064x}"
        )
        for index, image_key in enumerate(sorted(CUSTOM_IMAGE_KEYS), 1)
    }
    return {
        "schema_version": 1,
        "policy_id": "PR23-SECURITY-CERTIFICATION-V1",
        "environment": "staging",
        "release_sha": RELEASE_SHA,
        "observed_at": "2026-07-31T10:00:00Z",
        "external_runner": True,
        "images": images,
        "pentest_independent": {
            "release_sha": RELEASE_SHA,
            "authorized": True,
            "authorization_reference": "ROE-2026-001",
            "completed": True,
            "independent_assessor": True,
            "no_conflict_of_interest": True,
            "assessor_organization": "Independent Security Lda",
            "assessor_report_id": "PT-2026-001",
            "encrypted_findings_channel": "approved-encrypted-portal",
            "started_at": "2026-07-20T08:00:00Z",
            "completed_at": "2026-07-25T17:00:00Z",
            "roles_tested": sorted(REQUIRED_ROLES),
            "surfaces_tested": sorted(REQUIRED_SURFACES),
            "two_tenants_overlapping_identifiers": True,
            "restricted_database_role_tested": True,
            "test_accounts_revoked": True,
            "allowlists_removed": True,
            "audit_logs_reconciled": True,
            "stop_rule_incidents": 0,
        },
        "zero_high_critical": {
            "open_counts": {
                "critical": 0,
                "high": 0,
                "medium": 1,
                "low": 1,
            },
            "remediated_findings": 2,
            "independently_retested_findings": 2,
            "failed_retests": 0,
            "threat_model_items_tested": 16,
            "unresolved_release_blockers": 0,
            "open_medium_low": [
                {
                    "id": "F-003",
                    "severity": "medium",
                    "owner": "BE",
                    "due_at": "2026-09-01T00:00:00Z",
                },
                {
                    "id": "F-004",
                    "severity": "low",
                    "owner": "FE-M",
                    "due_at": "2026-10-01T00:00:00Z",
                },
            ],
        },
        "privacy_approved": {
            "approved": True,
            "legal_review_independent": True,
            "jurisdiction": "MZ",
            "legal_opinion_reference": "LEGAL-PRIV-2026-001",
            "approver_name": "Approved Counsel",
            "approver_role": "External Legal Counsel",
            "policy_version": "privacy-2026.1",
            "signed_at": "2026-07-28T10:00:00Z",
            "valid_until": "2027-07-28T10:00:00Z",
            "tenant_contract_roles_defined": True,
            "privacy_lifecycle_tests_passed": True,
            "subprocessors_assessed": True,
            "cross_tenant_bi_governed": True,
            "controls_approved": sorted(REQUIRED_PRIVACY_CONTROLS),
            "open_high_privacy_risks": 0,
            "privacy_flows_tested": 8,
        },
        "evidence": {
            group: [_write_artifact(tmp_path, kind) for kind in sorted(kinds)]
            for group, kinds in REQUIRED_EVIDENCE.items()
        },
    }


def test_security_certification_passes_complete_bundle(tmp_path):
    result = evaluate_security_certification(_context(tmp_path), base_dir=tmp_path)

    assert result["decision"] == "PASS"
    assert result["controls"] == {
        "pentest_independent": True,
        "zero_high_critical": True,
        "privacy_approved": True,
    }
    assert result["evidence_files"] == 9
    assert result["blockers"] == []


def test_security_certification_rejects_each_control(tmp_path):
    context = _context(tmp_path)
    context["pentest_independent"]["independent_assessor"] = False
    context["zero_high_critical"]["open_counts"]["high"] = 1
    context["privacy_approved"]["open_high_privacy_risks"] = 1

    result = evaluate_security_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert result["controls"] == {
        "pentest_independent": False,
        "zero_high_critical": False,
        "privacy_approved": False,
    }


def test_security_certification_rejects_evidence_drift(tmp_path):
    context = _context(tmp_path)
    context["evidence"]["pentest_independent"][0]["sha256"] = "0" * 64
    context["evidence"]["zero_high_critical"].append(
        context["evidence"]["zero_high_critical"][0].copy()
    )
    report_path = tmp_path / context["evidence"]["privacy_approved"][0]["path"]
    physical = json.loads(report_path.read_text(encoding="utf-8"))
    physical["release_sha"] = "f" * 40
    report_path.write_text(json.dumps(physical, sort_keys=True), encoding="utf-8")
    context["evidence"]["privacy_approved"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()

    result = evaluate_security_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "evidence.pentest_independent[0] hash mismatch" in blockers
    assert "evidence.zero_high_critical duplicate kind" in blockers
    assert "physical release SHA mismatch" in blockers


def test_security_certification_rejects_scope_retest_and_expired_owner_item(tmp_path):
    context = _context(tmp_path)
    context["pentest_independent"]["roles_tested"] = ["unauthenticated"]
    context["zero_high_critical"]["independently_retested_findings"] = 1
    context["zero_high_critical"]["open_medium_low"][0]["due_at"] = (
        "2026-07-01T00:00:00Z"
    )
    context["privacy_approved"]["valid_until"] = "2026-07-30T00:00:00Z"

    result = evaluate_security_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "roles_tested set mismatch" in blockers
    assert "remediation/retest counts mismatch" in blockers
    assert "due_at is invalid" in blockers
    assert "privacy_approved validity window is invalid" in blockers


def test_security_certification_global_image_drift_makes_all_controls_false(tmp_path):
    context = _context(tmp_path)
    context["images"]["ROTAS_BACKEND_IMAGE"] = "registry.example/rotas/backend:latest"

    result = evaluate_security_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert all(value is False for value in result["controls"].values())
