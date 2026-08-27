"""Fail-closed validation for a PR-22 RC/staging certification context."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

RELEASE_SHA = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
TOKEN_ENV = re.compile(r"^ROTAS_PERF_TENANT_[AB]_TOKEN$")
REQUIRED_SCENARIOS = frozenset(
    {
        "api_read",
        "offline_sync_batch",
        "idempotency_race",
        "degraded_network",
    }
)
MINIMUM_REQUESTS = {
    "api_read": 10_000,
    "offline_sync_batch": 3_000,
    "idempotency_race": 20,
    "degraded_network": 5_000,
}
PG_STAT_FIELDS = frozenset(
    {
        "queryid",
        "calls",
        "total_exec_time_ms",
        "mean_exec_time_ms",
        "rows",
        "shared_blks_hit",
        "shared_blks_read",
        "temp_blks_written",
    }
)


class PerformanceCertificationError(ValueError):
    pass


def _require_external_https(value: object, field: str, failures: list[str]) -> None:
    parsed = urlsplit(str(value or ""))
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.hostname in {"localhost", "127.0.0.1"}
        or parsed.hostname.endswith(".example.invalid")
    ):
        failures.append(f"{field} must be a real non-local HTTPS URL.")


def validate_pg_stat_report(report: object) -> int:
    if not isinstance(report, dict):
        raise PerformanceCertificationError("pg_stat_statements report must be an object.")
    failures: list[str] = []
    if report.get("schema_version") != 1:
        failures.append("pg_stat_statements schema_version must be 1.")
    if report.get("extension") != "pg_stat_statements":
        failures.append("pg_stat_statements extension evidence is missing.")
    if report.get("query_text_included") is not False:
        failures.append("pg_stat_statements evidence must explicitly exclude query text.")
    entries = report.get("entries")
    if not isinstance(entries, list) or not entries:
        failures.append("pg_stat_statements evidence must contain at least one entry.")
        entries = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or set(entry) != PG_STAT_FIELDS:
            failures.append(f"pg_stat_statements entry {index} has an invalid field set.")
            continue
        if not isinstance(entry.get("queryid"), int):
            failures.append(f"pg_stat_statements entry {index} queryid must be an integer.")
        for field in PG_STAT_FIELDS - {"queryid"}:
            value = entry.get(field)
            if not isinstance(value, (int, float)) or value < 0:
                failures.append(
                    f"pg_stat_statements entry {index} {field} must be non-negative."
                )
    if failures:
        raise PerformanceCertificationError("; ".join(failures))
    return len(entries)


def validate_performance_fragment(
    report: object,
    *,
    scenario: str,
    tenant_id: UUID,
    base_url: str,
    release_sha: str,
) -> None:
    if not isinstance(report, dict):
        raise PerformanceCertificationError("Performance fragment must be an object.")
    failures: list[str] = []
    if report.get("schema_version") != 1:
        failures.append("fragment schema_version must be 1.")
    if report.get("policy_id") != "PR22-PERFORMANCE-V1":
        failures.append("fragment policy_id is invalid.")
    if report.get("profile") != "staging_certification":
        failures.append("fragment profile must be staging_certification.")
    if report.get("evidence_class") != "release_evidence_fragment":
        failures.append("fragment evidence_class must be release_evidence_fragment.")
    if report.get("scenario") != scenario:
        failures.append(f"fragment scenario must be {scenario}.")
    if report.get("release_sha") != release_sha:
        failures.append("fragment release_sha does not match the certification context.")
    if report.get("passed") is not True:
        failures.append(f"fragment {scenario} must have passed.")
    checks = report.get("checks")
    if (
        not isinstance(checks, dict)
        or not checks
        or any(value is not True for value in checks.values())
    ):
        failures.append("fragment checks must all be explicitly true.")
    target = report.get("target")
    if not isinstance(target, dict):
        failures.append("fragment target is required.")
    else:
        if target.get("base_url") != base_url:
            failures.append("fragment base_url does not match certification context.")
        if target.get("tenant_id") != str(tenant_id):
            failures.append("fragment tenant_id does not match certification context.")
        if target.get("authorization") != "redacted":
            failures.append("fragment authorization must be redacted.")
    metrics = report.get("metrics")
    if not isinstance(metrics, dict):
        failures.append("fragment metrics are required.")
    else:
        if int(metrics.get("delivered_requests", 0) or 0) < MINIMUM_REQUESTS[scenario]:
            failures.append(f"fragment {scenario} has insufficient delivered requests.")
        if float(metrics.get("unexpected_error_rate", 1) or 0) > 0.01:
            failures.append(f"fragment {scenario} exceeded the error ceiling.")
        pool = metrics.get("database_pool_observation")
        if not isinstance(pool, dict) or int(pool.get("scrapes", 0) or 0) < 1:
            failures.append("fragment must include database pool scrapes.")
        runtime = metrics.get("worker_runtime_observation")
        runtime_metrics = runtime.get("metrics", {}) if isinstance(runtime, dict) else {}
        for metric_name in (
            "rotas_event_loop_lag_seconds",
            "rotas_process_cpu_utilization_ratio",
        ):
            metric = runtime_metrics.get(metric_name)
            if not isinstance(metric, dict) or int(metric.get("samples", 0) or 0) < 1:
                failures.append(f"fragment runtime metric is missing: {metric_name}")
    if failures:
        raise PerformanceCertificationError("; ".join(failures))


def validate_soak_report(
    report: object,
    *,
    release_sha: str,
) -> int:
    if not isinstance(report, dict):
        raise PerformanceCertificationError("Soak report must be an object.")
    failures: list[str] = []
    if report.get("schema_version") != 1:
        failures.append("soak schema_version must be 1.")
    if report.get("release_sha") != release_sha:
        failures.append("soak release_sha does not match the certification context.")
    duration = int(report.get("duration_seconds", 0) or 0)
    if duration < 7200:
        failures.append("soak duration must be at least 7200 seconds.")
    if report.get("observability_window_complete") is not True:
        failures.append("soak observability window must be complete.")
    if report.get("unresolved_sev1_sev2") != 0:
        failures.append("soak must have zero unresolved Sev-1/Sev-2 incidents.")
    if report.get("completed") is not True:
        failures.append("soak report must be completed.")
    if failures:
        raise PerformanceCertificationError("; ".join(failures))
    return duration


def _read_json_evidence(
    value: object,
    *,
    field: str,
    base_dir: Path,
) -> object:
    if not isinstance(value, str) or not value:
        raise PerformanceCertificationError(f"{field} path is required.")
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PerformanceCertificationError(f"Cannot read {field}: {exc}") from exc


def validate_certification_context(
    context: object,
    *,
    require_token_env: bool = False,
    base_dir: Path | None = None,
) -> dict[str, int]:
    if not isinstance(context, dict):
        raise PerformanceCertificationError("Certification context must be an object.")
    failures: list[str] = []
    if context.get("schema_version") != 1:
        failures.append("schema_version must be 1.")
    if context.get("policy_id") != "PR22-PERFORMANCE-V1":
        failures.append("policy_id must be PR22-PERFORMANCE-V1.")
    if not RELEASE_SHA.fullmatch(str(context.get("release_sha", ""))):
        failures.append("release_sha must be a full lowercase Git SHA.")
    if not IMAGE_DIGEST.fullmatch(str(context.get("backend_image", ""))):
        failures.append("backend_image must be an immutable RepoDigest.")

    _require_external_https(context.get("base_url"), "base_url", failures)
    _require_external_https(context.get("metrics_url"), "metrics_url", failures)

    runner = context.get("runner")
    if not isinstance(runner, dict):
        failures.append("runner metadata is required.")
    else:
        if runner.get("location") != "external":
            failures.append("runner.location must be external.")
        if runner.get("co_located_with_api") is not False:
            failures.append("runner must not be co-located with the API.")
        if not str(runner.get("runner_id", "")).strip():
            failures.append("runner.runner_id is required.")

    database = context.get("database")
    if not isinstance(database, dict):
        failures.append("database metadata is required.")
    else:
        if database.get("application_role") != "rotas_app":
            failures.append("database.application_role must be rotas_app.")
        if database.get("pg_stat_statements_enabled") is not True:
            failures.append("pg_stat_statements must be enabled.")

    tenants = context.get("tenants")
    tenant_ids: set[UUID] = set()
    tenant_by_alias: dict[str, UUID] = {}
    token_envs: set[str] = set()
    aliases: set[str] = set()
    if not isinstance(tenants, list) or len(tenants) != 2:
        failures.append("Exactly two tenant contexts are required.")
        tenants = []
    for tenant in tenants:
        if not isinstance(tenant, dict):
            failures.append("Each tenant context must be an object.")
            continue
        try:
            tenant_id = UUID(str(tenant.get("tenant_id", "")))
            tenant_ids.add(tenant_id)
        except ValueError:
            failures.append("Each tenant_id must be a UUID.")
            tenant_id = UUID(int=0)
        alias = str(tenant.get("alias", ""))
        if alias not in {"tenant_a", "tenant_b"}:
            failures.append("Tenant aliases must be tenant_a and tenant_b.")
        aliases.add(alias)
        tenant_by_alias[alias] = tenant_id
        token_name = str(tenant.get("token_env", ""))
        if not TOKEN_ENV.fullmatch(token_name):
            failures.append("Tenant token_env must use the approved A/B variable names.")
        token_envs.add(token_name)
        if require_token_env and not os.environ.get(token_name):
            failures.append(f"Required ephemeral token environment is missing: {token_name}")
    if len(tenant_ids) != 2:
        failures.append("Tenant IDs must be distinct.")
    if aliases != {"tenant_a", "tenant_b"}:
        failures.append("Both canonical tenant aliases are required.")
    if len(token_envs) != 2:
        failures.append("Tenant token environments must be distinct.")

    scenarios = context.get("scenarios")
    scenario_set = set(scenarios) if isinstance(scenarios, list) else set()
    if scenario_set != REQUIRED_SCENARIOS or (
        isinstance(scenarios, list) and len(scenarios) != len(REQUIRED_SCENARIOS)
    ):
        failures.append("All four canonical scenarios are required exactly once.")
    if int(context.get("soak_seconds", 0) or 0) < 7200:
        failures.append("soak_seconds must be at least 7200.")

    pg_stat_path = context.get("pg_stat_report")
    pg_stat_entries = 0
    if not isinstance(pg_stat_path, str) or not pg_stat_path:
        failures.append("pg_stat_report path is required.")
    else:
        try:
            pg_stat_report = _read_json_evidence(
                pg_stat_path,
                field="pg_stat_report",
                base_dir=base_dir or Path.cwd(),
            )
            pg_stat_entries = validate_pg_stat_report(pg_stat_report)
        except PerformanceCertificationError as exc:
            failures.append(f"Invalid pg_stat_report: {exc}")

    report_count = 0
    reports = context.get("reports")
    if not isinstance(reports, dict):
        failures.append("reports mapping is required.")
    else:
        for alias in ("tenant_a", "tenant_b"):
            tenant_reports = reports.get(alias)
            if not isinstance(tenant_reports, dict) or set(tenant_reports) != REQUIRED_SCENARIOS:
                failures.append(f"{alias} must map all four canonical reports.")
                continue
            tenant_id = tenant_by_alias.get(alias, UUID(int=0))
            for scenario in sorted(REQUIRED_SCENARIOS):
                try:
                    fragment = _read_json_evidence(
                        tenant_reports[scenario],
                        field=f"reports.{alias}.{scenario}",
                        base_dir=base_dir or Path.cwd(),
                    )
                    validate_performance_fragment(
                        fragment,
                        scenario=scenario,
                        tenant_id=tenant_id,
                        base_url=str(context.get("base_url", "")),
                        release_sha=str(context.get("release_sha", "")),
                    )
                    report_count += 1
                except PerformanceCertificationError as exc:
                    failures.append(f"Invalid {alias}/{scenario} fragment: {exc}")

    soak_duration = 0
    try:
        soak_report = _read_json_evidence(
            context.get("soak_report"),
            field="soak_report",
            base_dir=base_dir or Path.cwd(),
        )
        soak_duration = validate_soak_report(
            soak_report,
            release_sha=str(context.get("release_sha", "")),
        )
    except PerformanceCertificationError as exc:
        failures.append(f"Invalid soak_report: {exc}")

    if failures:
        raise PerformanceCertificationError("; ".join(failures))
    return {
        "tenants": len(tenant_ids),
        "scenarios": len(REQUIRED_SCENARIOS),
        "soak_seconds": int(context["soak_seconds"]),
        "pg_stat_entries": pg_stat_entries,
        "performance_fragments": report_count,
        "observed_soak_seconds": soak_duration,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--require-token-env", action="store_true")
    args = parser.parse_args()
    try:
        context = json.loads(args.context.read_text(encoding="utf-8"))
        result = validate_certification_context(
            context,
            require_token_env=args.require_token_env,
            base_dir=args.context.resolve().parent,
        )
    except (
        OSError,
        json.JSONDecodeError,
        PerformanceCertificationError,
    ) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 1
    print(
        json.dumps(
            {
                "status": "ok",
                "evidence_class": "release_evidence_context",
                **result,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
