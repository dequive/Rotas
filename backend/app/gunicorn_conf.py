"""Gunicorn hooks required for correct Prometheus multiprocess collection."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Protocol

_PROMETHEUS_ENV = "PROMETHEUS_MULTIPROC_DIR"
_METRIC_FILE_GLOB = "*.db"


class _Worker(Protocol):
    pid: int


def prepare_prometheus_multiprocess_directory() -> Path:
    """Create and clean a temp-scoped directory before Gunicorn forks workers."""
    temp_root = Path(tempfile.gettempdir()).resolve()
    configured = os.environ.get(_PROMETHEUS_ENV)
    target = (
        Path(configured).resolve()
        if configured
        else (temp_root / "rotas-prometheus").resolve()
    )
    if target != temp_root and temp_root not in target.parents:
        raise RuntimeError(
            f"{_PROMETHEUS_ENV} must resolve inside the operating system temp directory."
        )
    target.mkdir(parents=True, exist_ok=True)
    for metric_file in target.glob(_METRIC_FILE_GLOB):
        if metric_file.is_file():
            metric_file.unlink()
    os.environ[_PROMETHEUS_ENV] = str(target)
    return target


def on_starting(_server: object) -> None:
    """Run in the master before application modules are imported by workers."""
    prepare_prometheus_multiprocess_directory()


def child_exit(_server: object, worker: _Worker) -> None:
    """Remove live-gauge contribution after a worker exits."""
    # Import only after on_starting has set PROMETHEUS_MULTIPROC_DIR. Importing
    # prometheus_client at config-module load time freezes its ValueClass in
    # single-process mode before Gunicorn forks workers.
    from prometheus_client import multiprocess

    multiprocess.mark_process_dead(worker.pid)
