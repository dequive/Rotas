import hashlib
import json
from pathlib import Path

from scripts.observability_certification import (
    REQUIRED_EVIDENCE,
    REQUIRED_RUNTIME_METRICS,
    REQUIRED_TRACE_SERVICES,
    evaluate_observability_certification,
)
from scripts.validate_observability import REQUIRED_ALERTS, REQUIRED_SLOS

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _write_artifact(tmp_path: Path, kind: str) -> dict:
    path = tmp_path / f"{kind.replace(':', '-')}.json"
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
    evidence = {
        group: [_write_artifact(tmp_path, kind) for kind in sorted(kinds)]
        for group, kinds in REQUIRED_EVIDENCE.items()
    }
    alerts = {
        alert: {
            "release_sha": RELEASE_SHA,
            "fired_at": "2026-07-31T08:00:00Z",
            "delivered_at": "2026-07-31T08:00:10Z",
            "acknowledged_at": "2026-07-31T08:01:00Z",
            "resolved_at": "2026-07-31T08:05:00Z",
            "channel": "pagerduty-staging",
            "delivery_id": f"delivery-{alert}",
            "acknowledged_by_role": "SRE",
            "firing_observed": True,
            "resolved_observed": True,
        }
        for alert in REQUIRED_ALERTS
    }
    return {
        "schema_version": 1,
        "policy_id": "PR20-OBSERVABILITY-CERTIFICATION-V1",
        "environment": "staging",
        "release_sha": RELEASE_SHA,
        "observed_at": "2026-07-31T09:00:00Z",
        "external_runner": True,
        "operator": "sre-independent",
        "metrics": {
            "release_sha": RELEASE_SHA,
            "prometheus_healthy": True,
            "backend_target_up": True,
            "rule_evaluation_failures": 0,
            "dashboard_uid": "rotas-release-slos",
            "dashboard_panels": 10,
            "sensitive_label_scan_clean": True,
            "slo_series": sorted(REQUIRED_SLOS),
            "runtime_metrics": sorted(REQUIRED_RUNTIME_METRICS),
        },
        "logs": {
            "provider": "central-log-store",
            "centralized": True,
            "searchable_by_release_sha": True,
            "request_id_correlation": True,
            "tenant_access_control": True,
            "pii_findings": 0,
            "retention_days": 30,
        },
        "traces": {
            "provider": "central-trace-store",
            "enabled": True,
            "searchable_by_release_sha": True,
            "request_id_correlation": True,
            "error_trace_captured": True,
            "pii_findings": 0,
            "services": sorted(REQUIRED_TRACE_SERVICES),
            "sampled_journeys": 4,
            "retention_days": 7,
        },
        "alerts": alerts,
        "slo_window": {
            "started_at": "2026-07-01T00:00:00Z",
            "ended_at": "2026-07-31T00:00:00Z",
            "complete": True,
            "coverage_ratio": 0.999,
            "slos": {
                "api_availability": {
                    "value": 0.9995,
                    "objective_met": True,
                    "sample_count": 100_000,
                },
                "api_latency_p95": {
                    "value": 0.18,
                    "objective_met": True,
                    "sample_count": 100_000,
                },
                "outbox_dead_letter": {
                    "value": 0,
                    "objective_met": True,
                    "sample_count": 10_000,
                },
                "metrics_target_availability": {
                    "value": 1,
                    "objective_met": True,
                    "sample_count": 86_400,
                },
            },
        },
        "evidence": evidence,
    }


def test_observability_certification_passes_complete_bundle(tmp_path):
    result = evaluate_observability_certification(
        _context(tmp_path),
        base_dir=tmp_path,
    )

    assert result["decision"] == "PASS"
    assert result["controls"] == {
        "metrics": True,
        "logs": True,
        "traces": True,
        "alerts_delivered": True,
        "slo_window": True,
    }
    assert result["evidence_files"] == 12
    assert result["blockers"] == []


def test_observability_certification_rejects_each_runtime_control(tmp_path):
    context = _context(tmp_path)
    context["metrics"]["backend_target_up"] = False
    context["logs"]["pii_findings"] = 1
    context["traces"]["services"] = ["backend"]
    alert = sorted(REQUIRED_ALERTS)[0]
    context["alerts"][alert]["channel"] = "test"
    context["slo_window"]["slos"]["api_latency_p95"]["value"] = 0.4

    result = evaluate_observability_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert result["controls"] == {
        "metrics": False,
        "logs": False,
        "traces": False,
        "alerts_delivered": False,
        "slo_window": False,
    }


def test_observability_certification_rejects_hash_physical_sha_and_duplicates(
    tmp_path,
):
    context = _context(tmp_path)
    context["evidence"]["metrics"][0]["sha256"] = "0" * 64
    trace_path = tmp_path / context["evidence"]["traces"][0]["path"]
    physical = json.loads(trace_path.read_text(encoding="utf-8"))
    physical["release_sha"] = "f" * 40
    trace_path.write_text(json.dumps(physical, sort_keys=True), encoding="utf-8")
    context["evidence"]["traces"][0]["sha256"] = hashlib.sha256(
        trace_path.read_bytes()
    ).hexdigest()
    context["evidence"]["logs"].append(context["evidence"]["logs"][0].copy())

    result = evaluate_observability_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "evidence.metrics[0] hash mismatch" in blockers
    assert "physical release SHA mismatch" in blockers
    assert "evidence.logs duplicate kind" in blockers


def test_observability_certification_rejects_short_window_and_alert_order(tmp_path):
    context = _context(tmp_path)
    context["slo_window"]["started_at"] = "2026-07-30T00:00:00Z"
    context["slo_window"]["coverage_ratio"] = float("nan")
    context["slo_window"]["slos"]["api_availability"]["sample_count"] = True
    context["metrics"]["slo_series"] = None
    alert = sorted(REQUIRED_ALERTS)[0]
    context["alerts"][alert]["resolved_at"] = "2026-07-31T08:00:05Z"

    result = evaluate_observability_certification(context, base_dir=tmp_path)

    blockers = " ".join(result["blockers"])
    assert result["decision"] == "NO-GO"
    assert "slo_window must cover at least 30 complete days" in blockers
    assert "slo_window.coverage_ratio must be between 0.99 and 1" in blockers
    assert "api_availability.sample_count is invalid" in blockers
    assert "metrics.slo_series set mismatch" in blockers
    assert f"alerts.{alert} lifecycle order is invalid" in blockers


def test_observability_certification_makes_all_controls_false_on_global_drift(
    tmp_path,
):
    context = _context(tmp_path)
    context["external_runner"] = False

    result = evaluate_observability_certification(context, base_dir=tmp_path)

    assert result["decision"] == "NO-GO"
    assert all(value is False for value in result["controls"].values())
