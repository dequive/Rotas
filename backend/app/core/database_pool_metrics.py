"""Low-cardinality Prometheus telemetry for SQLAlchemy connection pools."""

from __future__ import annotations

from prometheus_client import Counter, Gauge
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

_POOL_CONNECTIONS = Gauge(
    "rotas_db_pool_connections",
    "Current SQLAlchemy pool connections by fixed state.",
    ("pool", "state"),
    multiprocess_mode="livesum",
)
_POOL_CAPACITY = Gauge(
    "rotas_db_pool_capacity",
    "Configured SQLAlchemy pool limits.",
    ("pool", "limit"),
    multiprocess_mode="livesum",
)
_POOL_CHECKOUTS = Counter(
    "rotas_db_pool_checkouts",
    "SQLAlchemy connection checkouts.",
    ("pool",),
)
_POOL_INVALIDATIONS = Counter(
    "rotas_db_pool_invalidations",
    "SQLAlchemy connection invalidations.",
    ("pool",),
)
_INSTALLED_POOLS: set[int] = set()
_IDLE_MARKER = "rotas_pool_metrics_idle"


def install_database_pool_metrics(
    target_engine: AsyncEngine,
    *,
    pool_name: str,
    pool_size: int,
    max_overflow: int,
) -> None:
    """Expose pool occupancy without tenant, user, query or connection labels."""
    if pool_name not in {"application", "administrative", "shared"}:
        raise ValueError("Database pool name must use a fixed low-cardinality value.")

    pool = target_engine.sync_engine.pool
    pool_identity = id(pool)
    if pool_identity in _INSTALLED_POOLS:
        return
    _INSTALLED_POOLS.add(pool_identity)

    checked_out = _POOL_CONNECTIONS.labels(pool_name, "checked_out")
    checked_in = _POOL_CONNECTIONS.labels(pool_name, "checked_in")
    _POOL_CONNECTIONS.labels(pool_name, "base_size").set(pool_size)
    _POOL_CAPACITY.labels(pool_name, "pool_size").set(pool_size)
    _POOL_CAPACITY.labels(pool_name, "max_connections").set(
        pool_size + max_overflow
    )
    _POOL_CHECKOUTS.labels(pool_name).inc(0)
    _POOL_INVALIDATIONS.labels(pool_name).inc(0)

    @event.listens_for(pool, "checkout")
    def _record_checkout(
        _dbapi_connection: object,
        connection_record: object,
        _connection_proxy: object,
    ) -> None:
        record_info = getattr(connection_record, "info", {})
        if record_info.pop(_IDLE_MARKER, False):
            checked_in.dec()
        checked_out.inc()
        _POOL_CHECKOUTS.labels(pool_name).inc()

    @event.listens_for(pool, "checkin")
    def _record_checkin(
        dbapi_connection: object | None,
        connection_record: object,
    ) -> None:
        checked_out.dec()
        if dbapi_connection is not None:
            record_info = getattr(connection_record, "info", {})
            if not record_info.get(_IDLE_MARKER, False):
                record_info[_IDLE_MARKER] = True
                checked_in.inc()

    @event.listens_for(pool, "close")
    def _record_close(
        _dbapi_connection: object,
        connection_record: object,
    ) -> None:
        record_info = getattr(connection_record, "info", {})
        if record_info.pop(_IDLE_MARKER, False):
            checked_in.dec()

    @event.listens_for(pool, "invalidate")
    def _record_invalidation(*_args: object) -> None:
        _POOL_INVALIDATIONS.labels(pool_name).inc()
