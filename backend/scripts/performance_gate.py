"""PR-22 HTTP performance gate with secret-safe, machine-readable evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx


class PerformanceGateError(ValueError):
    pass


@dataclass(frozen=True)
class Sample:
    status_code: int | None
    http_ms: float
    end_to_end_ms: float
    error: str | None = None
    domain_failures: int = 0
    server_ids: tuple[str, ...] = ()
    server_timings: tuple[tuple[str, float], ...] = ()


_POOL_METRIC_RE = re.compile(
    r'^rotas_db_pool_(?P<metric>connections|capacity)'
    r'\{(?P<labels>[^}]*)\}\s+(?P<value>-?(?:\d+(?:\.\d*)?|\.\d+))$'
)
_POOL_LABEL_RE = re.compile(r'(?P<name>pool|state|limit)="(?P<value>[^"]+)"')
_RUNTIME_METRIC_RE = re.compile(
    r"^(?P<name>rotas_event_loop_lag_seconds|"
    r"rotas_process_cpu_utilization_ratio)"
    r"\s+(?P<value>-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$"
)
_RELEASE_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def parse_pool_metrics(payload: str) -> dict[str, dict[str, float]]:
    """Parse only the fixed-label pool gauges emitted by ROTAS."""
    parsed: dict[str, dict[str, float]] = {}
    for line in payload.splitlines():
        match = _POOL_METRIC_RE.match(line.strip())
        if match is None:
            continue
        labels = {
            item.group("name"): item.group("value")
            for item in _POOL_LABEL_RE.finditer(match.group("labels"))
        }
        pool_name = labels.get("pool")
        dimension = labels.get("state") or labels.get("limit")
        if pool_name not in {"application", "administrative", "shared"} or not dimension:
            continue
        parsed.setdefault(pool_name, {})[dimension] = float(match.group("value"))
    return parsed


def parse_runtime_metrics(payload: str) -> dict[str, float]:
    """Parse only the two fixed, label-free worker runtime gauges."""
    parsed: dict[str, float] = {}
    for line in payload.splitlines():
        match = _RUNTIME_METRIC_RE.match(line.strip())
        if match is not None:
            parsed[match.group("name")] = float(match.group("value"))
    return parsed


async def sample_pool_metrics(
    metrics_url: str,
    *,
    stop: asyncio.Event,
    observations: list[dict[str, dict[str, float]]],
    runtime_observations: list[dict[str, float]],
    errors: Counter[str],
    interval_seconds: float = 0.1,
) -> None:
    """Sample process-visible pool occupancy while the scenario is running."""
    async with httpx.AsyncClient(timeout=2) as client:
        while not stop.is_set():
            try:
                response = await client.get(metrics_url)
                response.raise_for_status()
                observations.append(parse_pool_metrics(response.text))
                runtime_observations.append(parse_runtime_metrics(response.text))
            except httpx.HTTPError as exc:
                errors[type(exc).__name__] += 1
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


def summarize_pool_observations(
    observations: list[dict[str, dict[str, float]]],
    errors: Counter[str],
) -> dict[str, Any]:
    pools = sorted({pool for observation in observations for pool in observation})
    summary: dict[str, Any] = {}
    for pool in pools:
        values = [item[pool] for item in observations if pool in item]
        checked_out = [item["checked_out"] for item in values if "checked_out" in item]
        capacities = [
            item["max_connections"] for item in values if "max_connections" in item
        ]
        max_checked_out = max(checked_out, default=0)
        max_capacity = max(capacities, default=0)
        summary[pool] = {
            "observed_max_checked_out": max_checked_out,
            "configured_max_connections": max_capacity,
            "observed_max_utilization": round(
                max_checked_out / max_capacity if max_capacity else 0,
                6,
            ),
        }
    return {
        "collection": "http_scrape_process_visible",
        "scrapes": len(observations),
        "scrape_errors": dict(sorted(errors.items())),
        "pools": summary,
    }


def summarize_runtime_observations(
    observations: list[dict[str, float]],
) -> dict[str, Any]:
    """Summarize max and p95 without worker, host or tenant labels."""
    metric_names = (
        "rotas_event_loop_lag_seconds",
        "rotas_process_cpu_utilization_ratio",
    )
    summary: dict[str, Any] = {}
    for metric_name in metric_names:
        values = [
            observation[metric_name]
            for observation in observations
            if metric_name in observation
        ]
        summary[metric_name] = {
            "samples": len(values),
            "p95": round(percentile(values, 95), 6),
            "max": round(max(values), 6) if values else 0,
        }
    return {
        "collection": "http_scrape_multiprocess_aggregated",
        "scrapes": len(observations),
        "metrics": summary,
    }


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    if not 0 <= percentile_value <= 100:
        raise PerformanceGateError("Percentile must be between 0 and 100.")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile_value / 100 * len(ordered)))
    return ordered[rank - 1]


def load_policy(path: Path) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PerformanceGateError(f"Cannot read performance policy: {exc}") from exc
    if policy.get("policy_id") != "PR22-PERFORMANCE-V1":
        raise PerformanceGateError("Unsupported performance policy.")
    return policy


def validate_staging_fragment_inputs(
    *,
    profile_scenario: dict[str, Any],
    requests: int,
    base_url: str,
    metrics_url: str | None,
) -> str:
    release_sha = os.environ.get("ROTAS_RELEASE_SHA", "")
    if not _RELEASE_SHA_RE.fullmatch(release_sha):
        raise PerformanceGateError(
            "ROTAS_RELEASE_SHA must be the full lowercase RC SHA in staging."
        )
    minimum_requests = int(profile_scenario.get("minimum_requests", 0))
    if not minimum_requests or requests < minimum_requests:
        raise PerformanceGateError(
            f"Staging scenario requires at least {minimum_requests} requests."
        )
    for value, label in (
        (base_url, "base URL"),
        (metrics_url, "metrics URL"),
    ):
        parsed = urlsplit(value or "")
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.hostname in {"localhost", "127.0.0.1"}
            or parsed.hostname.endswith(".example.invalid")
        ):
            raise PerformanceGateError(
                f"Staging {label} must be a real non-local HTTPS URL."
            )
    return release_sha


def render_payload(template: dict[str, Any], request_id: int) -> dict[str, Any]:
    encoded = json.dumps(template)
    return json.loads(encoded.replace("{{request_id}}", str(request_id)))


def _token() -> str:
    token = os.environ.get("ROTAS_PERF_TOKEN", "")
    if not token:
        raise PerformanceGateError("ROTAS_PERF_TOKEN is required.")
    return token


def _headers(tenant_id: UUID) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "X-Tenant-Id": str(tenant_id),
        "User-Agent": "rotas-pr22-performance-gate/1",
    }


def _domain_observations(response: httpx.Response) -> tuple[int, tuple[str, ...]]:
    try:
        body = response.json()
    except ValueError:
        return 0, ()
    if not isinstance(body, dict) or not isinstance(body.get("results"), list):
        return 0, ()
    failures = 0
    server_ids: list[str] = []
    for result in body["results"]:
        if not isinstance(result, dict):
            failures += 1
            continue
        if result.get("status") != "processed":
            failures += 1
        if result.get("server_id"):
            server_ids.append(str(result["server_id"]))
    return failures, tuple(server_ids)


def parse_server_timing(value: str | None) -> tuple[tuple[str, float], ...]:
    if not value:
        return ()
    parsed: list[tuple[str, float]] = []
    for entry in value.split(","):
        parts = [part.strip() for part in entry.split(";")]
        if len(parts) != 2 or not parts[1].startswith("dur="):
            continue
        try:
            duration = float(parts[1][4:])
        except ValueError:
            continue
        parsed.append((parts[0], duration))
    return tuple(parsed)


async def _one_request(
    client: httpx.AsyncClient,
    *,
    method: str,
    path: str,
    headers: dict[str, str],
    expected_statuses: set[int],
    payload_template: dict[str, Any] | None,
    request_id: int,
    latency_ms: int = 0,
    jitter_ms: int = 0,
    loss_rate: float = 0,
    rng: random.Random | None = None,
) -> Sample:
    started = time.perf_counter()
    if latency_ms or jitter_ms:
        jitter = (rng or random).uniform(-jitter_ms, jitter_ms)
        await asyncio.sleep(max(0, latency_ms + jitter) / 1000)
    if loss_rate and (rng or random).random() < loss_rate:
        return Sample(
            status_code=None,
            http_ms=0,
            end_to_end_ms=(time.perf_counter() - started) * 1000,
            error="simulated_network_drop",
        )

    http_started = time.perf_counter()
    try:
        response = await client.request(
            method,
            path,
            headers=headers,
            json=(
                render_payload(payload_template, request_id)
                if payload_template is not None
                else None
            ),
        )
        http_ms = (time.perf_counter() - http_started) * 1000
        domain_failures, server_ids = _domain_observations(response)
        error = None
        if response.status_code not in expected_statuses:
            error = f"unexpected_status:{response.status_code}"
        return Sample(
            status_code=response.status_code,
            http_ms=http_ms,
            end_to_end_ms=(time.perf_counter() - started) * 1000,
            error=error,
            domain_failures=domain_failures,
            server_ids=server_ids,
            server_timings=parse_server_timing(
                response.headers.get("server-timing")
            ),
        )
    except httpx.HTTPError as exc:
        return Sample(
            status_code=None,
            http_ms=(time.perf_counter() - http_started) * 1000,
            end_to_end_ms=(time.perf_counter() - started) * 1000,
            error=type(exc).__name__,
        )


async def execute_scenario(
    *,
    base_url: str,
    tenant_id: UUID,
    budget: dict[str, Any],
    requests: int,
    concurrency: int,
    payload_template: dict[str, Any] | None = None,
    timeout_seconds: float = 10,
    seed: int = 2207,
    metrics_url: str | None = None,
    metrics_interval_seconds: float = 0.1,
    pool_observations: list[dict[str, dict[str, float]]] | None = None,
    runtime_observations: list[dict[str, float]] | None = None,
    pool_scrape_errors: Counter[str] | None = None,
) -> list[Sample]:
    if requests < 1 or concurrency < 1:
        raise PerformanceGateError("Requests and concurrency must be positive.")
    if metrics_interval_seconds <= 0:
        raise PerformanceGateError("Metrics interval must be positive.")
    semaphore = asyncio.Semaphore(concurrency)
    headers = _headers(tenant_id)
    rng = random.Random(seed)

    stop_sampling = asyncio.Event()
    observations = pool_observations if pool_observations is not None else []
    runtime_samples = (
        runtime_observations if runtime_observations is not None else []
    )
    scrape_errors = pool_scrape_errors if pool_scrape_errors is not None else Counter()
    sampler = (
        asyncio.create_task(
            sample_pool_metrics(
                metrics_url,
                stop=stop_sampling,
                observations=observations,
                runtime_observations=runtime_samples,
                errors=scrape_errors,
                interval_seconds=metrics_interval_seconds,
            )
        )
        if metrics_url
        else None
    )
    async with httpx.AsyncClient(
        base_url=base_url.rstrip("/"),
        timeout=timeout_seconds,
        limits=httpx.Limits(
            max_connections=concurrency,
            max_keepalive_connections=concurrency,
        ),
    ) as client:

        async def bounded(index: int) -> Sample:
            async with semaphore:
                return await _one_request(
                    client,
                    method=str(budget["method"]),
                    path=str(budget["path"]),
                    headers=headers,
                    expected_statuses=set(budget["expected_statuses"]),
                    payload_template=payload_template,
                    request_id=index,
                    latency_ms=int(budget.get("latency_ms", 0)),
                    jitter_ms=int(budget.get("jitter_ms", 0)),
                    loss_rate=float(budget.get("simulated_loss_rate", 0)),
                    rng=rng,
                )

        try:
            return await asyncio.gather(*(bounded(index) for index in range(requests)))
        finally:
            stop_sampling.set()
            if sampler is not None:
                await sampler


def evaluate(
    scenario: str,
    budget: dict[str, Any],
    samples: list[Sample],
) -> dict[str, Any]:
    total = len(samples)
    simulated_drops = sum(sample.error == "simulated_network_drop" for sample in samples)
    unexpected_errors = sum(
        sample.error is not None and sample.error != "simulated_network_drop"
        for sample in samples
    )
    delivered = [sample for sample in samples if sample.error != "simulated_network_drop"]
    http_values = [sample.http_ms for sample in delivered]
    end_to_end_values = [sample.end_to_end_ms for sample in samples]
    domain_failures = sum(sample.domain_failures for sample in samples)
    domain_results = sum(
        sample.domain_failures + len(sample.server_ids) for sample in samples
    )
    distinct_server_ids = sorted(
        {server_id for sample in samples for server_id in sample.server_ids}
    )
    phase_values: dict[str, list[float]] = {}
    for sample in samples:
        for phase, duration in sample.server_timings:
            phase_values.setdefault(phase, []).append(duration)
    metrics = {
        "requests": total,
        "delivered_requests": len(delivered),
        "status_codes": dict(
            sorted(
                Counter(
                    str(sample.status_code)
                    for sample in samples
                    if sample.status_code is not None
                ).items()
            )
        ),
        "http_ms": {
            "mean": round(statistics.fmean(http_values), 3) if http_values else 0,
            "p50": round(percentile(http_values, 50), 3),
            "p95": round(percentile(http_values, 95), 3),
            "p99": round(percentile(http_values, 99), 3),
            "max": round(max(http_values), 3) if http_values else 0,
        },
        "end_to_end_ms": {
            "p95": round(percentile(end_to_end_values, 95), 3),
            "max": round(max(end_to_end_values), 3) if end_to_end_values else 0,
        },
        "unexpected_error_rate": round(unexpected_errors / total, 6),
        "error_types": dict(
            sorted(
                Counter(
                    sample.error
                    for sample in samples
                    if sample.error is not None
                    and sample.error != "simulated_network_drop"
                ).items()
            )
        ),
        "simulated_drop_rate": round(simulated_drops / total, 6),
        "domain_failure_rate": round(
            domain_failures / domain_results if domain_results else 0,
            6,
        ),
        "distinct_server_ids": len(distinct_server_ids),
        "server_timing_ms": {
            phase: {
                "samples": len(values),
                "p50": round(percentile(values, 50), 3),
                "p95": round(percentile(values, 95), 3),
                "max": round(max(values), 3),
            }
            for phase, values in sorted(phase_values.items())
        },
    }
    checks: dict[str, bool] = {
        "p95_http": metrics["http_ms"]["p95"] <= float(budget["p95_http_ms"]),
        "unexpected_error_rate": metrics["unexpected_error_rate"]
        <= float(
            budget.get(
                "max_unexpected_error_rate",
                budget.get("max_error_rate", 0),
            )
        ),
    }
    if "p99_http_ms" in budget:
        checks["p99_http"] = metrics["http_ms"]["p99"] <= float(
            budget["p99_http_ms"]
        )
    if "p95_end_to_end_ms" in budget:
        checks["p95_end_to_end"] = metrics["end_to_end_ms"]["p95"] <= float(
            budget["p95_end_to_end_ms"]
        )
    if "max_domain_failure_rate" in budget:
        checks["domain_failure_rate"] = metrics["domain_failure_rate"] <= float(
            budget["max_domain_failure_rate"]
        )
    if "simulated_loss_rate" in budget:
        checks["delivery_loss_delta"] = abs(
            metrics["simulated_drop_rate"] - float(budget["simulated_loss_rate"])
        ) <= float(budget["max_delivery_loss_delta"])
    if scenario == "idempotency_race":
        checks["single_business_effect"] = metrics["distinct_server_ids"] <= int(
            budget["max_distinct_server_ids"]
        )
        checks["server_id_observed"] = metrics["distinct_server_ids"] == 1
        checks["conflicts"] = domain_failures <= int(budget["max_conflicts"])
    return {"metrics": metrics, "checks": checks, "passed": all(checks.values())}


def build_report(
    *,
    scenario: str,
    profile: str,
    base_url: str,
    tenant_id: UUID,
    concurrency: int,
    elapsed_seconds: float,
    evaluation: dict[str, Any],
    release_sha: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "policy_id": "PR22-PERFORMANCE-V1",
        "generated_at": datetime.now(UTC).isoformat(),
        "evidence_class": (
            "engineering_evidence_only"
            if profile == "local_drill"
            else "release_evidence_fragment"
        ),
        "scenario": scenario,
        "profile": profile,
        "release_sha": release_sha,
        "target": {
            "base_url": base_url,
            "tenant_id": str(tenant_id),
            "authorization": "redacted",
        },
        "concurrency": concurrency,
        "elapsed_seconds": round(elapsed_seconds, 3),
        **evaluation,
    }


def _payload(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PerformanceGateError(f"Cannot read payload template: {exc}") from exc
    if not isinstance(value, dict):
        raise PerformanceGateError("Payload template must be a JSON object.")
    return value


async def _async_main(args: argparse.Namespace) -> int:
    policy = load_policy(args.policy)
    budgets = policy["budgets"]
    if args.scenario not in budgets:
        raise PerformanceGateError(f"Unknown scenario: {args.scenario}")
    budget = budgets[args.scenario]
    profile = policy["profiles"][args.profile]
    profile_scenario = profile.get(args.scenario, {})
    requests = args.requests or profile_scenario.get("requests")
    concurrency = args.concurrency or profile_scenario.get(
        "concurrency",
        budget.get("concurrency"),
    )
    if not requests:
        raise PerformanceGateError(
            "This profile requires an explicit --requests value for bounded execution."
        )
    if not concurrency:
        raise PerformanceGateError("Scenario concurrency is not configured.")
    release_sha: str | None = None
    if args.profile == "staging_certification":
        release_sha = validate_staging_fragment_inputs(
            profile_scenario=profile_scenario,
            requests=int(requests),
            base_url=args.base_url,
            metrics_url=args.metrics_url,
        )
    payload = _payload(args.payload)
    if budget["method"] != "GET" and payload is None:
        raise PerformanceGateError("Mutating scenarios require --payload.")

    started = time.perf_counter()
    pool_observations: list[dict[str, dict[str, float]]] = []
    runtime_observations: list[dict[str, float]] = []
    pool_scrape_errors: Counter[str] = Counter()
    samples = await execute_scenario(
        base_url=args.base_url,
        tenant_id=args.tenant_id,
        budget=budget,
        requests=int(requests),
        concurrency=int(concurrency),
        payload_template=payload,
        timeout_seconds=args.timeout,
        seed=args.seed,
        metrics_url=args.metrics_url,
        metrics_interval_seconds=args.metrics_interval,
        pool_observations=pool_observations,
        runtime_observations=runtime_observations,
        pool_scrape_errors=pool_scrape_errors,
    )
    evaluation = evaluate(args.scenario, budget, samples)
    if args.metrics_url:
        evaluation["metrics"]["database_pool_observation"] = (
            summarize_pool_observations(pool_observations, pool_scrape_errors)
        )
        evaluation["metrics"]["worker_runtime_observation"] = (
            summarize_runtime_observations(runtime_observations)
        )
    report = build_report(
        scenario=args.scenario,
        profile=args.profile,
        base_url=args.base_url,
        tenant_id=args.tenant_id,
        concurrency=int(concurrency),
        elapsed_seconds=time.perf_counter() - started,
        evaluation=evaluation,
        release_sha=release_sha,
    )
    output = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(__file__).resolve().parents[2]
        / "infra"
        / "performance"
        / "PERFORMANCE_BUDGETS.json",
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument(
        "--scenario",
        choices=(
            "api_read",
            "offline_sync_batch",
            "idempotency_race",
            "degraded_network",
        ),
        required=True,
    )
    parser.add_argument(
        "--profile",
        choices=("local_drill", "staging_certification"),
        required=True,
    )
    parser.add_argument("--requests", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument(
        "--metrics-url",
        help=(
            "Optional Prometheus endpoint sampled during the run. In a multi-worker "
            "deployment this is process-visible unless the runtime aggregates metrics."
        ),
    )
    parser.add_argument(
        "--metrics-interval",
        type=float,
        default=0.1,
        help="Seconds between optional Prometheus scrapes during the run.",
    )
    parser.add_argument("--seed", type=int, default=2207)
    args = parser.parse_args()
    try:
        return asyncio.run(_async_main(args))
    except PerformanceGateError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
