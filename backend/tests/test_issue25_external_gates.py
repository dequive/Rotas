import json
from copy import deepcopy
from pathlib import Path

from scripts.validate_issue25_external_gates import evaluate

SHA = "80fa0ca4c2794b7e7a552930728af141005e63f1"
ROOT = Path(__file__).resolve().parents[2]


def _green_evidence() -> dict:
    return {
        "schema_version": 1,
        "gate": "ISSUE-25-EXTERNAL-CERTIFICATION",
        "commit_sha": SHA,
        "ci": {
            "run_id": 123456,
            "head_sha": SHA,
            "conclusion": "success",
            "jobs": [
                {"name": name, "conclusion": "success", "runner_id": index, "steps_executed": 5}
                for index, name in enumerate(("Backend", "Frontend", "E2E"), start=1)
            ],
        },
        "sentry": {
            "environment": "staging",
            "send_default_pii": False,
            "manager_spans_observed": True,
            "driver_spans_observed": True,
            "dashboard_url": "https://sentry.example.invalid/dashboard/issue-25",
            "alerts": [
                {
                    "name": name,
                    "test_fired": True,
                    "delivered": True,
                    "runbook_url": f"https://runbooks.example.invalid/{name}",
                }
                for name in (
                    "manager-cls",
                    "manager-lcp",
                    "manager-inp",
                    "driver-bootstrap",
                    "driver-sync",
                    "driver-bootstrap-unavailable",
                    "driver-sync-error",
                )
            ],
        },
        "android": {
            "physical_device": True,
            "emulator": False,
            "performance_class": "low_end",
            "ram_mb": 3072,
            "network_profile": "unstable",
            "reduced_motion_passed": True,
            "offline_sync_passed": True,
            "driver_tests_passed": True,
            "artifact_url": "https://evidence.example.invalid/android/issue-25",
        },
    }


def test_accepts_complete_external_evidence_for_the_exact_sha():
    result = evaluate(_green_evidence(), expected_sha=SHA)

    assert result == {
        "schema_version": 1,
        "gate": "ISSUE-25-EXTERNAL-CERTIFICATION",
        "decision": "GO",
        "commit_sha": SHA,
        "blockers": [],
    }


def test_rejects_jobs_that_never_received_a_runner_or_executed_steps():
    evidence = _green_evidence()
    evidence["ci"]["jobs"][0]["runner_id"] = 0
    evidence["ci"]["jobs"][0]["steps_executed"] = 0

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "NO_GO"
    assert "CI job Backend did not receive a runner" in result["blockers"]
    assert "CI job Backend executed no steps" in result["blockers"]


def test_rejects_sha_drift_in_ci_evidence():
    evidence = _green_evidence()
    evidence["ci"]["head_sha"] = "a" * 40

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "NO_GO"
    assert "CI head_sha must match the certified commit_sha" in result["blockers"]


def test_rejects_incomplete_sentry_and_non_physical_android_evidence():
    evidence = _green_evidence()
    evidence["sentry"]["alerts"][0]["delivered"] = False
    evidence["android"]["physical_device"] = False
    evidence["android"]["emulator"] = True

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "NO_GO"
    assert "Sentry alert manager-cls notification delivery is not proven" in result["blockers"]
    assert "Android evidence must come from a physical device" in result["blockers"]
    assert "Android emulator evidence cannot certify the physical-device gate" in result["blockers"]


def test_rejects_secret_bearing_evidence_and_never_echoes_secret_values():
    evidence = _green_evidence()
    evidence["sentry"]["dsn"] = "https://" + "public:private@" + "sentry.example.invalid/1"

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "INVALID"
    assert "evidence contains prohibited secret-bearing key: sentry.dsn" in result["blockers"]
    assert "private" not in str(result)


def test_rejects_missing_alerts_and_invalid_low_end_claim():
    evidence = deepcopy(_green_evidence())
    evidence["sentry"]["alerts"] = evidence["sentry"]["alerts"][:-1]
    evidence["android"]["ram_mb"] = 8192

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "NO_GO"
    assert "Sentry alerts are incomplete: driver-sync-error" in result["blockers"]
    assert "Android low-end evidence requires ram_mb between 512 and 4096" in result["blockers"]


def test_rejects_unknown_fields_that_could_smuggle_identity_data():
    evidence = _green_evidence()
    evidence["sentry"]["tenant_id"] = "tenant-must-not-be-recorded"
    evidence["android"]["tester_email"] = "person@example.invalid"

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "INVALID"
    assert "evidence contains non-allowlisted key: sentry.tenant_id" in result["blockers"]
    assert "evidence contains non-allowlisted key: android.tester_email" in result["blockers"]
    assert "tenant-must-not-be-recorded" not in str(result)
    assert "person@example.invalid" not in str(result)


def test_versioned_template_is_intentionally_invalid_and_fail_closed():
    template = json.loads(
        (ROOT / "infra" / "release" / "ISSUE25_EXTERNAL_CERTIFICATION.template.json").read_text(
            encoding="utf-8",
        )
    )

    result = evaluate(template, expected_sha="0" * 40)

    assert result["decision"] == "INVALID"
    assert result["blockers"]
    assert "CI run_id must be a positive integer" in result["blockers"]
    assert all("prohibited" not in blocker for blocker in result["blockers"])
    assert all("non-allowlisted" not in blocker for blocker in result["blockers"])


def test_rejects_unknown_job_and_alert_names_without_echoing_them():
    evidence = _green_evidence()
    evidence["ci"]["jobs"].append(
        {"name": "person@example.invalid", "conclusion": "success", "runner_id": 9, "steps_executed": 2}
    )
    evidence["sentry"]["alerts"].append(
        {
            "name": "tenant-secret-name",
            "test_fired": True,
            "delivered": True,
            "runbook_url": "https://runbooks.example.invalid/extra",
        }
    )

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "INVALID"
    assert "CI evidence contains unsupported job names" in result["blockers"]
    assert "Sentry evidence contains unsupported alert names" in result["blockers"]
    assert "person@example.invalid" not in str(result)
    assert "tenant-secret-name" not in str(result)


def test_rejects_evidence_urls_with_embedded_credentials_or_query_tokens():
    evidence = _green_evidence()
    evidence["sentry"]["dashboard_url"] = (
        "https://" + "user:password@" + "sentry.example.invalid/dashboard"
    )
    evidence["android"]["artifact_url"] = "https://evidence.example.invalid/android?token=secret"

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "NO_GO"
    assert "Sentry dashboard_url must be an HTTPS evidence URL" in result["blockers"]
    assert "Android artifact_url must be an HTTPS evidence URL" in result["blockers"]
    assert "password" not in str(result)
    assert "token=secret" not in str(result)


def test_rejects_duplicate_jobs_alerts_and_non_positive_run_id():
    evidence = _green_evidence()
    evidence["ci"]["run_id"] = 0
    evidence["ci"]["jobs"].append(deepcopy(evidence["ci"]["jobs"][0]))
    evidence["sentry"]["alerts"].append(deepcopy(evidence["sentry"]["alerts"][0]))

    result = evaluate(evidence, expected_sha=SHA)

    assert result["decision"] == "INVALID"
    assert "CI run_id must be a positive integer" in result["blockers"]
    assert "CI evidence contains duplicate job names" in result["blockers"]
    assert "Sentry evidence contains duplicate alert names" in result["blockers"]
