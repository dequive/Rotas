from collections.abc import AsyncIterator
from contextvars import ContextVar

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
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


@event.listens_for(AsyncSession.sync_session_class, "after_begin")
def _inject_rls_tenant(session, transaction, connection):  # type: ignore[no-untyped-def]
    tid = _rls_tenant.get()
    if tid is not None:
        connection.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": tid},
        )


async def get_raw_session() -> AsyncIterator[AsyncSession]:
    """Session without RLS — for auth lookups before principal is known."""
    set_rls_tenant(None)
    try:
        async with AsyncSessionLocal() as session:
            yield session
    finally:
        set_rls_tenant(None)
