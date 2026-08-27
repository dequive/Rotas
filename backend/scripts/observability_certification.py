"""Fail-closed PR-20 certification for release observability evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.validate_observability import REQUIRED_ALERTS, REQUIRED_SLOS

POLICY_ID = "PR20-OBSERVABILITY-CERTIFICATION-V1"
RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
FILE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
RFC3339_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
REQUIRED_TRACE_SERVICES = {"backend", "governance", "worker"}
REQUIRED_RUNTIME_METRICS = {
    "rotas_db_pool_connections",
    "rotas_db_pool_capacity",
    "rotas_db_pool_checkouts",
    "rotas_db_pool_invalidations",
    "rotas_event_loop_lag_seconds",
    "rotas_process_cpu_utilization_ratio",
}
REQUIRED_EVIDENCE = {
    "metrics": {"metrics_snapshot", "dashboard_export"},
    "logs": {"logs_query", "logs_pii_scan"},
    "traces": {"trace_export", "trace_pii_scan"},
    "alerts": {f"alert_drill:{alert}" for alert in REQUIRED_ALERTS},
    "slo_window": {"slo_report"},
}
SLO_OBJECTIVES = {
    "api_availability": ("minimum", 0.999),
    "api_latency_p95": ("maximum", 0.2),
    "outbox_dead_letter": ("maximum", 0.0),
    "metrics_target_availability": ("minimum", 0.999),
}


class ObservabilityCertificationError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: object) -> datetime | None:
    text = str(value)
    if not RFC3339_Z.fullmatch(text):
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


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
        blockers.append("evidence must contain exactly the five PR-20 evidence groups.")
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


def _validate_alerts(
    alerts: object,
    *,
    release_sha: str,
    blockers: list[str],
) -> None:
    if not isinstance(alerts, dict) or set(alerts) != REQUIRED_ALERTS:
        blockers.append("alerts must contain exactly the five canonical PR-20 alerts.")
        return
    for alert_name in sorted(REQUIRED_ALERTS):
        drill = alerts.get(alert_name)
        if not isinstance(drill, dict):
            blockers.append(f"alerts.{alert_name} drill is required.")
            continue
        if drill.get("release_sha") != release_sha:
            blockers.append(f"alerts.{alert_name} release SHA mismatch.")
        timestamps = [
            _timestamp(drill.get(field))
            for field in ("fired_at", "delivered_at", "acknowledged_at", "resolved_at")
        ]
        if any(value is None for value in timestamps):
            blockers.append(f"alerts.{alert_name} timestamps are invalid.")
        else:
            ordered = [value for value in timestamps if value is not None]
            if ordered != sorted(ordered) or len(set(ordered)) != 4:
                blockers.append(f"alerts.{alert_name} lifecycle order is invalid.")
        channel = str(drill.get("channel", "")).strip().lower()
        if not channel or channel in {"test", "local", "null", "console"}:
            blockers.append(f"alerts.{alert_name} real delivery channel is required.")
        if not str(drill.get("delivery_id", "")).strip():
            blockers.append(f"alerts.{alert_name} delivery_id is required.")
        if not str(drill.get("acknowledged_by_role", "")).strip():
            blockers.append(f"alerts.{alert_name} acknowledgement role is required.")
        if drill.get("firing_observed") is not True:
            blockers.append(f"alerts.{alert_name} firing was not observed.")
        if drill.get("resolved_observed") is not True:
            blockers.append(f"alerts.{alert_name} resolution was not observed.")


def evaluate_observability_certification(
    context: object,
    *,
    base_dir: Path,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not isinstance(context, dict):
        raise ObservabilityCertificationError(
            "Observability certification context must be an object."
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
    if not str(context.get("operator", "")).strip():
        blockers.append("operator is required.")

    evidence_count = _validate_evidence(
        context.get("evidence"),
        base_dir=base_dir,
        release_sha=release_sha,
        blockers=blockers,
    )

    metrics = context.get("metrics")
    if not isinstance(metrics, dict):
        blockers.append("metrics result is required.")
    else:
        metric_expectations = {
            "release_sha": release_sha,
            "prometheus_healthy": True,
            "backend_target_up": True,
            "dashboard_uid": "rotas-release-slos",
            "sensitive_label_scan_clean": True,
        }
        for key, value in metric_expectations.items():
            actual = metrics.get(key)
            if (isinstance(value, bool) and actual is not value) or (
                not isinstance(value, bool) and actual != value
            ):
                blockers.append(f"metrics.{key} mismatch.")
        if (
            not _finite_number(metrics.get("rule_evaluation_failures"))
            or metrics["rule_evaluation_failures"] != 0
        ):
            blockers.append("metrics.rule_evaluation_failures mismatch.")
        if not isinstance(metrics.get("dashboard_panels"), int) or metrics[
            "dashboard_panels"
        ] < 10:
            blockers.append("metrics.dashboard_panels must be at least 10.")
        if not _exact_string_set(metrics.get("slo_series"), REQUIRED_SLOS):
            blockers.append("metrics.slo_series set mismatch.")
        if not _exact_string_set(
            metrics.get("runtime_metrics"),
            REQUIRED_RUNTIME_METRICS,
        ):
            blockers.append("metrics.runtime_metrics set mismatch.")

    logs = context.get("logs")
    if not isinstance(logs, dict):
        blockers.append("logs result is required.")
    else:
        if not str(logs.get("provider", "")).strip():
            blockers.append("logs.provider is required.")
        log_expectations = {
            "centralized": True,
            "searchable_by_release_sha": True,
            "request_id_correlation": True,
            "tenant_access_control": True,
        }
        for key, value in log_expectations.items():
            if logs.get(key) is not value:
                blockers.append(f"logs.{key} mismatch.")
        if not _finite_number(logs.get("pii_findings")) or logs["pii_findings"] != 0:
            blockers.append("logs.pii_findings mismatch.")
        if not isinstance(logs.get("retention_days"), int) or logs["retention_days"] < 30:
            blockers.append("logs.retention_days must be at least 30.")

    traces = context.get("traces")
    if not isinstance(traces, dict):
        blockers.append("traces result is required.")
    else:
        if not str(traces.get("provider", "")).strip():
            blockers.append("traces.provider is required.")
        trace_expectations = {
            "enabled": True,
            "searchable_by_release_sha": True,
            "request_id_correlation": True,
            "error_trace_captured": True,
        }
        for key, value in trace_expectations.items():
            if traces.get(key) is not value:
                blockers.append(f"traces.{key} mismatch.")
        if (
            not _finite_number(traces.get("pii_findings"))
            or traces["pii_findings"] != 0
        ):
            blockers.append("traces.pii_findings mismatch.")
        if not _exact_string_set(traces.get("services"), REQUIRED_TRACE_SERVICES):
            blockers.append("traces.services set mismatch.")
        if not isinstance(traces.get("sampled_journeys"), int) or traces[
            "sampled_journeys"
        ] < 4:
            blockers.append("traces.sampled_journeys must be at least 4.")
        if (
            not isinstance(traces.get("retention_days"), int)
            or traces["retention_days"] < 7
        ):
            blockers.append("traces.retention_days must be at least 7.")

    _validate_alerts(
        context.get("alerts"),
        release_sha=release_sha,
        blockers=blockers,
    )

    slo_window = context.get("slo_window")
    if not isinstance(slo_window, dict):
        blockers.append("slo_window result is required.")
    else:
        start = _timestamp(slo_window.get("started_at"))
        end = _timestamp(slo_window.get("ended_at"))
        if start is None or end is None or end - start < timedelta(days=30):
            blockers.append("slo_window must cover at least 30 complete days.")
        if slo_window.get("complete") is not True:
            blockers.append("slo_window.complete must be true.")
        coverage = slo_window.get("coverage_ratio")
        if not _finite_number(coverage):
            blockers.append("slo_window.coverage_ratio must be between 0.99 and 1.")
        else:
            assert isinstance(coverage, (int, float)) and not isinstance(coverage, bool)
            coverage_number = float(coverage)
            if coverage_number < 0.99 or coverage_number > 1:
                blockers.append(
                    "slo_window.coverage_ratio must be between 0.99 and 1."
                )
        slos = slo_window.get("slos")
        if not isinstance(slos, dict) or set(slos) != REQUIRED_SLOS:
            blockers.append("slo_window.slos set mismatch.")
            slos = {}
        for slo_id, (direction, objective) in SLO_OBJECTIVES.items():
            item = slos.get(slo_id)
            if not isinstance(item, dict):
                blockers.append(f"slo_window.slos.{slo_id} result is required.")
                continue
            value = item.get("value")
            if not _finite_number(value):
                blockers.append(f"slo_window.slos.{slo_id}.value is invalid.")
                continue
            assert isinstance(value, (int, float)) and not isinstance(value, bool)
            numeric_value = float(value)
            meets = (
                numeric_value >= objective
                if direction == "minimum"
                else numeric_value <= objective
            )
            if not meets or item.get("objective_met") is not True:
                blockers.append(f"slo_window.slos.{slo_id} objective is not met.")
            if not _positive_int(item.get("sample_count")):
                blockers.append(f"slo_window.slos.{slo_id}.sample_count is invalid.")

    global_integrity_failed = any(
        blocker.startswith(
            (
                "schema_version",
                "policy_id",
                "environment",
                "release_sha",
                "observed_at",
                "external_runner",
                "operator",
                "evidence must contain",
                "duplicate evidence path",
            )
        )
        for blocker in blockers
    )
    controls = {}
    control_sections = {
        "metrics": "metrics",
        "logs": "logs",
        "traces": "traces",
        "alerts_delivered": "alerts",
        "slo_window": "slo_window",
    }
    for control, section in control_sections.items():
        controls[control] = not global_integrity_failed and not any(
            blocker.startswith(section)
            or blocker.startswith(f"evidence.{section}")
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
        result = evaluate_observability_certification(
            context,
            base_dir=context_path.parent,
        )
    except (OSError, json.JSONDecodeError, ObservabilityCertificationError) as exc:
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
