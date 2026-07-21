"""Stabilization/P0-F8: transactional outbox for the ROTAS -> Governance bridge."""

from .models import OutboxEvent
from .service import enqueue, drain_outbox, BackoffSchedule, DEFAULT_BACKOFFS_SECONDS

__all__ = [
    "OutboxEvent",
    "enqueue",
    "drain_outbox",
    "BackoffSchedule",
    "DEFAULT_BACKOFFS_SECONDS",
]