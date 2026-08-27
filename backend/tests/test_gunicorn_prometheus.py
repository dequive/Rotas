import multiprocessing
import os
from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry, Gauge, generate_latest, multiprocess

from app.gunicorn_conf import prepare_prometheus_multiprocess_directory


def _write_live_gauge(value: float) -> None:
    Gauge(
        "rotas_test_multiprocess_pool_capacity",
        "Test-only multiprocess capacity.",
        multiprocess_mode="livesum",
    ).set(value)


def test_multiprocess_directory_is_temp_scoped_and_stale_metrics_are_removed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    target = tmp_path / "rotas-prometheus"
    target.mkdir()
    stale = target / "gauge_livesum_123.db"
    stale.write_text("stale", encoding="utf-8")
    unrelated = target / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    monkeypatch.setattr("app.gunicorn_conf.tempfile.gettempdir", lambda: str(tmp_path))
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(target))

    assert prepare_prometheus_multiprocess_directory() == target.resolve()
    assert os.environ["PROMETHEUS_MULTIPROC_DIR"] == str(target.resolve())
    assert not stale.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_multiprocess_directory_rejects_path_outside_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    temp_root = tmp_path / "temp"
    outside = tmp_path / "outside"
    monkeypatch.setattr("app.gunicorn_conf.tempfile.gettempdir", lambda: str(temp_root))
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(outside))

    with pytest.raises(RuntimeError, match="must resolve inside"):
        prepare_prometheus_multiprocess_directory()


def test_live_gauges_are_summed_across_spawned_processes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    target = tmp_path / "rotas-prometheus"
    target.mkdir()
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(target))
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(target=_write_live_gauge, args=(value,))
        for value in (2.0, 3.0)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    registry = CollectorRegistry()
    multiprocess.MultiProcessCollector(registry, path=str(target))
    payload = generate_latest(registry).decode()
    assert "rotas_test_multiprocess_pool_capacity 5.0" in payload
