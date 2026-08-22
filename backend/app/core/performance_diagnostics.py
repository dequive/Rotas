"""Request-scoped performance diagnostics for bounded local investigations.

The feature is disabled by default and production configuration rejects it.
Only fixed low-cardinality phase names are accepted; no identifiers or SQL are
written to the response.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from time import perf_counter

ALLOWED_PHASES = frozenset(
    {
        "admin_sql",
        "app_sql",
        "auth_identity",
        "rls_context",
        "sync_commit",
        "sync_dispatch",
        "sync_flush",
        "sync_idempotency",
        "tenant_lookup",
    }
)

_request_timings: ContextVar[dict[str, float] | None] = ContextVar(
    "request_performance_timings",
    default=None,
)


def begin_request_timings() -> Token[dict[str, float] | None]:
    return _request_timings.set({})


def reset_request_timings(token: Token[dict[str, float] | None]) -> None:
    _request_timings.reset(token)


def observe_request_phase(phase: str, elapsed_seconds: float) -> None:
    timings = _request_timings.get()
    if timings is None:
        return
    if phase not in ALLOWED_PHASES:
        raise ValueError(f"Unsupported performance phase: {phase}")
    timings[phase] = timings.get(phase, 0.0) + max(0.0, elapsed_seconds)


@contextmanager
def measure_request_phase(phase: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        observe_request_phase(phase, perf_counter() - started)


def render_server_timing() -> str:
    timings = _request_timings.get() or {}
    return ", ".join(
        f"{phase};dur={seconds * 1000:.3f}"
        for phase, seconds in sorted(timings.items())
    )
