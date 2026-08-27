import hashlib
import json
from pathlib import Path

from scripts.accessibility_certification import (
    REQUIRED_ASSISTIVE_TECH,
    REQUIRED_EVIDENCE,
    REQUIRED_JOURNEYS,
    REQUIRED_MANUAL_CHECKS,
    REQUIRED_MOBILE_PLATFORMS,
    REQUIRED_ROLES,
    evaluate_accessibility_certification,
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
    return {
        "schema_version": 1,
        "policy_id": "PR24-ACCESSIBILITY-CERTIFICATION-V1",
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
        "wcag_2_2_aa": {
            "standard": "WCAG 2.2",
            "level": "AA",
            "manager_build_passed": True,
            "driver_build_passed": True,
            "route_inventory_complete": True,
            "all_a_aa_criteria_evaluated": True,
            "total_routes": 72,
            "tested_routes": 72,
            "failed_a_aa_criteria": 0,
            "critical_axe_violations": 0,
            "serious_axe_violations": 0,
            "skipped_tests": 0,
            "unresolved_exceptions": 0,
        },
        "manual_assistive": {
            "independent_assessor": True,
            "no_conflict_of_interest": True,
            "audit_completed": True,
            "findings_retested": True,
            "assessor_organization": "Independent Accessibility Lda",
            "report_id": "A11Y-2026-001",
            "assistive_technologies": sorted(REQUIRED_ASSISTIVE_TECH),
            "checks": sorted(REQUIRED_MANUAL_CHECKS),
            "open_a_aa_findings": 0,
            "failed_retests": 0,
            "blocked_tasks": 0,
        },
        "mobile_real": {
            "physical_devices": True,
            "platforms": sorted(REQUIRED_MOBILE_PLATFORMS),
            "portrait_tested": True,
            "landscape_tested": True,
            "touch_targets_passed": True,
            "one_handed_driver_journey_passed": True,
            "screen_reader_gestures_passed": True,
            "devices": [
                {
                    "manufacturer": "Apple",
                    "model": "iPhone",
                    "os_version": "iOS 19",
                    "physical": True,
                },
                {
                    "manufacturer": "Samsung",
                    "model": "Galaxy",
                    "os_version": "Android 16",
                    "physical": True,
                },
            ],
            "failed_scenarios": 0,
            "blocked_scenarios": 0,
        },
        "role_coverage": {
            "roles": sorted(REQUIRED_ROLES),
            "journeys": sorted(REQUIRED_JOURNEYS),
            "two_tenants_overlapping_identifiers": True,
            "all_states_covered": True,
            "tenant_isolation_verified": True,
            "po_approved": True,
            "user_acceptance_approved": True,
            "participants": 7,
            "failed_journeys": 0,
            "skipped_journeys": 0,
            "cross_tenant_leaks": 0,
        },
        "evidence": {
            group: [_write_artifact(tmp_path, kind) for kind in sorted(kinds)]
            for group, kinds in REQUIRED_EVIDENCE.items()
        },
    }


def test_accessibility_certification_passes_complete_bundle(tmp_path):
    result = evaluate_accessibility_certification(
        _context(tmp_path),
        base_dir=tmp_path,
    )

    assert result["decision"] == "PASS"
    assert result["controls"] == {
        "wcag_2_2_aa": True,
        "manual_assistive": True,
        "mobile_real": True,
        "role_coverage": True,
    }
    assert result["evidence_files"] == 11
    assert result["blockers"] == []


def test_accessibility_certification_rejects_each_control(tmp_path):
    context = _context(tmp_path)
    context["wcag_2_2_aa"]["serious_axe_violations"] = 1
    context["manual_assistive"]["open_a_aa_findings"] = 1
    context["mobile_real"]["physical_devices"] = False
    context["role_coverage"]["skipped_journeys"] = 1

    result = evaluate_accessibility_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert all(value is False for value in result["controls"].values())


def test_accessibility_certification_rejects_evidence_drift(tmp_path):
    context = _context(tmp_path)
    context["evidence"]["wcag_2_2_aa"][0]["sha256"] = "0" * 64
    context["evidence"]["manual_assistive"].append(
        context["evidence"]["manual_assistive"][0].copy()
    )
    report_path = tmp_path / context["evidence"]["mobile_real"][0]["path"]
    physical = json.loads(report_path.read_text(encoding="utf-8"))
    physical["release_sha"] = "f" * 40
    report_path.write_text(json.dumps(physical, sort_keys=True), encoding="utf-8")
    context["evidence"]["mobile_real"][0]["sha256"] = hashlib.sha256(
        report_path.read_bytes()
    ).hexdigest()

    result = evaluate_accessibility_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "evidence.wcag_2_2_aa[0] hash mismatch" in blockers
    assert "evidence.manual_assistive duplicate kind" in blockers
    assert "physical release SHA mismatch" in blockers


def test_accessibility_certification_rejects_incomplete_scope(tmp_path):
    context = _context(tmp_path)
    context["wcag_2_2_aa"]["tested_routes"] = 71
    context["manual_assistive"]["assistive_technologies"] = ["NVDA_Firefox"]
    context["mobile_real"]["devices"][0]["physical"] = False
    context["role_coverage"]["roles"] = ["tenant_admin"]

    result = evaluate_accessibility_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "route coverage must be complete" in blockers
    assert "assistive_technologies set mismatch" in blockers
    assert "invalid or emulated entries" in blockers
    assert "role_coverage.roles set mismatch" in blockers


def test_accessibility_certification_image_drift_fails_all_controls(tmp_path):
    context = _context(tmp_path)
    context["images"]["ROTAS_MANAGER_IMAGE"] = "registry.example/rotas/manager:latest"

    result = evaluate_accessibility_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert all(value is False for value in result["controls"].values())
