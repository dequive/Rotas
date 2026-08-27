"""Static fail-closed validation for the PR-20 observability baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


class ObservabilityPolicyError(ValueError):
    pass


REQUIRED_SLOS = {
    "api_availability",
    "api_latency_p95",
    "outbox_dead_letter",
    "metrics_target_availability",
}
REQUIRED_ALERTS = {
    "RotasBackendDown",
    "RotasApiHighErrorRate",
    "RotasApiLatencyBudget",
    "RotasOutboxDeadLetter",
    "RotasPrometheusRuleFailures",
}
PINNED_IMAGES = {
    "prom/prometheus@sha256:cff72a3f49918f41c4b5c8a6174dd8433036bebf7878120da538b3720ba3fa0d",
    "prom/alertmanager@sha256:51a825c2a40acc3e338fdd00d622e01ec090f72be2b3ea46be0839cd47a4d286",
    "grafana/grafana@sha256:121a7a9ece6dc10b969f1f96eed64b4f07dfac0d0b8abc070f7cb83bbde86f63",
}


def validate_observability_policy(repo_root: Path) -> dict[str, int]:
    root = repo_root / "infra" / "observability"
    compose = (repo_root / "infra" / "staging" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    prometheus = (root / "prometheus.yml").read_text(encoding="utf-8")
    rules = (root / "rules" / "rotas-slo.rules.yml").read_text(encoding="utf-8")
    alertmanager = (root / "alertmanager.yml").read_text(encoding="utf-8")
    rule_tests = (root / "tests" / "rotas-slo.test.yml").read_text(encoding="utf-8")
    dashboard = json.loads(
        (root / "grafana" / "dashboards" / "rotas-slo.json").read_text(
            encoding="utf-8"
        )
    )
    catalog = json.loads(
        (repo_root / "docs" / "observability" / "ROTAS_SLO_CATALOG.json").read_text(
            encoding="utf-8"
        )
    )
    failures: list[str] = []

    slo_ids = {item.get("id") for item in catalog.get("slos", [])}
    if slo_ids != REQUIRED_SLOS:
        failures.append("SLO catalog must contain exactly the required release SLIs.")
    for item in catalog.get("slos", []):
        for field in ("owner", "window_days", "indicator", "source", "alert", "runbook"):
            if not item.get(field):
                failures.append(f"SLO {item.get('id')!r} is missing {field}.")

    for alert in REQUIRED_ALERTS:
        if f"alert: {alert}" not in rules:
            failures.append(f"required alert is missing: {alert}")
        if f"alertname: {alert}" not in rule_tests:
            failures.append(f"required alert has no temporal rule test: {alert}")
    if "runbook:" not in rules or "severity:" not in rules:
        failures.append("Every alert group must expose severity and runbook metadata.")

    for image in PINNED_IMAGES:
        if image not in compose:
            failures.append(f"observability image is not pinned in staging: {image}")
    for required in (
        "job_name: rotas-backend",
        "alertmanager:9093",
        "/etc/prometheus/rules/*.yml",
    ):
        if required not in prometheus:
            failures.append(f"Prometheus control is missing: {required}")
    if "url_file: /run/secrets/alertmanager_webhook_url" not in alertmanager:
        failures.append("Alertmanager must load its webhook from an external secret.")

    if dashboard.get("uid") != "rotas-release-slos":
        failures.append("Grafana dashboard must have the canonical stable UID.")
    panels = dashboard.get("panels", [])
    if len(panels) < 7:
        failures.append("Grafana release dashboard must contain at least seven panels.")

    public_surface = "\n".join(
        (prometheus, rules, alertmanager, rule_tests, json.dumps(dashboard))
    )
    for forbidden in ("tenant_id", "user_id", "document_id", "event_id"):
        if forbidden in public_surface:
            failures.append(f"high-cardinality or sensitive label is forbidden: {forbidden}")

    pool_metrics = (
        repo_root / "backend" / "app" / "core" / "database_pool_metrics.py"
    ).read_text(encoding="utf-8")
    runtime_metrics = (
        repo_root / "backend" / "app" / "core" / "runtime_metrics.py"
    ).read_text(encoding="utf-8")
    main = (repo_root / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    gunicorn_metrics = (
        repo_root / "backend" / "app" / "gunicorn_conf.py"
    ).read_text(encoding="utf-8")
    backend_dockerfile = (repo_root / "backend" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    railway = (repo_root / "backend" / "railway.toml").read_text(encoding="utf-8")
    for required_pool_metric in (
        "rotas_db_pool_connections",
        "rotas_db_pool_capacity",
        "rotas_db_pool_checkouts",
        "rotas_db_pool_invalidations",
    ):
        if required_pool_metric not in pool_metrics:
            failures.append(
                f"Database pool telemetry is missing: {required_pool_metric}"
            )
    for forbidden in ("tenant_id", "user_id", "document_id", "connection_id"):
        if f'"{forbidden}"' in pool_metrics:
            failures.append(
                f"Database pool telemetry contains a forbidden label: {forbidden}"
            )
    if pool_metrics.count('multiprocess_mode="livesum"') < 2:
        failures.append("Pool occupancy and capacity must use livesum gauges.")
    if "set_function" in pool_metrics:
        failures.append("Callback gauges are not valid for multiprocess pool telemetry.")
    for metric_name, mode in (
        ("rotas_event_loop_lag_seconds", 'multiprocess_mode="livemax"'),
        ("rotas_process_cpu_utilization_ratio", 'multiprocess_mode="livesum"'),
    ):
        if metric_name not in runtime_metrics or mode not in runtime_metrics:
            failures.append(
                f"Worker runtime telemetry is missing or not aggregated: {metric_name}"
            )
        if metric_name not in json.dumps(dashboard):
            failures.append(f"Dashboard is missing worker runtime metric: {metric_name}")
    for lifecycle_hook in (
        "start_runtime_metrics_sampler",
        "stop_runtime_metrics_sampler",
    ):
        if lifecycle_hook not in main:
            failures.append(f"Runtime metrics lifecycle hook is missing: {lifecycle_hook}")
    for required_control in (
        "PROMETHEUS_MULTIPROC_DIR",
        "tempfile.gettempdir",
        "mark_process_dead",
        "*.db",
    ):
        if required_control not in gunicorn_metrics:
            failures.append(
                f"Gunicorn multiprocess control is missing: {required_control}"
            )
    if not all(
        token in backend_dockerfile
        for token in (
            '"--config"',
            '"python:app.gunicorn_conf"',
            '"--no-control-socket"',
        )
    ):
        failures.append("Backend image must load the Gunicorn metrics hooks.")
    if not all(
        token in railway
        for token in (
            "--config python:app.gunicorn_conf",
            "--no-control-socket",
        )
    ):
        failures.append("Railway runtime must load the Gunicorn metrics hooks.")

    if failures:
        raise ObservabilityPolicyError("; ".join(failures))
    return {
        "slos": len(slo_ids),
        "alerts": len(REQUIRED_ALERTS),
        "dashboard_panels": len(panels),
        "pinned_images": len(PINNED_IMAGES),
        "multiprocess_metrics": 1,
        "worker_runtime_metrics": 2,
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
        result = validate_observability_policy(args.repo_root.resolve())
    except (OSError, json.JSONDecodeError, ObservabilityPolicyError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
