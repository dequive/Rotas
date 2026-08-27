import json
from collections import Counter
from pathlib import Path
from uuid import UUID

import pytest

from scripts.performance_gate import (
    PerformanceGateError,
    Sample,
    build_report,
    evaluate,
    execute_scenario,
    parse_pool_metrics,
    parse_runtime_metrics,
    parse_server_timing,
    percentile,
    render_payload,
    summarize_pool_observations,
    summarize_runtime_observations,
    validate_staging_fragment_inputs,
)
from scripts.validate_performance_policy import validate_performance_policy

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_percentile_uses_nearest_rank_and_rejects_invalid_percentile():
    assert percentile([1, 2, 3, 4, 100], 95) == 100
    assert percentile([], 95) == 0
    with pytest.raises(PerformanceGateError):
        percentile([1], 101)


@pytest.mark.asyncio
async def test_metrics_sampling_interval_must_be_positive():
    with pytest.raises(PerformanceGateError, match="Metrics interval"):
        await execute_scenario(
            base_url="http://localhost",
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            budget={"method": "GET", "path": "/", "expected_statuses": [200]},
            requests=1,
            concurrency=1,
            metrics_interval_seconds=0,
        )


def test_payload_template_generates_unique_request_identity():
    template = {
        "device_id": "pr22",
        "operations": [
            {
                "local_id": "local-{{request_id}}",
                "idempotency_key": "idem-{{request_id}}",
            }
        ],
    }
    rendered = render_payload(template, 17)
    assert rendered["operations"][0]["local_id"] == "local-17"
    assert rendered["operations"][0]["idempotency_key"] == "idem-17"


def test_server_timing_parser_is_bounded_and_ignores_invalid_entries():
    assert parse_server_timing(
        "admin_sql;dur=1.250, auth_identity;dur=2.500, invalid, app_sql;dur=x"
    ) == (
        ("admin_sql", 1.25),
        ("auth_identity", 2.5),
    )


def test_pool_metric_parser_and_summary_are_fixed_label_and_bounded():
    first = parse_pool_metrics(
        '\n'.join(
            [
                'rotas_db_pool_connections{pool="application",state="checked_out"} 3',
                'rotas_db_pool_capacity{limit="max_connections",pool="application"} 15',
                'rotas_db_pool_connections{pool="unknown",state="checked_out"} 99',
                'unrelated_metric{tenant_id="secret"} 1',
            ]
        )
    )
    second = {
        "application": {
            "checked_out": 6.0,
            "max_connections": 15.0,
        }
    }
    assert first == {
        "application": {
            "checked_out": 3,
            "max_connections": 15,
        }
    }
    assert summarize_pool_observations([first, second], Counter()) == {
        "collection": "http_scrape_process_visible",
        "scrapes": 2,
        "scrape_errors": {},
        "pools": {
            "application": {
                "observed_max_checked_out": 6,
                "configured_max_connections": 15,
                "observed_max_utilization": 0.4,
            }
        },
    }


def test_runtime_metric_parser_and_summary_are_fixed_and_bounded():
    payload = "\n".join(
        [
            "rotas_event_loop_lag_seconds 0.025",
            "rotas_process_cpu_utilization_ratio 1.5",
            'rotas_event_loop_lag_seconds{tenant_id="forbidden"} 99',
            "unrelated_metric 42",
        ]
    )
    parsed = parse_runtime_metrics(payload)
    assert parsed == {
        "rotas_event_loop_lag_seconds": 0.025,
        "rotas_process_cpu_utilization_ratio": 1.5,
    }
    assert summarize_runtime_observations(
        [
            parsed,
            {
                "rotas_event_loop_lag_seconds": 0.1,
                "rotas_process_cpu_utilization_ratio": 2.0,
            },
        ]
    ) == {
        "collection": "http_scrape_multiprocess_aggregated",
        "scrapes": 2,
        "metrics": {
            "rotas_event_loop_lag_seconds": {
                "samples": 2,
                "p95": 0.1,
                "max": 0.1,
            },
            "rotas_process_cpu_utilization_ratio": {
                "samples": 2,
                "p95": 2.0,
                "max": 2.0,
            },
        },
    }
def test_read_budget_passes_and_latency_regression_fails():
    budget = {
        "p95_http_ms": 200,
        "p99_http_ms": 500,
        "max_error_rate": 0.01,
    }
    passing = [Sample(200, 50, 50) for _ in range(100)]
    assert evaluate("api_read", budget, passing)["passed"] is True

    regressed = [Sample(200, 250, 250) for _ in range(100)]
    result = evaluate("api_read", budget, regressed)
    assert result["passed"] is False
    assert result["checks"]["p95_http"] is False

    timed_out = passing[:-1] + [
        Sample(None, 10_000, 10_000, error="ReadTimeout")
    ]
    assert evaluate("api_read", budget, timed_out)["metrics"]["error_types"] == {
        "ReadTimeout": 1
    }


def test_sync_budget_counts_domain_failures_separately_from_http_status():
    budget = {
        "p95_http_ms": 500,
        "max_error_rate": 0.01,
        "max_domain_failure_rate": 0,
    }
    samples = [
        Sample(200, 25, 25, domain_failures=1, server_ids=("one",)),
    ]
    result = evaluate("offline_sync_batch", budget, samples)
    assert result["metrics"]["unexpected_error_rate"] == 0
    assert result["metrics"]["domain_failure_rate"] == 0.5
    assert result["passed"] is False


def test_idempotency_race_requires_one_observed_business_effect():
    budget = {
        "p95_http_ms": 500,
        "max_error_rate": 0,
        "max_distinct_server_ids": 1,
        "max_conflicts": 0,
    }
    replayed = [
        Sample(200, 20, 20, server_ids=("server-one",)),
        Sample(200, 25, 25, server_ids=("server-one",)),
    ]
    assert evaluate("idempotency_race", budget, replayed)["passed"] is True

    duplicated = replayed + [Sample(200, 25, 25, server_ids=("server-two",))]
    assert evaluate("idempotency_race", budget, duplicated)["passed"] is False

    conflicted = replayed + [
        Sample(200, 25, 25, domain_failures=1, server_ids=("server-one",))
    ]
    assert evaluate("idempotency_race", budget, conflicted)["passed"] is False


def test_degraded_network_distinguishes_injected_loss_from_unexpected_errors():
    budget = {
        "p95_http_ms": 200,
        "p95_end_to_end_ms": 600,
        "max_unexpected_error_rate": 0,
        "simulated_loss_rate": 0.02,
        "max_delivery_loss_delta": 0.03,
    }
    samples = [Sample(200, 50, 300) for _ in range(98)]
    samples.extend(
        [
            Sample(None, 0, 250, error="simulated_network_drop"),
            Sample(None, 0, 250, error="simulated_network_drop"),
        ]
    )
    result = evaluate("degraded_network", budget, samples)
    assert result["metrics"]["simulated_drop_rate"] == 0.02
    assert result["metrics"]["unexpected_error_rate"] == 0
    assert result["passed"] is True


def test_report_redacts_authorization_secret():
    report = build_report(
        scenario="api_read",
        profile="local_drill",
        base_url="http://localhost:8000",
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        concurrency=4,
        elapsed_seconds=1,
        evaluation={"metrics": {}, "checks": {}, "passed": True},
    )
    encoded = json.dumps(report)
    assert report["target"]["authorization"] == "redacted"
    assert "Bearer" not in encoded
    assert report["evidence_class"] == "engineering_evidence_only"

    staging_report = build_report(
        scenario="api_read",
        profile="staging_certification",
        base_url="https://api.staging.rotas.co.mz",
        tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
        concurrency=50,
        elapsed_seconds=1800,
        evaluation={"metrics": {}, "checks": {}, "passed": True},
        release_sha="0123456789abcdef0123456789abcdef01234567",
    )
    assert staging_report["evidence_class"] == "release_evidence_fragment"
    assert (
        staging_report["release_sha"]
        == "0123456789abcdef0123456789abcdef01234567"
    )


def test_staging_fragment_requires_rc_sha_minimum_volume_and_external_metrics(
    monkeypatch,
):
    monkeypatch.setenv(
        "ROTAS_RELEASE_SHA",
        "0123456789abcdef0123456789abcdef01234567",
    )
    assert (
        validate_staging_fragment_inputs(
            profile_scenario={"minimum_requests": 10_000},
            requests=10_000,
            base_url="https://api.staging.rotas.co.mz",
            metrics_url="https://metrics.staging.rotas.co.mz/metrics",
        )
        == "0123456789abcdef0123456789abcdef01234567"
    )

    with pytest.raises(PerformanceGateError, match="at least 10000"):
        validate_staging_fragment_inputs(
            profile_scenario={"minimum_requests": 10_000},
            requests=9_999,
            base_url="https://api.staging.rotas.co.mz",
            metrics_url="https://metrics.staging.rotas.co.mz/metrics",
        )
    with pytest.raises(PerformanceGateError, match="metrics URL"):
        validate_staging_fragment_inputs(
            profile_scenario={"minimum_requests": 10_000},
            requests=10_000,
            base_url="https://api.staging.rotas.co.mz",
            metrics_url=None,
        )


def test_performance_policy_is_versioned_and_fail_closed():
    assert validate_performance_policy(REPO_ROOT) == {
        "budgets": 4,
        "release_invariants": 5,
        "staging_soak_seconds": 7200,
        "certification_controls": 4,
        "certification_artifacts": 2,
    }
