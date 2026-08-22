"""Static, fail-closed validation for the PR-22 performance contract."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.performance_gate import PerformanceGateError, load_policy


def validate_performance_policy(repo_root: Path) -> dict[str, int]:
    policy_path = repo_root / "infra" / "performance" / "PERFORMANCE_BUDGETS.json"
    policy = load_policy(policy_path)
    failures: list[str] = []
    budgets = policy.get("budgets", {})
    required = {
        "api_read",
        "offline_sync_batch",
        "idempotency_race",
        "degraded_network",
    }
    if set(budgets) != required:
        failures.append("The four canonical PR-22 scenarios are required.")
    if budgets.get("api_read", {}).get("p95_http_ms") != 200:
        failures.append("API read p95 must match the 200 ms SLO.")
    if budgets.get("offline_sync_batch", {}).get("p95_http_ms") != 500:
        failures.append("Offline sync p95 must be 500 ms.")
    if budgets.get("offline_sync_batch", {}).get("max_domain_failure_rate") != 0:
        failures.append("Offline sync domain failures must be zero.")
    race = budgets.get("idempotency_race", {})
    if race.get("max_distinct_server_ids") != 1 or race.get("max_conflicts") != 0:
        failures.append("Concurrent idempotency must allow exactly one business effect.")
    degraded = budgets.get("degraded_network", {})
    if degraded.get("latency_ms", 0) < 200 or degraded.get(
        "simulated_loss_rate", 0
    ) <= 0:
        failures.append("Degraded network must include latency and delivery loss.")

    certification = policy.get("profiles", {}).get("staging_certification", {})
    expected_minimum_requests = {
        "api_read": 10_000,
        "offline_sync_batch": 3_000,
        "idempotency_race": 20,
        "degraded_network": 5_000,
    }
    for scenario, minimum in expected_minimum_requests.items():
        if certification.get(scenario, {}).get("minimum_requests") != minimum:
            failures.append(
                f"Staging minimum_requests for {scenario} must be {minimum}."
            )
    for control in (
        "representative_dataset_required",
        "restricted_database_role_required",
        "observability_window_required",
    ):
        if certification.get(control) is not True:
            failures.append(f"Staging certification control is missing: {control}")
    if certification.get("soak_seconds", 0) < 7200:
        failures.append("Staging soak must be at least two hours.")
    certification_controls = (
        "external_runner_required",
        "two_tenants_required",
        "pg_stat_statements_required",
        "worker_runtime_metrics_required",
    )
    for control in certification_controls:
        if certification.get(control) is not True:
            failures.append(f"Staging certification must require {control}.")
    if any(
        value != 0 for value in policy.get("release_invariants", {}).values()
    ):
        failures.append("Release integrity invariants must be zero-tolerance.")

    tooling = (
        repo_root / "backend" / "scripts" / "performance_gate.py"
    ).read_text(encoding="utf-8")
    for required_control in (
        "ROTAS_PERF_TOKEN",
        '"authorization": "redacted"',
        "engineering_evidence_only",
        "simulated_network_drop",
        "single_business_effect",
        "release_evidence_fragment",
    ):
        if required_control not in tooling:
            failures.append(f"Performance tooling control is missing: {required_control}")
    certification_tooling = (
        repo_root / "backend" / "scripts" / "performance_certification.py"
    ).read_text(encoding="utf-8")
    pg_stat_exporter = (
        repo_root / "backend" / "scripts" / "export_pg_stat_statements.py"
    ).read_text(encoding="utf-8")
    for required_control in (
        "Exactly two tenant contexts are required.",
        "backend_image must be an immutable RepoDigest.",
        "runner.location must be external.",
        "soak_seconds must be at least 7200.",
        "query_text_included",
    ):
        if required_control not in certification_tooling:
            failures.append(
                f"Certification bundle control is missing: {required_control}"
            )
    pg_stat_sql = pg_stat_exporter.split("PG_STAT_SQL", 1)[-1].split('"""', 2)[1].lower()
    for forbidden_export in ("query,", "query "):
        if forbidden_export in pg_stat_sql:
            failures.append("pg_stat_statements exporter must not select query text.")
    if failures:
        raise PerformanceGateError("; ".join(failures))
    return {
        "budgets": len(budgets),
        "release_invariants": len(policy["release_invariants"]),
        "staging_soak_seconds": int(certification["soak_seconds"]),
        "certification_controls": len(certification_controls),
        "certification_artifacts": 2,
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
        result = validate_performance_policy(args.repo_root.resolve())
    except (OSError, json.JSONDecodeError, PerformanceGateError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps({"status": "ok", **result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
