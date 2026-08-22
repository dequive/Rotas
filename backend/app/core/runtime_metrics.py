"""Low-cardinality worker runtime telemetry for performance diagnosis."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from time import monotonic, process_time

from prometheus_client import Gauge

_EVENT_LOOP_LAG = Gauge(
    "rotas_event_loop_lag_seconds",
    "Maximum event-loop scheduling delay across live API workers.",
    multiprocess_mode="livemax",
)
_PROCESS_CPU_UTILIZATION = Gauge(
    "rotas_process_cpu_utilization_ratio",
    "Sum of API worker CPU utilisation as core-equivalent ratio.",
    multiprocess_mode="livesum",
)


def calculate_runtime_sample(
    *,
    deadline: float,
    previous_wall: float,
    current_wall: float,
    previous_cpu: float,
    current_cpu: float,
) -> tuple[float, float]:
    """Return non-negative event-loop lag and process CPU/core ratio."""
    wall_delta = max(0.0, current_wall - previous_wall)
    cpu_delta = max(0.0, current_cpu - previous_cpu)
    lag_seconds = max(0.0, current_wall - deadline)
    cpu_ratio = cpu_delta / wall_delta if wall_delta else 0.0
    return lag_seconds, cpu_ratio


async def collect_runtime_metrics(interval_seconds: float = 0.5) -> None:
    """Continuously sample the current worker with bounded overhead."""
    if interval_seconds <= 0:
        raise ValueError("Runtime metrics interval must be positive.")

    previous_wall = monotonic()
    previous_cpu = process_time()
    while True:
        deadline = previous_wall + interval_seconds
        await asyncio.sleep(max(0.0, deadline - monotonic()))
        current_wall = monotonic()
        current_cpu = process_time()
        lag_seconds, cpu_ratio = calculate_runtime_sample(
            deadline=deadline,
            previous_wall=previous_wall,
            current_wall=current_wall,
            previous_cpu=previous_cpu,
            current_cpu=current_cpu,
        )
        _EVENT_LOOP_LAG.set(lag_seconds)
        _PROCESS_CPU_UTILIZATION.set(cpu_ratio)
        previous_wall = current_wall
        previous_cpu = current_cpu


def start_runtime_metrics_sampler() -> asyncio.Task[None]:
    return asyncio.create_task(
        collect_runtime_metrics(),
        name="rotas-runtime-metrics",
    )


async def stop_runtime_metrics_sampler(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
