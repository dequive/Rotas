from collections.abc import AsyncIterator
from contextvars import ContextVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# Pool tuning: 4 workers × pool_size=3 × max_overflow=2 = max 20 connections.
# Adjust pool_size and max_overflow to match your PostgreSQL max_connections.
_pool_kwargs: dict = {}
if settings.environment == "production":
    _pool_kwargs = {"pool_size": 3, "max_overflow": 2, "pool_timeout": 10}

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    **_pool_kwargs,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# ─── RLS context ─────────────────────────────────────────────────────────────
_rls_tenant: ContextVar[str | None] = ContextVar("_rls_tenant", default=None)


def set_rls_tenant(tenant_id: str | None) -> None:
    _rls_tenant.set(tenant_id)


def install_rls_context(target_engine: AsyncEngine) -> None:
    """Apply the current tenant at the start of every database transaction.

    Services may commit and therefore release/reacquire a pooled connection.
    Reapplying the transaction-local setting on every BEGIN prevents both
    missing context and tenant leakage across pooled connections.
    """

    @event.listens_for(target_engine.sync_engine, "begin")
    def _apply_tenant_context(connection) -> None:
        tenant_id = _rls_tenant.get()
        if tenant_id is not None:
            connection.execute(
                text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
                {"tenant_id": tenant_id},
            )


install_rls_context(engine)


async def get_raw_session() -> AsyncIterator[AsyncSession]:
    """Session without RLS — for auth lookups before principal is known."""
    set_rls_tenant(None)
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        set_rls_tenant(None)
