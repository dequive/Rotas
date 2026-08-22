import json
from pathlib import Path

import pytest

from scripts.export_pg_stat_statements import PG_STAT_SQL, build_report
from scripts.performance_certification import (
    PerformanceCertificationError,
    validate_certification_context,
    validate_pg_stat_report,
)

RELEASE_SHA = "0123456789abcdef0123456789abcdef01234567"
IMAGE = "registry.rotas.co.mz/backend@sha256:" + "a" * 64


def _pg_entry() -> dict[str, int | float]:
    return {
        "queryid": 123,
        "calls": 50,
        "total_exec_time_ms": 100.5,
        "mean_exec_time_ms": 2.01,
        "rows": 50,
        "shared_blks_hit": 200,
        "shared_blks_read": 2,
        "temp_blks_written": 0,
    }


def _write_pg_report(tmp_path: Path) -> Path:
    path = tmp_path / "pg-stat.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "extension": "pg_stat_statements",
                "query_text_included": False,
                "entries": [_pg_entry()],
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_fragment(
    tmp_path: Path,
    *,
    alias: str,
    tenant_id: str,
    scenario: str,
) -> str:
    minimum_requests = {
        "api_read": 10_000,
        "offline_sync_batch": 3_000,
        "idempotency_race": 20,
        "degraded_network": 5_000,
    }
    path = tmp_path / f"{alias}-{scenario}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "policy_id": "PR22-PERFORMANCE-V1",
                "profile": "staging_certification",
                "evidence_class": "release_evidence_fragment",
                "scenario": scenario,
                "release_sha": RELEASE_SHA,
                "passed": True,
                "checks": {"p95_http": True, "unexpected_error_rate": True},
                "target": {
                    "base_url": "https://api.staging.rotas.co.mz",
                    "tenant_id": tenant_id,
                    "authorization": "redacted",
                },
                "metrics": {
                    "delivered_requests": minimum_requests[scenario],
                    "unexpected_error_rate": 0,
                    "database_pool_observation": {"scrapes": 10},
                    "worker_runtime_observation": {
                        "metrics": {
                            "rotas_event_loop_lag_seconds": {"samples": 10},
                            "rotas_process_cpu_utilization_ratio": {"samples": 10},
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def _context(pg_stat_path: Path) -> dict:
    tmp_path = pg_stat_path.parent
    tenant_ids = {
        "tenant_a": "00000000-0000-0000-0000-000000000001",
        "tenant_b": "00000000-0000-0000-0000-000000000002",
    }
    scenarios = [
        "api_read",
        "offline_sync_batch",
        "idempotency_race",
        "degraded_network",
    ]
    reports = {
        alias: {
            scenario: _write_fragment(
                tmp_path,
                alias=alias,
                tenant_id=tenant_id,
                scenario=scenario,
            )
            for scenario in scenarios
        }
        for alias, tenant_id in tenant_ids.items()
    }
    soak_path = tmp_path / "soak.json"
    soak_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_sha": RELEASE_SHA,
                "duration_seconds": 7200,
                "observability_window_complete": True,
                "unresolved_sev1_sev2": 0,
                "completed": True,
            }
        ),
        encoding="utf-8",
    )
    return {
        "schema_version": 1,
        "policy_id": "PR22-PERFORMANCE-V1",
        "release_sha": RELEASE_SHA,
        "backend_image": IMAGE,
        "base_url": "https://api.staging.rotas.co.mz",
        "metrics_url": "https://metrics.staging.rotas.co.mz/metrics",
        "runner": {
            "location": "external",
            "runner_id": "load-runner-maputo-01",
            "co_located_with_api": False,
        },
        "database": {
            "application_role": "rotas_app",
            "pg_stat_statements_enabled": True,
        },
        "tenants": [
            {
                "alias": "tenant_a",
                "tenant_id": tenant_ids["tenant_a"],
                "token_env": "ROTAS_PERF_TENANT_A_TOKEN",
            },
            {
                "alias": "tenant_b",
                "tenant_id": tenant_ids["tenant_b"],
                "token_env": "ROTAS_PERF_TENANT_B_TOKEN",
            },
        ],
        "scenarios": scenarios,
        "soak_seconds": 7200,
        "pg_stat_report": str(pg_stat_path),
        "reports": reports,
        "soak_report": str(soak_path),
    }


def test_certification_context_requires_real_rc_two_tenants_and_pg_stats(tmp_path):
    context = _context(_write_pg_report(tmp_path))

    assert validate_certification_context(context) == {
        "tenants": 2,
        "scenarios": 4,
        "soak_seconds": 7200,
        "pg_stat_entries": 1,
        "performance_fragments": 8,
        "observed_soak_seconds": 7200,
    }


def test_certification_context_rejects_local_runner_duplicate_tenant_and_short_soak(
    tmp_path,
):
    context = _context(_write_pg_report(tmp_path))
    context["base_url"] = "http://localhost:8000"
    context["runner"]["location"] = "local"
    context["tenants"][1]["tenant_id"] = context["tenants"][0]["tenant_id"]
    context["soak_seconds"] = 60

    with pytest.raises(PerformanceCertificationError) as exc:
        validate_certification_context(context)

    message = str(exc.value)
    assert "non-local HTTPS" in message
    assert "runner.location must be external" in message
    assert "Tenant IDs must be distinct" in message
    assert "at least 7200" in message


def test_pg_stat_report_rejects_query_text_and_exporter_whitelists_fields():
    unsafe = {
        "schema_version": 1,
        "extension": "pg_stat_statements",
        "query_text_included": False,
        "entries": [{**_pg_entry(), "query": "SELECT secret FROM tenants"}],
    }
    with pytest.raises(PerformanceCertificationError, match="field set"):
        validate_pg_stat_report(unsafe)

    report = build_report(
        [{**_pg_entry(), "query": "SELECT secret FROM tenants"}],
        limit=100,
    )
    assert "query" not in report["entries"][0]
    assert " query," not in PG_STAT_SQL.lower()
    assert " query " not in PG_STAT_SQL.lower()
