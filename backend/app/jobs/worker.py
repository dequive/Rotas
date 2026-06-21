"""Shim — consolidated into app.worker.

All tasks and crons have been merged into ``app.worker.WorkerSettings``.
Existing Railway services using ``arq app.jobs.worker.WorkerSettings`` continue to work.

Preferred start command: arq app.worker.WorkerSettings
"""

from app.worker import WorkerSettings as WorkerSettings  # noqa: F401
