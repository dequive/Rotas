"""Validate external certification evidence for ROTAS Issue #25."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

GATE = "ISSUE-25-EXTERNAL-CERTIFICATION"
REQUIRED_JOBS = {"Backend", "Frontend", "E2E"}
REQUIRED_ALERTS = {
    "manager-cls",
    "manager-lcp",
    "manager-inp",
    "driver-bootstrap",
    "driver-sync",
    "driver-bootstrap-unavailable",
    "driver-sync-error",
}
PROHIBITED_KEYS = {
    "auth_token",
    "dsn",
    "password",
    "private_key",
    "secret",
    "token",
}
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_KEYS = {
    "": {"schema_version", "gate", "commit_sha", "ci", "sentry", "android"},
    "ci": {"run_id", "head_sha", "conclusion", "jobs"},
    "ci.jobs[]": {"name", "conclusion", "runner_id", "steps_executed"},
    "sentry": {
        "environment",
        "send_default_pii",
        "manager_spans_observed",
        "driver_spans_observed",
        "dashboard_url",
        "alerts",
    },
    "sentry.alerts[]": {"name", "test_fired", "delivered", "runbook_url"},
    "android": {
        "physical_device",
        "emulator",
        "performance_class",
        "ram_mb",
        "network_profile",
        "reduced_motion_passed",
        "offline_sync_passed",
        "driver_tests_passed",
        "artifact_url",
    },
}


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _prohibited_paths(value: object, *, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            if key.lower() in PROHIBITED_KEYS:
                found.append(child_path)
            found.extend(_prohibited_paths(child, path=child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_prohibited_paths(child, path=f"{path}[{index}]"))
    return found


def _unknown_paths(value: object, *, path: str = "") -> list[str]:
    found: list[str] = []
    if not isinstance(value, dict):
        return found
    allowed = ALLOWED_KEYS.get(path)
    if allowed is None:
        return found
    for raw_key, child in value.items():
        key = str(raw_key)
        child_path = f"{path}.{key}" if path else key
        if key not in allowed:
            found.append(child_path)
            continue
        if child_path == "ci.jobs" and isinstance(child, list):
            for item in child:
                found.extend(_unknown_paths(item, path="ci.jobs[]"))
        elif child_path == "sentry.alerts" and isinstance(child, list):
            for item in child:
                found.extend(_unknown_paths(item, path="sentry.alerts[]"))
        else:
            found.extend(_unknown_paths(child, path=child_path))
    return found


def _valid_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlsplit(value)
    return (
        parsed.scheme == "https"
        and bool(parsed.hostname)
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
    )


def evaluate(evidence: object, *, expected_sha: str) -> dict[str, Any]:
    """Return a fail-closed decision without including evidence values."""
    invalid: list[str] = []
    blockers: list[str] = []
    data = _mapping(evidence)

    if not data:
        invalid.append("evidence must be an object")
    if not FULL_SHA.fullmatch(expected_sha):
        invalid.append("expected_sha must be a full lowercase Git SHA")
    for secret_path in _prohibited_paths(evidence):
        invalid.append(f"evidence contains prohibited secret-bearing key: {secret_path}")
    for unknown_path in _unknown_paths(evidence):
        invalid.append(f"evidence contains non-allowlisted key: {unknown_path}")
    if data.get("schema_version") != 1:
        invalid.append("schema_version must be 1")
    if data.get("gate") != GATE:
        invalid.append(f"gate must be {GATE}")

    commit_sha = data.get("commit_sha")
    if not isinstance(commit_sha, str) or not FULL_SHA.fullmatch(commit_sha):
        invalid.append("commit_sha must be a full lowercase Git SHA")
        safe_commit_sha = ""
    else:
        safe_commit_sha = commit_sha
        if commit_sha != expected_sha:
            blockers.append("commit_sha must match the expected release candidate SHA")

    ci = _mapping(data.get("ci"))
    if ci.get("head_sha") != safe_commit_sha:
        blockers.append("CI head_sha must match the certified commit_sha")
    if ci.get("conclusion") != "success":
        blockers.append("CI run conclusion must be success")
    run_id = ci.get("run_id")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id <= 0:
        invalid.append("CI run_id must be a positive integer")

    raw_jobs = ci.get("jobs")
    jobs: list[object] = raw_jobs if isinstance(raw_jobs, list) else []
    jobs_by_name = {
        job.get("name"): job
        for raw_job in jobs
        if (job := _mapping(raw_job)) and isinstance(job.get("name"), str)
    }
    if len(jobs_by_name) != len(jobs):
        invalid.append("CI evidence contains duplicate job names")
    missing_jobs = sorted(REQUIRED_JOBS - jobs_by_name.keys())
    if missing_jobs:
        blockers.append(f"CI jobs are incomplete: {', '.join(missing_jobs)}")
    if jobs_by_name.keys() - REQUIRED_JOBS:
        invalid.append("CI evidence contains unsupported job names")
    for name in sorted(REQUIRED_JOBS & jobs_by_name.keys()):
        job = jobs_by_name[name]
        if job.get("conclusion") != "success":
            blockers.append(f"CI job {name} conclusion must be success")
        runner_id = job.get("runner_id")
        if not isinstance(runner_id, int) or isinstance(runner_id, bool) or runner_id <= 0:
            blockers.append(f"CI job {name} did not receive a runner")
        steps = job.get("steps_executed")
        if not isinstance(steps, int) or isinstance(steps, bool) or steps <= 0:
            blockers.append(f"CI job {name} executed no steps")

    sentry = _mapping(data.get("sentry"))
    if sentry.get("environment") in {None, "", "production"}:
        blockers.append("Sentry certification must use an explicit non-production environment")
    if sentry.get("send_default_pii") is not False:
        blockers.append("Sentry send_default_pii must be false")
    if sentry.get("manager_spans_observed") is not True:
        blockers.append("Sentry Manager spans are not proven")
    if sentry.get("driver_spans_observed") is not True:
        blockers.append("Sentry Driver spans are not proven")
    if not _valid_https_url(sentry.get("dashboard_url")):
        blockers.append("Sentry dashboard_url must be an HTTPS evidence URL")

    raw_alerts = sentry.get("alerts")
    alerts: list[object] = raw_alerts if isinstance(raw_alerts, list) else []
    alerts_by_name = {
        alert.get("name"): alert
        for raw_alert in alerts
        if (alert := _mapping(raw_alert)) and isinstance(alert.get("name"), str)
    }
    if len(alerts_by_name) != len(alerts):
        invalid.append("Sentry evidence contains duplicate alert names")
    missing_alerts = sorted(REQUIRED_ALERTS - alerts_by_name.keys())
    if missing_alerts:
        blockers.append(f"Sentry alerts are incomplete: {', '.join(missing_alerts)}")
    if alerts_by_name.keys() - REQUIRED_ALERTS:
        invalid.append("Sentry evidence contains unsupported alert names")
    for name in sorted(REQUIRED_ALERTS & alerts_by_name.keys()):
        alert = alerts_by_name[name]
        if alert.get("test_fired") is not True:
            blockers.append(f"Sentry alert {name} was not test-fired")
        if alert.get("delivered") is not True:
            blockers.append(f"Sentry alert {name} notification delivery is not proven")
        if not _valid_https_url(alert.get("runbook_url")):
            blockers.append(f"Sentry alert {name} requires an HTTPS runbook_url")

    android = _mapping(data.get("android"))
    if android.get("physical_device") is not True:
        blockers.append("Android evidence must come from a physical device")
    if android.get("emulator") is not False:
        blockers.append("Android emulator evidence cannot certify the physical-device gate")
    if android.get("performance_class") != "low_end":
        blockers.append("Android performance_class must be low_end")
    ram_mb = android.get("ram_mb")
    if not isinstance(ram_mb, int) or isinstance(ram_mb, bool) or not 512 <= ram_mb <= 4096:
        blockers.append("Android low-end evidence requires ram_mb between 512 and 4096")
    if android.get("network_profile") != "unstable":
        blockers.append("Android network_profile must be unstable")
    for field, message in (
        ("reduced_motion_passed", "Android reduced-motion journey is not proven"),
        ("offline_sync_passed", "Android offline sync journey is not proven"),
        ("driver_tests_passed", "Android Driver test journey is not proven"),
    ):
        if android.get(field) is not True:
            blockers.append(message)
    if not _valid_https_url(android.get("artifact_url")):
        blockers.append("Android artifact_url must be an HTTPS evidence URL")

    decision = "INVALID" if invalid else ("NO_GO" if blockers else "GO")
    return {
        "schema_version": 1,
        "gate": GATE,
        "decision": decision,
        "commit_sha": safe_commit_sha,
        "blockers": invalid + blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        result = evaluate(evidence, expected_sha=args.expected_sha)
    except (OSError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": 1,
            "gate": GATE,
            "decision": "INVALID",
            "commit_sha": "",
            "blockers": [f"cannot read valid evidence JSON: {type(exc).__name__}"],
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "GO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
