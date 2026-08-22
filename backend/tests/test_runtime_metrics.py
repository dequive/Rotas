import asyncio

import pytest

from app.core.runtime_metrics import (
    calculate_runtime_sample,
    collect_runtime_metrics,
    start_runtime_metrics_sampler,
    stop_runtime_metrics_sampler,
)


def test_runtime_sample_calculates_lag_and_cpu_ratio_without_negative_values():
    assert calculate_runtime_sample(
        deadline=10.5,
        previous_wall=10.0,
        current_wall=10.6,
        previous_cpu=3.0,
        current_cpu=3.3,
    ) == pytest.approx((0.1, 0.5))
    assert calculate_runtime_sample(
        deadline=11.0,
        previous_wall=10.0,
        current_wall=10.5,
        previous_cpu=4.0,
        current_cpu=3.0,
    ) == (0.0, 0.0)


@pytest.mark.asyncio
async def test_runtime_sampler_rejects_invalid_interval_and_stops_cleanly():
    with pytest.raises(ValueError, match="interval"):
        await collect_runtime_metrics(0)

    task = start_runtime_metrics_sampler()
    await asyncio.sleep(0)
    await stop_runtime_metrics_sampler(task)
    assert task.cancelled()
